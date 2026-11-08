"""
BrandProof AI — Guideline Document Ingestion Service.
Extracts structured clauses and passages from PDF and DOCX documents with
verifiable page and paragraph references.
"""

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

import pypdf
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.source import SourceDocument, SourcePassage


@dataclass
class ExtractedPassage:
    heading: str | None
    clause_ref: str | None
    passage_text: str
    normalized_text: str
    page_number: int | None
    start_offset: int
    end_offset: int


def normalize_text(text: str) -> str:
    """Normalizes whitespace and removes control characters."""
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf_passages(file_bytes: bytes) -> list[ExtractedPassage]:
    """
    Extracts text passages from PDF document bytes page by page.
    Handles empty or malformed files cleanly.
    """
    if not file_bytes or len(file_bytes.strip()) == 0:
        raise ValueError("Cannot ingest empty PDF file.")

    passages: list[ExtractedPassage] = []
    pages_text: list[str] = []

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            pages_text.append(txt)
    except Exception:
        # Resilient fallback: extract text from PDF streams or ASCII chunks
        stream_matches = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", file_bytes, re.DOTALL)
        if stream_matches:
            pages_text = [m.decode("utf-8", errors="ignore") for m in stream_matches]
        else:
            text_candidate = file_bytes.decode("utf-8", errors="ignore")
            lines = [
                line.strip()
                for line in text_candidate.splitlines()
                if not line.startswith("%") and len(line.strip()) > 3
            ]
            pages_text = ["\n".join(lines)] if lines else []

    if not any(t.strip() for t in pages_text):
        raise ValueError("PDF file contains no readable text.")

    cumulative_offset = 0
    passage_count = 0

    for page_idx, page_text in enumerate(pages_text, start=1):
        page_text = page_text.strip()
        if not page_text:
            continue

        raw_sections = [s.strip() for s in re.split(r"\n\s*\n", page_text) if s.strip()]
        if not raw_sections:
            raw_sections = [page_text]

        for sec_idx, section in enumerate(raw_sections, start=1):
            passage_count += 1
            lines = section.split("\n")
            first_line = lines[0].strip()
            heading = first_line[:120] if len(first_line) < 120 and len(lines) > 1 else None
            clause_ref = f"Page {page_idx}, Section {sec_idx}"

            start_off = cumulative_offset
            end_off = cumulative_offset + len(section)
            cumulative_offset = end_off + 2  # accounted for newline separator

            passages.append(
                ExtractedPassage(
                    heading=heading,
                    clause_ref=clause_ref,
                    passage_text=section,
                    normalized_text=normalize_text(section),
                    page_number=page_idx,
                    start_offset=start_off,
                    end_offset=end_off,
                )
            )

    if not passages:
        raise ValueError("No extractable textual content found in PDF.")

    return passages


def extract_docx_passages(file_bytes: bytes) -> list[ExtractedPassage]:
    """
    Extracts paragraphs from DOCX document bytes using XML extraction.
    """
    if not file_bytes or len(file_bytes.strip()) == 0:
        raise ValueError("Cannot ingest empty DOCX file.")

    try:
        zf = zipfile.ZipFile(io.BytesIO(file_bytes))
        xml_content = zf.read("word/document.xml")
    except Exception as e:
        raise ValueError(f"Malformed or corrupt DOCX archive: {e}") from e

    tree = ET.fromstring(xml_content)
    # XML namespace for WordprocessingML
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs: list[str] = []
    for p in tree.iterfind(".//w:p", ns):
        texts = [node.text for node in p.iterfind(".//w:t", ns) if node.text]
        p_text = "".join(texts).strip()
        if p_text:
            paragraphs.append(p_text)

    if not paragraphs:
        raise ValueError("DOCX document contains no textual paragraphs.")

    passages: list[ExtractedPassage] = []
    cumulative_offset = 0

    for p_idx, para in enumerate(paragraphs, start=1):
        clause_ref = f"Paragraph {p_idx}"
        lines = para.split("\n")
        first_line = lines[0].strip()
        heading = first_line[:120] if len(first_line) < 80 and len(paragraphs) > 1 else None

        start_off = cumulative_offset
        end_off = cumulative_offset + len(para)
        cumulative_offset = end_off + 2

        passages.append(
            ExtractedPassage(
                heading=heading,
                clause_ref=clause_ref,
                passage_text=para,
                normalized_text=normalize_text(para),
                page_number=None,
                start_offset=start_off,
                end_offset=end_off,
            )
        )

    return passages


def ingest_document_passages(
    db: Session,
    document: SourceDocument,
    file_bytes: bytes,
) -> list[SourcePassage]:
    """
    Ingests and persists structured passages for a SourceDocument.
    Updates document status to 'processing' and then 'processed' or 'failed'.
    """
    document.status = "processing"
    db.flush()

    try:
        if document.file_type.lower() == "pdf":
            raw_passages = extract_pdf_passages(file_bytes)
        elif document.file_type.lower() == "docx":
            raw_passages = extract_docx_passages(file_bytes)
        else:
            raise ValueError(f"Unsupported file type for passage ingestion: {document.file_type}")

        # Clear any existing passages for idempotency
        db.execute(delete(SourcePassage).where(SourcePassage.document_id == document.id))

        created_passages: list[SourcePassage] = []
        for p in raw_passages:
            passage = SourcePassage(
                workspace_id=document.workspace_id,
                document_id=document.id,
                heading=p.heading,
                clause_ref=p.clause_ref,
                passage_text=p.passage_text,
                normalized_text=p.normalized_text,
                page_number=p.page_number,
                start_offset=p.start_offset,
                end_offset=p.end_offset,
            )
            db.add(passage)
            created_passages.append(passage)

        document.status = "processed"
        document.error_message = None
        db.flush()
        return created_passages

    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)[:500]
        db.flush()
        raise
