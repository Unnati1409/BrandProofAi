"""
BrandProof AI — Brand Knowledge Extraction Service.
Extracts candidate rules, approved facts, and tone attributes from guideline passages
using Google Gemini (when configured) with deterministic heuristic fallbacks.
Candidates remain strictly UNAPPROVED until confirmed by a Brand Owner.
"""

import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.rule import ApprovedFact, Rule, ToneAttribute
from app.models.source import SourcePassage

logger = logging.getLogger("brandproof.extraction")


def extract_candidates_heuristic(
    passages: list[SourcePassage],
    workspace_id: str,
) -> tuple[list[Rule], list[ApprovedFact], list[ToneAttribute]]:
    """
    Deterministic rule-based extractor that scans passages for known
    guideline phrasing patterns (banned terms, required wording, facts, tone).
    Guarantees reliable candidate generation even if external AI is offline.
    """
    rules: list[Rule] = []
    facts: list[ApprovedFact] = []
    tones: list[ToneAttribute] = []

    for passage in passages:
        text = passage.passage_text
        ref = passage.clause_ref or "Guideline Clause"

        # 1. Banned Terminology patterns
        for line in text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            m_trigger = re.search(
                r"(?:do not use|avoid|never say|prohibited term|banned term)[:\s]+",
                line_str,
                re.IGNORECASE,
            )
            if m_trigger:
                after_trigger = line_str[m_trigger.end() :].strip()
                parts = re.split(
                    r"\s*(?:[-–—]|\buse\b|\binstead\b)\s*", after_trigger, flags=re.IGNORECASE
                )
                raw_term = parts[0].strip().strip("'\"").strip()
                raw_term = re.sub(
                    r"^(?:the term|the word)\s+", "", raw_term, flags=re.IGNORECASE
                ).strip("'\"")
                preferred = parts[1].strip().strip("'\"").strip() if len(parts) > 1 else ""
                preferred = (
                    re.sub(r"\b(?:instead|prefer)\b", "", preferred, flags=re.IGNORECASE)
                    .strip()
                    .strip("'\"")
                    .strip()
                )

                if raw_term and len(raw_term) < 50:
                    rules.append(
                        Rule(
                            workspace_id=workspace_id,
                            source_passage_id=passage.id,
                            rule_type="banned_term",
                            severity="high",
                            status="candidate",
                            payload={"banned_term": raw_term, "preferred_term": preferred},
                            explanation=f"Guideline prohibits using '{raw_term}'. {f'Use {preferred} instead.' if preferred else ''}".strip(),
                        )
                    )

        # 2. Required Wording / Disclaimers
        # e.g., "Must include the following disclaimer: ...", "Always include: ..."
        disclaimer_matches = re.findall(
            r"(?:must include|always include|required disclaimer|disclaimer required)[:\s]+[\"']?([^\"'\n]+)[\"']?",
            text,
            re.IGNORECASE,
        )
        for discl in disclaimer_matches:
            discl = discl.strip()
            discl = (
                re.sub(
                    r"^(?:the following disclaimer|the disclaimer|disclaimer|wording)[:\s]+",
                    "",
                    discl,
                    flags=re.IGNORECASE,
                )
                .strip()
                .strip("'\"")
            )
            if discl and len(discl) > 10:
                rules.append(
                    Rule(
                        workspace_id=workspace_id,
                        source_passage_id=passage.id,
                        rule_type="required_wording",
                        severity="high",
                        status="candidate",
                        payload={"required_term": discl, "context": "disclaimer"},
                        explanation=f"Required disclosure or compliance statement: '{discl}'",
                    )
                )

        # 3. Product Names & Official Spelling
        # e.g., "Product name: AuraHealth (capital H)", "Official name: ProGuard AI"
        product_matches = re.findall(
            r"(?:product name|brand name|official spelling|trademark)[:\s]+[\"']?([A-Za-z0-9_\- ]+)[\"']?",
            text,
            re.IGNORECASE,
        )
        for prod in product_matches:
            prod = prod.strip()
            if prod and 2 < len(prod) < 40:
                rules.append(
                    Rule(
                        workspace_id=workspace_id,
                        source_passage_id=passage.id,
                        rule_type="terminology",
                        severity="medium",
                        status="candidate",
                        payload={"canonical_name": prod, "variants": [prod.lower()]},
                        explanation=f"Canonical brand/product name must be spelled and cased exactly as '{prod}'.",
                    )
                )

        # 4. Approved Facts (Factual assertions, statistics, certifications)
        # e.g., "Contains 100% natural ingredients", "Certified Organic since 2020", "Clinically tested"
        fact_matches = re.findall(
            r"(?:fact|verified|certified|proven to|contains|founded in|trusted by|over \d+[\w\s%]+)[^.\n]+",
            text,
            re.IGNORECASE,
        )
        for fact_text in fact_matches:
            fact_text = fact_text.strip()
            if len(fact_text) > 15:
                facts.append(
                    ApprovedFact(
                        workspace_id=workspace_id,
                        source_passage_id=passage.id,
                        statement=fact_text,
                        source_reference=ref,
                        owner="Brand Team",
                        status="candidate",
                        version=1,
                    )
                )

        # 5. Tone Attributes
        # e.g., "Tone: Confident and Empathetic", "Brand Voice: Professional, Inspiring"
        tone_matches = re.findall(
            r"(?:brand voice|tone of voice|tone)[:\s]+([^.\n]+)", text, re.IGNORECASE
        )
        for tone_desc in tone_matches:
            tone_desc = tone_desc.strip()
            if tone_desc and len(tone_desc) < 80:
                tones.append(
                    ToneAttribute(
                        workspace_id=workspace_id,
                        name=tone_desc[:50],
                        description=f"Tone established in guideline: {tone_desc}",
                        positive_examples=["Clear, empowering, and verified statements."],
                        negative_examples=["Exaggerated, unverified, or pushy claims."],
                        status="candidate",
                    )
                )

    return rules, facts, tones


