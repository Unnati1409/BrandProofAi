"""
BrandProof AI — Hybrid Review Engine.
Combines deterministic rule evaluation (banned words, required terminology,
product casing, accessibility) with Google Gemini AI analysis (claim verification, tone)
grounded strictly in confirmed workspace-specific evidence.
"""

import json
import logging
import re
import time
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content import ContentItem, ContentVersion
from app.models.review import Finding, ReviewRun
from app.models.rule import ApprovedFact, Rule, ToneAttribute

logger = logging.getLogger("brandproof.review_engine")


def run_deterministic_checks(
    raw_text: str,
    rules: list[Rule],
    workspace_id: str,
    run_id: str,
    content_version_id: str,
) -> list[Finding]:
    """
    Executes high-speed deterministic pattern checks against confirmed workspace rules.
    Every finding strictly computes exact start_offset and end_offset from the submitted text.
    Uses exact database constraint values:
    category IN ('terminology', 'banned_term', 'required_wording', 'claim', 'tone', 'accessibility')
    basis_label IN ('rule_based', 'ai_assisted')
    verdict IN ('supported', 'contradicted', 'unsupported', 'needs_human_review')
    accessibility_result IN ('passed', 'failed', 'not_checked')
    decision IN ('open', 'applied_suggestion', 'manual_edit', 'dismissed', 'ask_reviewer')
    """
    findings: list[Finding] = []

    for rule in rules:
        payload = rule.payload or {}

        # 1. Banned Terminology Check
        if rule.rule_type == "banned_term":
            banned_term = payload.get("banned_term")
            preferred_term = payload.get("preferred_term", "")
            if not banned_term:
                continue

            pattern = re.compile(rf"\b{re.escape(banned_term)}\b", re.IGNORECASE)
            for match in pattern.finditer(raw_text):
                start = match.start()
                end = match.end()
                actual_quote = raw_text[start:end]

                suggestions = [preferred_term] if preferred_term else []
                findings.append(
                    Finding(
                        workspace_id=workspace_id,
                        run_id=run_id,
                        content_version_id=content_version_id,
                        category="banned_term",
                        severity=rule.severity or "high",
                        basis_label="rule_based",
                        verdict="contradicted",
                        start_offset=start,
                        end_offset=end,
                        rule_id=rule.id,
                        quoted_submitted_content=actual_quote,
                        quoted_approved_source=f"Banned term: '{banned_term}'. Preferred: '{preferred_term or 'Do not use'}'",
                        source_reference=rule.explanation or "Brand Rule Book",
                        explanation=f"Found prohibited term '{actual_quote}'. Guideline requires avoiding this wording.",
                        suggestions=suggestions,
                        decision="open",
                    )
                )

        # 2. Required Terminology & Disclaimers Check
        elif rule.rule_type == "required_wording":
            required_term = payload.get("required_term")
            if not required_term:
                continue

            if required_term.lower() not in raw_text.lower():
                findings.append(
                    Finding(
                        workspace_id=workspace_id,
                        run_id=run_id,
                        content_version_id=content_version_id,
                        category="required_wording",
                        severity=rule.severity or "high",
                        basis_label="rule_based",
                        verdict="unsupported",
                        start_offset=0,
                        end_offset=min(len(raw_text), 40),
                        rule_id=rule.id,
                        quoted_submitted_content=raw_text[:40] if raw_text else "[Empty Content]",
                        quoted_approved_source=required_term,
                        source_reference=rule.explanation or "Compliance Requirement",
                        explanation=f"Missing mandatory required wording or disclosure: '{required_term}'",
                        suggestions=[f"Include required wording: {required_term}"],
                        decision="open",
                    )
                )

        # 3. Product Name Spelling and Capitalization Check
        elif rule.rule_type == "terminology":
            canonical = payload.get("canonical_name")
            if not canonical:
                continue

            pattern = re.compile(rf"\b{re.escape(canonical)}\b", re.IGNORECASE)
            for match in pattern.finditer(raw_text):
                actual_quote = match.group(0)
                if actual_quote != canonical:
                    findings.append(
                        Finding(
                            workspace_id=workspace_id,
                            run_id=run_id,
                            content_version_id=content_version_id,
                            category="terminology",
                            severity="medium",
                            basis_label="rule_based",
                            verdict="contradicted",
                            start_offset=match.start(),
                            end_offset=match.end(),
                            rule_id=rule.id,
                            quoted_submitted_content=actual_quote,
                            quoted_approved_source=f"Official spelling: '{canonical}'",
                            source_reference=rule.explanation or "Brand Naming Standard",
                            explanation=f"Incorrect product casing or spelling: '{actual_quote}'. Must be cased as '{canonical}'.",
                            suggestions=[canonical],
                            decision="open",
                        )
                    )

    # 4. Accessibility Checks
    # 4a. Missing image alt text
    img_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
    for match in img_pattern.finditer(raw_text):
        alt_text = match.group(1).strip()
        if not alt_text:
            findings.append(
                Finding(
                    workspace_id=workspace_id,
                    run_id=run_id,
                    content_version_id=content_version_id,
                    category="accessibility",
                    severity="medium",
                    basis_label="rule_based",
                    verdict="needs_human_review",
                    start_offset=match.start(),
                    end_offset=match.end(),
                    quoted_submitted_content=match.group(0),
                    quoted_approved_source="WCAG 2.1 Non-text Content (1.1.1): Images must provide descriptive alternative text.",
                    source_reference="Accessibility Standard",
                    explanation="Image is missing descriptive alt text for screen readers.",
                    suggestions=[
                        "Add descriptive alt text inside square brackets: ![Product Hero Image](url)"
                    ],
                    accessibility_result="failed",
                    decision="open",
                )
            )

    # 4b. Heading hierarchy check (e.g. H1 followed directly by H3)
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    last_level = 0
    for match in heading_pattern.finditer(raw_text):
        hashes = match.group(1)
        current_level = len(hashes)
        if last_level > 0 and current_level > last_level + 1:
            findings.append(
                Finding(
                    workspace_id=workspace_id,
                    run_id=run_id,
                    content_version_id=content_version_id,
                    category="accessibility",
                    severity="low",
                    basis_label="rule_based",
                    verdict="needs_human_review",
                    start_offset=match.start(),
                    end_offset=match.end(),
                    quoted_submitted_content=match.group(0),
                    quoted_approved_source="WCAG 2.1 Info and Relationships (1.3.1): Headings must follow sequential logical order without skipping levels.",
                    source_reference="Accessibility Standard",
                    explanation=f"Skipped heading level: jumped from H{last_level} directly to H{current_level}.",
                    suggestions=[
                        f"Use level H{last_level + 1} heading instead of H{current_level}"
                    ],
                    accessibility_result="failed",
                    decision="open",
                )
            )
        last_level = current_level

    return findings


