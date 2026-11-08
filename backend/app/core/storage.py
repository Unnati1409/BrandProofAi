"""
BrandProof AI — Workspace-Isolated Storage Service.
Handles guideline file validation, magic byte verification, size enforcement,
and secure storage in private workspace-scoped paths without public URL exposure.
"""

import io
import os
import re
import zipfile
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import ValidationError

settings = get_settings()

# Default maximum upload size (20 MB)
DEFAULT_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
LOCAL_STORAGE_ROOT = Path(".local_storage")


def sanitize_filename(filename: str) -> str:
    """Strips directory traversal components and unsafe characters from filenames."""
    clean = os.path.basename(filename)
    clean = re.sub(r"[^\w\s.-]", "_", clean).strip()
    return clean or "uploaded_document"


def validate_guideline_file(
    filename: str, content: bytes, max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES
) -> str:
    """
    Validates file size, extension, and genuine magic bytes:
    - PDF: Checks for '%PDF-' header bytes.
    - DOCX: Verifies valid ZIP archive structure containing '[Content_Types].xml' or 'word/'.
    Returns normalized file_type ('pdf' or 'docx').
    Raises ValidationError on invalid content or oversized payload.
    """
    if len(content) == 0:
        raise ValidationError("Uploaded file is empty (0 bytes).")

    if len(content) > max_size_bytes:
        max_mb = max_size_bytes // (1024 * 1024)
        raise ValidationError(
            f"File size exceeds maximum permitted limit of {max_mb}MB (file is {len(content) / (1024 * 1024):.2f}MB)."
        )

    lower_name = filename.lower()

    # 1. PDF Validation
    if lower_name.endswith(".pdf"):
        if not content.startswith(b"%PDF-"):
            raise ValidationError(
                "Invalid PDF document: magic bytes '%PDF-' missing from file header. Possible corrupted or disguised file."
            )
        return "pdf"

    # 2. DOCX Validation
    if lower_name.endswith(".docx"):
        if not content.startswith(b"PK\x03\x04"):
            raise ValidationError("Invalid DOCX document: file is not a valid OpenXML ZIP archive.")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = zf.namelist()
                if not any(
                    name.startswith("word/") or name == "[Content_Types].xml" for name in namelist
                ):
                    raise ValidationError(
                        "Invalid DOCX document: archive does not contain Word document structures."
                    )
        except zipfile.BadZipFile:
            raise ValidationError("Invalid DOCX document: corrupted ZIP archive structure.")
        return "docx"

    raise ValidationError(
        f"Unsupported file format for '{filename}'. Only .pdf and .docx documents are accepted."
    )


def save_workspace_source_file(
    workspace_id: str,
    source_id: str,
    filename: str,
    content: bytes,
) -> str:
    """
    Persists guideline file to private workspace-scoped storage.
    Storage reference convention: '{workspace_id}/guidelines/{source_id}/{filename}'.
    Never exposes public URLs or cloud service credentials.
    """
    clean_name = sanitize_filename(filename)
    relative_path = f"{workspace_id}/guidelines/{source_id}/{clean_name}"

    # In local/staging without hosted Supabase Storage keys, store in private local directory
    dest_path = LOCAL_STORAGE_ROOT / workspace_id / "guidelines" / source_id / clean_name
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(content)

    return relative_path


def read_workspace_source_file(storage_path: str) -> bytes:
    """Reads file bytes from private workspace storage."""
    dest_path = LOCAL_STORAGE_ROOT / storage_path
    if not dest_path.exists():
        raise FileNotFoundError(f"Stored file not found: {storage_path}")
    with open(dest_path, "rb") as f:
        return f.read()