async def extract_candidates_with_gemini(
    passages: list[SourcePassage],
    workspace_id: str,
    api_key: str,
    model_name: str,
) -> tuple[list[Rule], list[ApprovedFact], list[ToneAttribute]] | None:
    """
    Invokes Google Gemini API to extract structured candidate rules, facts, and tone attributes.
    Returns None if the API call fails, allowing automatic fallback to deterministic extraction.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    combined_text = "\n\n---\n\n".join(
        [
            f"[Passage ID: {p.id} | Ref: {p.clause_ref or 'General'}]\n{p.passage_text}"
            for p in passages[:15]  # Limit context window for speed and efficiency
        ]
    )

    prompt = f"""
You are BrandProof AI's Guideline Parser. Analyze the following brand guideline passages and extract:
1. "rules": List of specific brand rules. Each rule MUST have:
   - "source_passage_id": string (the exact Passage ID from header)
   - "rule_type": one of ["banned_term", "required_wording", "terminology"]
   - "severity": one of ["high", "medium", "low"]
   - "banned_term": string (for banned_term, else null)
   - "preferred_term": string (for banned_term, else null)
   - "required_term": string (for required_wording, else null)
   - "canonical_name": string (for terminology, else null)
   - "explanation": brief explanation
2. "facts": List of approved brand facts and verifiable claims. Each fact MUST have:
   - "source_passage_id": string (the exact Passage ID)
   - "statement": string (the verified factual claim)
   - "source_reference": string
   - "owner": "Brand Team"
3. "tones": List of tone attributes. Each tone MUST have:
   - "name": string
   - "description": string
   - "positive_examples": array of strings
   - "negative_examples": array of strings

Respond ONLY with valid JSON in this exact structure:
{{
  "rules": [...],
  "facts": [...],
  "tones": [...]
}}

GUIDELINE PASSAGES:
{combined_text}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)

            rules: list[Rule] = []
            facts: list[ApprovedFact] = []
            tones: list[ToneAttribute] = []

            for r_data in parsed.get("rules", []):
                p_id = r_data.get("source_passage_id")
                r_type = r_data.get("rule_type", "terminology")
                if r_type not in ["banned_term", "required_wording", "terminology"]:
                    r_type = "terminology"

                payload_dict: dict[str, Any] = {}
                if r_type == "banned_term":
                    payload_dict["banned_term"] = r_data.get("banned_term") or ""
                    payload_dict["preferred_term"] = r_data.get("preferred_term") or ""
                elif r_type == "required_wording":
                    payload_dict["required_term"] = r_data.get("required_term") or ""
                else:
                    payload_dict["canonical_name"] = r_data.get("canonical_name") or ""

                rules.append(
                    Rule(
                        workspace_id=workspace_id,
                        source_passage_id=p_id,
                        rule_type=r_type,
                        severity=r_data.get("severity", "medium"),
                        status="candidate",
                        payload=payload_dict,
                        explanation=r_data.get("explanation", "Extracted brand rule."),
                    )
                )

            for f_data in parsed.get("facts", []):
                facts.append(
                    ApprovedFact(
                        workspace_id=workspace_id,
                        source_passage_id=f_data.get("source_passage_id"),
                        statement=f_data.get("statement", ""),
                        source_reference=f_data.get("source_reference", "Guideline Extract"),
                        owner=f_data.get("owner", "Brand Team"),
                        status="candidate",
                        version=1,
                    )
                )

            for t_data in parsed.get("tones", []):
                tones.append(
                    ToneAttribute(
                        workspace_id=workspace_id,
                        name=t_data.get("name", "Brand Voice"),
                        description=t_data.get("description", ""),
                        positive_examples=t_data.get("positive_examples", []),
                        negative_examples=t_data.get("negative_examples", []),
                        status="candidate",
                    )
                )

            return rules, facts, tones

    except Exception as e:
        logger.warning(f"Gemini candidate extraction failed with error: {e}. Falling back.")
        return None


async def extract_and_persist_candidates(
    db: Session,
    workspace_id: str,
    passages: list[SourcePassage],
) -> dict[str, int]:
    """
    Extracts candidate rules, facts, and tone attributes from passages and persists them as candidates.
    Tries Gemini first if configured; falls back reliably to deterministic extraction.
    """
    settings = get_settings()
    rules: list[Rule] = []
    facts: list[ApprovedFact] = []
    tones: list[ToneAttribute] = []

    if settings.GEMINI_API_KEY:
        gemini_result = await extract_candidates_with_gemini(
            passages=passages,
            workspace_id=workspace_id,
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.GEMINI_TEXT_MODEL,
        )
        if gemini_result is not None:
            rules, facts, tones = gemini_result

    # Fallback to heuristic if Gemini not configured or produced 0 items
    if not rules and not facts and not tones:
        rules, facts, tones = extract_candidates_heuristic(passages, workspace_id)

    # Persist extracted candidates
    for r in rules:
        db.add(r)
    for f in facts:
        db.add(f)
    for t in tones:
        db.add(t)

    db.flush()

    return {
        "candidate_rules": len(rules),
        "candidate_facts": len(facts),
        "candidate_tones": len(tones),
    }
