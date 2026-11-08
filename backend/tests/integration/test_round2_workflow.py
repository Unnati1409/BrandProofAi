"""
BrandProof AI — Complete Round 2 End-to-End Workflow Verification Suite.
Verifies the complete product demonstration:
1. Brand Owner uploads guideline (PDF/DOCX).
2. Guideline is parsed into verifiable passages with page/paragraph refs.
3. Candidate rules, facts, and tone attributes are extracted.
4. Brand Owner explicitly confirms rules and facts (candidates are never active evidence).
5. Creator submits content draft (pasted text or upload).
6. Hybrid Review Engine runs deterministic + accessibility + AI checks.
7. Evidence-backed findings report exact offsets, quotes, severity, and suggestions.
8. Creator resolves findings and submits updated version.
9. Reviewer reviews, comments, and requests changes.
10. Manager / Reviewer approves content (preserving creator self-approval prohibition).
11. Approved content is exported with tamper-evident audit certificate.
"""

import io
import uuid
import zipfile

import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.main import app
from tests.security.jwt_test_helpers import DEFAULT_TEST_SECRET
from tests.security.test_rbac_authorization import create_user_in_postgres


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", DEFAULT_TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def make_guideline_pdf_bytes() -> bytes:
    """Creates synthetic PDF content containing guideline rules, facts, and voice."""
    content = """%PDF-1.4
%BrandProof AI Guideline
1 0 obj
<< /Title (AuraHealth Official Brand Manual) >>
endobj
2 0 obj
<< /Contents 3 0 R >>
endobj
3 0 obj
<< /Length 300 >>
stream
AuraHealth Global Brand Standards 2026

Brand Voice: Confident, scientifically backed, and empathetic.

Terminology Rules:
Official spelling: AuraHealth (capital H). Never spell as aurahealth or Aurahealth.
Do not use 'cure all' - use 'supports wellness' instead.
Prohibited term: cheap - use 'accessible' instead.

Compliance Disclaimers:
Must include the following disclaimer: This product has not been evaluated by the FDA.

Approved Brand Facts:
Contains 100% certified organic botanicals.
Clinically tested across 500 double-blind patient trials.
endstream
endobj
trailer
<< >>
%%EOF"""
    return content.encode("utf-8")


def make_guideline_docx_bytes() -> bytes:
    """Creates synthetic DOCX content with OpenXML document structure."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        zf.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>AuraHealth DOCX Brand Book</w:t></w:r></w:p>
                <w:p><w:r><w:t>Do not use "miracle drug" - use "natural remedy" instead.</w:t></w:r></w:p>
                <w:p><w:r><w:t>Must include: Not intended to diagnose or treat disease.</w:t></w:r></w:p>
              </w:body>
            </w:document>""",
        )
    return buf.getvalue()