async def run_gemini_evidence_verification(
    raw_text: str,
    facts: list[ApprovedFact],
    tones: list[ToneAttribute],
    workspace_id: str,
    run_id: str,
    content_version_id: str,
    api_key: str,
    model_name: str,
) -> tuple[list[Finding], str | None]:
    """
    Invokes Google Gemini to verify factual claims and tone consistency against confirmed facts.
    Strictly verifies that any quoted submitted text actually exists in raw_text.
    """
    if not facts and not tones:
        return [], "No confirmed facts or tone attributes available for AI verification."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    facts_text = "\n".join(
        [f"- Fact ID {f.id}: '{f.statement}' (Source: {f.source_reference})" for f in facts[:20]]
    )
    tones_text = "\n".join([f"- Tone: '{t.name}': {t.description}" for t in tones[:5]])

    prompt = f"""
You are BrandProof AI's Claim and Tone Verification Engine.
Evaluate the submitted marketing text against the APPROVED BRAND EVIDENCE provided below.

APPROVED FACTS:
{facts_text or "None"}

TONE ATTRIBUTES:
{tones_text or "None"}

SUBMITTED CONTENT TO REVIEW:
\"\"\"
{raw_text}
\"\"\"

TASKS:
1. Identify any claims that CONTRADICT approved facts (verdict: "contradicted", category: "claim").
2. Identify unsupported claims that make assertions without evidence (verdict: "unsupported", category: "claim").
3. Identify statements violating tone attributes (verdict: "needs_human_review", category: "tone").
4. Quoted submitted content MUST be an EXACT, literal verbatim substring of the submitted content.

Respond ONLY with valid JSON in this structure:
{{
  "findings": [
    {{
      "category": "claim" or "tone",
      "severity": "high" or "medium" or "low",
      "verdict": "contradicted" or "unsupported" or "needs_human_review",
      "quoted_submitted_content": "exact substring from submitted content",
      "fact_id": "Fact ID if applicable else null",
      "quoted_approved_source": "the approved fact or tone guideline",
      "explanation": "why this claim is contradicted or unsupported",
      "suggestions": ["suggested correction 1"]
    }}
  ]
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Gemini verification API returned status {resp.status_code}")
                return [], f"Gemini API returned error HTTP {resp.status_code}"

            data = resp.json()
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_json)

            validated_findings: list[Finding] = []
            for item in parsed.get("findings", []):
                quote = item.get("quoted_submitted_content", "").strip()
                if not quote or quote not in raw_text:
                    continue

                start = raw_text.find(quote)
                end = start + len(quote)
                f_id = item.get("fact_id")

                v_cat = item.get("category", "claim")
                if v_cat not in ["claim", "tone"]:
                    v_cat = "claim"

                v_verdict = item.get("verdict", "needs_human_review")
                if v_verdict not in [
                    "supported",
                    "contradicted",
                    "unsupported",
                    "needs_human_review",
                ]:
                    v_verdict = "needs_human_review"

                validated_findings.append(
                    Finding(
                        workspace_id=workspace_id,
                        run_id=run_id,
                        content_version_id=content_version_id,
                        category=v_cat,
                        severity=item.get("severity", "medium"),
                        basis_label="ai_assisted",
                        verdict=v_verdict,
                        start_offset=start,
                        end_offset=end,
                        fact_id=f_id if f_id in [f.id for f in facts] else None,
                        quoted_submitted_content=quote,
                        quoted_approved_source=item.get("quoted_approved_source", "Approved Fact"),
                        source_reference="Verified Fact Base",
                        explanation=item.get(
                            "explanation", "Claim requires alignment with approved facts."
                        ),
                        suggestions=item.get("suggestions", []),
                        decision="open",
                    )
                )

            return validated_findings, None

    except Exception as e:
        logger.warning(f"Gemini verification failed with error: {e}")
        return [], f"Gemini review error: {str(e)[:200]}"


async def execute_content_review(
    db: Session,
    content_item: ContentItem,
    version: ContentVersion,
    user_id: str,
) -> tuple[ReviewRun, list[Finding]]:
    """
    Coordinates end-to-end review run:
    1. Loads ONLY confirmed rules, facts, and tone attributes for the workspace.
    2. Runs deterministic checks.
    3. Runs Gemini evidence verification if configured.
    4. Validates findings and persists review run.
    5. Updates content item state to 'in_review'.
    """
    start_time = time.time()
    settings = get_settings()

    # 1. Load ONLY CONFIRMED rules, facts, tone attributes
    confirmed_rules = (
        db.execute(
            select(Rule).where(
                Rule.workspace_id == content_item.workspace_id,
                Rule.status == "confirmed",
            )
        )
        .scalars()
        .all()
    )

    confirmed_facts = (
        db.execute(
            select(ApprovedFact).where(
                ApprovedFact.workspace_id == content_item.workspace_id,
                ApprovedFact.status == "confirmed",
            )
        )
        .scalars()
        .all()
    )

    # Exclude expired facts from active verification evidence
    today = date.today()
    active_facts = [f for f in confirmed_facts if not f.expiry_date or f.expiry_date >= today]

    confirmed_tones = (
        db.execute(
            select(ToneAttribute).where(
                ToneAttribute.workspace_id == content_item.workspace_id,
                ToneAttribute.status == "confirmed",
            )
        )
        .scalars()
        .all()
    )

    # Create Review Run record with status 'running'
    run = ReviewRun(
        workspace_id=content_item.workspace_id,
        content_version_id=version.id,
        model_identifier=settings.GEMINI_TEXT_MODEL
        if settings.GEMINI_API_KEY
        else "deterministic_engine_v1",
        prompt_version="v2.1",
        status="running",
        created_by=user_id,
    )
    db.add(run)
    db.flush()

    all_findings: list[Finding] = []

    # 2. Run Deterministic Checks
    det_start = time.time()
    det_findings = run_deterministic_checks(
        raw_text=version.raw_text,
        rules=confirmed_rules,
        workspace_id=content_item.workspace_id,
        run_id=run.id,
        content_version_id=version.id,
    )
    det_duration_ms = int((time.time() - det_start) * 1000)
    all_findings.extend(det_findings)

    # 3. Run Gemini Verification
    ai_duration_ms = 0
    not_checked_reason = None
    if settings.GEMINI_API_KEY:
        ai_start = time.time()
        ai_findings, err_reason = await run_gemini_evidence_verification(
            raw_text=version.raw_text,
            facts=active_facts,
            tones=confirmed_tones,
            workspace_id=content_item.workspace_id,
            run_id=run.id,
            content_version_id=version.id,
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.GEMINI_TEXT_MODEL,
        )
        ai_duration_ms = int((time.time() - ai_start) * 1000)
        all_findings.extend(ai_findings)
        not_checked_reason = err_reason
    else:
        not_checked_reason = "Gemini API key not configured; completed deterministic rule and accessibility verification."

    # 4. Persist findings into database
    for f in all_findings:
        if not_checked_reason and not f.not_checked_reason:
            f.not_checked_reason = not_checked_reason
        db.add(f)

    # 5. Finalize ReviewRun: status must be 'complete' (per check constraint)
    total_duration_ms = int((time.time() - start_time) * 1000)
    run.status = "complete"
    run.timings_ms = {
        "deterministic_ms": det_duration_ms,
        "ai_verification_ms": ai_duration_ms,
        "total_ms": total_duration_ms,
    }
    run.failure_reason = not_checked_reason

    # Transition content item state to 'in_review'
    content_item.state = "in_review"
    db.flush()

    return run, all_findings