def setup_round2_workspace():
    """Provisions a test workspace with all 5 distinct role users."""
    client = TestClient(app)
    admin_id = str(uuid.uuid4())
    admin_tok = create_user_in_postgres(admin_id, f"admin_{admin_id[:8]}@r2.demo", "Admin User")
    admin_h = {"Authorization": f"Bearer {admin_tok}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "AuraHealth Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_h,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    tokens = {"admin": admin_tok}
    user_ids = {"admin": admin_id}
    for role in ["brand_owner", "manager", "reviewer", "creator"]:
        uid = str(uuid.uuid4())
        tok = create_user_in_postgres(uid, f"{role}_{uid[:8]}@r2.demo", role.title())
        tokens[role] = tok
        user_ids[role] = uid
        inv_res = client.post(
            f"/api/v1/workspaces/{ws_id}/members/invite",
            json={"email": f"{role}_{uid[:8]}@r2.demo", "roles": [role]},
            headers=admin_h,
        )
        assert inv_res.status_code == 201

    headers = {r: {"Authorization": f"Bearer {tokens[r]}"} for r in tokens}
    return client, ws_id, headers, user_ids


# ==============================================================================
# TEST 1: COMPLETE END-TO-END DEMO WORKFLOW
# ==============================================================================


def test_complete_round2_demonstration_workflow():
    """
    Executes the full 10-step demonstration requested in the directive:
    1. Brand Owner uploads guideline.
    2. Document is processed and structured passages extracted.
    3. Brand rules and facts are extracted as candidates.
    4. Brand Owner confirms candidate rules/facts (unconfirmed remain inactive).
    5. Creator submits marketing draft with intentional violations.
    6. Review engine detects banned terms, missing disclaimers, casing errors, and accessibility issues.
    7. Creator resolves/dismisses findings and submits updated version.
    8. Review engine on updated version confirms clean compliance.
    9. Reviewer comments and Manager approves (verifying creator separation).
    10. Approved content is exported with tamper-evident audit hash.
    """
    client, ws_id, headers, user_ids = setup_round2_workspace()

    # Step 1: Brand Owner uploads brand guideline
    pdf_bytes = make_guideline_pdf_bytes()
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={"file": ("aurahealth_brand_guide.pdf", pdf_bytes, "application/pdf")},
        headers=headers["brand_owner"],
    )
    assert upload_res.status_code == 201
    source_doc = upload_res.json()
    source_id = source_doc["id"]
    assert source_doc["status"] == "uploaded"
    assert source_doc["is_approved"] is False  # Candidate invariant

    # Step 2: Brand Owner processes guideline document
    proc_res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/{source_id}/process",
        headers=headers["brand_owner"],
    )
    assert proc_res.status_code == 200
    proc_data = proc_res.json()
    assert proc_data["passages_count"] > 0
    assert proc_data["candidate_rules_extracted"] > 0
    assert proc_data["candidate_facts_extracted"] > 0

    # Verify extracted passages
    passages_res = client.get(
        f"/api/v1/workspaces/{ws_id}/sources/{source_id}/passages",
        headers=headers["brand_owner"],
    )
    assert passages_res.status_code == 200
    passages = passages_res.json()
    assert len(passages) > 0
    assert any("AuraHealth" in p["passage_text"] for p in passages)

    # Step 3: Check candidate rules and facts list
    rules_res = client.get(
        f"/api/v1/workspaces/{ws_id}/rules?status=candidate",
        headers=headers["brand_owner"],
    )
    assert rules_res.status_code == 200
    candidate_rules = rules_res.json()
    assert len(candidate_rules) > 0

    facts_res = client.get(
        f"/api/v1/workspaces/{ws_id}/facts?status=candidate",
        headers=headers["brand_owner"],
    )
    assert facts_res.status_code == 200
    candidate_facts = facts_res.json()
    assert len(candidate_facts) > 0

    # Step 4: Brand Owner confirms rules and facts
    confirmed_rule_ids = []
    for r in candidate_rules:
        patch_res = client.patch(
            f"/api/v1/workspaces/{ws_id}/rules/{r['id']}",
            json={"status": "confirmed"},
            headers=headers["brand_owner"],
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "confirmed"
        assert patch_res.json()["confirmed_by"] == user_ids["brand_owner"]
        confirmed_rule_ids.append(r["id"])

    for f in candidate_facts:
        patch_res = client.patch(
            f"/api/v1/workspaces/{ws_id}/facts/{f['id']}",
            json={"status": "confirmed"},
            headers=headers["brand_owner"],
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "confirmed"

    # Step 5: Creator submits a marketing post with intentional violations:
    # - Wrong casing: "Aurahealth" (instead of AuraHealth)
    # - Banned term: "cure all"
    # - Banned term: "cheap"
    # - Missing FDA disclaimer
    # - Accessibility: skipped heading (H1 then H3)
    # - Accessibility: missing image alt text
    violating_content = """# New Aurahealth Release

### Why This Is Revolutionary
Our new supplement is a cure all for daily stress. It is also remarkably cheap.

![](https://example.com/supplement.png)
"""
    submit_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json={
            "title": "Summer Launch Post",
            "file_type": "pasted_text",
            "raw_text": violating_content,
        },
        headers=headers["creator"],
    )
    assert submit_res.status_code == 201
    content_item = submit_res.json()
    content_id = content_item["id"]
    assert content_item["state"] == "draft"

    # Step 6: Trigger review engine
    review_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/review",
        headers=headers["creator"],
    )
    assert review_res.status_code == 200
    findings = review_res.json()
    assert len(findings) >= 4

    # Verify findings contain exact quotes, categories, and suggestions
    found_banned_cure = any("cure all" in f["quoted_submitted_content"] for f in findings)
    found_banned_cheap = any("cheap" in f["quoted_submitted_content"] for f in findings)
    found_casing = any(
        f["category"] == "terminology" and "Aurahealth" in f["quoted_submitted_content"]
        for f in findings
    )
    found_missing_fda = any(
        f["category"] == "required_wording" and "FDA" in f["quoted_approved_source"]
        for f in findings
    )
    found_alt_text = any(
        f["category"] == "accessibility" and "alt" in str(f.get("explanation")).lower()
        for f in findings
    )
    found_heading = any(
        f["category"] == "accessibility" and "heading" in str(f.get("explanation")).lower()
        for f in findings
    )

    assert found_banned_cure, "Review engine failed to detect banned term 'cure all'"
    assert found_banned_cheap, "Review engine failed to detect banned term 'cheap'"
    assert found_casing, "Review engine failed to detect casing violation 'Aurahealth'"
    assert found_missing_fda, "Review engine failed to detect missing FDA disclaimer"
    assert found_alt_text, "Review engine failed to detect missing image alt text"
    assert found_heading, "Review engine failed to detect skipped heading hierarchy"

    # Verify every finding has valid start_offset and end_offset
    for f in findings:
        if f["category"] != "required_wording":  # required wording flags top of document
            quote = f["quoted_submitted_content"]
            assert violating_content[f["start_offset"] : f["end_offset"]] == quote

    # Step 7: Creator resolves findings with reasons
    for f in findings:
        resolve_res = client.patch(
            f"/api/v1/workspaces/{ws_id}/content/findings/{f['id']}",
            json={
                "decision": "applied_suggestion",
                "decision_reason": "Corrected in Version 2 draft.",
            },
            headers=headers["creator"],
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["decision"] == "applied_suggestion"

    # Step 8: Creator submits corrected Version 2
    corrected_content = """# New AuraHealth Release

## Clinically Tested Wellness
Our new supplement supports wellness for daily vitality. It is accessible to all.

This product has not been evaluated by the FDA.

![AuraHealth Daily Supplement Bottle](https://example.com/supplement.png)
"""
    v2_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/versions",
        json={"raw_text": corrected_content},
        headers=headers["creator"],
    )
    assert v2_res.status_code == 200
    assert v2_res.json()["version_number"] == 2

    # Run review on Version 2 -> should have 0 policy violations!
    review_v2_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/review",
        headers=headers["creator"],
    )
    assert review_v2_res.status_code == 200
    v2_findings = review_v2_res.json()
    assert len(v2_findings) == 0, (
        f"Expected 0 violations on corrected content, got {len(v2_findings)}: {v2_findings}"
    )

    # Step 9: Reviewer comments and Reviewer / Manager approves
    # 9a. Reviewer leaves feedback
    comment_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/comments",
        json={
            "content_version_id": v2_res.json()["id"],
            "comment_text": "All guideline claims verified. Copy is approved for publishing.",
        },
        headers=headers["reviewer"],
    )
    assert comment_res.status_code == 200

    # 9b. Verify Creator CANNOT approve own content
    creator_approval_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/approve",
        json={"decision": "approved", "notes": "I approve my own post."},
        headers=headers["creator"],
    )
    assert creator_approval_res.status_code == 403

    # 9c. Reviewer approves content
    approve_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/approve",
        json={"decision": "approved", "notes": "Compliance checks passed 100%."},
        headers=headers["reviewer"],
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["new_state"] == "approved"

    # Step 10: Export approved content
    export_res = client.get(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/export",
        headers=headers["creator"],
    )
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert export_data["state"] == "approved"
    assert export_data["version_number"] == 2
    assert "AuraHealth" in export_data["content_text"]
    assert export_data["approval_metadata"]["approved_by"] == user_ids["reviewer"]
    assert len(export_data["audit_hash"]) == 64  # SHA-256


# ==============================================================================
# TEST 2: DOCX INGESTION & MALFORMED DOCUMENT HANDLING
# ==============================================================================


def test_docx_guideline_ingestion_and_error_handling():
    """Verifies DOCX parsing and error handling on malformed files."""
    client, ws_id, headers, _ = setup_round2_workspace()

    # 1. Valid DOCX Ingestion
    docx_bytes = make_guideline_docx_bytes()
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={
            "file": (
                "aurahealth_guide.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers["brand_owner"],
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["id"]

    proc_res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/{source_id}/process",
        headers=headers["brand_owner"],
    )
    assert proc_res.status_code == 200
    assert proc_res.json()["status"] == "processed"
    assert proc_res.json()["passages_count"] >= 3

    # 2. Corrupt / Empty File Handling
    empty_upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=headers["brand_owner"],
    )
    assert empty_upload_res.status_code in [400, 422]


# ==============================================================================
# TEST 3: UNCONFIRMED CANDIDATES ARE NEVER USED AS ACTIVE EVIDENCE
# ==============================================================================


def test_unconfirmed_candidate_rules_never_used_in_review():
    """
    CRITICAL GOVERNANCE INVARIANT:
    If a rule is extracted but remains status='candidate', the review engine
    must ignore it completely until explicitly confirmed by Brand Owner.
    """
    client, ws_id, headers, _ = setup_round2_workspace()

    # Create a manual candidate rule
    rule_res = client.post(
        f"/api/v1/workspaces/{ws_id}/rules",
        json={
            "rule_type": "banned_term",
            "severity": "high",
            "payload": {"banned_term": "unapproved_term", "preferred_term": "approved_term"},
            "explanation": "Unconfirmed rule",
        },
        headers=headers["brand_owner"],
    )
    assert rule_res.status_code == 201
    assert rule_res.json()["status"] == "candidate"

    # Submit content containing the candidate banned term
    content_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json={
            "title": "Test Candidate Invariant",
            "file_type": "pasted_text",
            "raw_text": "This draft contains unapproved_term in the text.",
        },
        headers=headers["creator"],
    )
    assert content_res.status_code == 201
    c_id = content_res.json()["id"]

    # Run review: must find ZERO violations because the rule is only a candidate!
    review_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{c_id}/review",
        headers=headers["creator"],
    )
    assert review_res.status_code == 200
    findings = review_res.json()
    assert len(findings) == 0, (
        "Candidate rule was illegally used as active evidence before confirmation!"
    )
