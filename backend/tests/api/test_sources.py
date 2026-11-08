"""
BrandProof AI — Guideline Source Management Tests.
Verifies file upload, magic-byte validation, workspace isolation,
unapproved-candidate invariants, retirement, and RBAC authorization.
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
    """Sets test JWT configuration and resets rate limiter."""
    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", DEFAULT_TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def make_valid_pdf_bytes(title: str = "Brand Guidelines") -> bytes:
    """Generates synthetic valid PDF binary content starting with %PDF- header."""
    return f"%PDF-1.4\n%BrandProof AI Guideline\n1 0 obj\n<< /Title ({title}) >>\nendobj\ntrailer\n<< >>\n%%EOF".encode()


def make_valid_docx_bytes() -> bytes:
    """Generates synthetic valid DOCX ZIP binary containing OpenXML document structure."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Brand Voice</w:t></w:r></w:p></w:body></w:document>',
        )
    return buf.getvalue()


def setup_workspace_with_roles():
    """Helper to provision a fresh workspace with all 5 distinct role users."""
    client = TestClient(app)
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(admin_id, f"admin_{admin_id[:8]}@sources.demo", "Admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Guideline Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    tokens = {"admin": admin_token}
    for role_name in ["brand_owner", "manager", "reviewer", "creator"]:
        uid = str(uuid.uuid4())
        tok = create_user_in_postgres(uid, f"{role_name}_{uid[:8]}@sources.demo", role_name.title())
        tokens[role_name] = tok
        inv_res = client.post(
            f"/api/v1/workspaces/{ws_id}/members/invite",
            json={"email": f"{role_name}_{uid[:8]}@sources.demo", "roles": [role_name]},
            headers=admin_headers,
        )
        assert inv_res.status_code == 201

    headers = {r: {"Authorization": f"Bearer {tokens[r]}"} for r in tokens}
    return client, ws_id, headers, tokens


def test_authorized_brand_owner_can_upload_pdf_guideline():
    """1. Authorized Brand Owner can upload a valid PDF guideline (HTTP 201)."""
    client, ws_id, headers, _ = setup_workspace_with_roles()
    pdf_bytes = make_valid_pdf_bytes("AuraHealth Global Brand Book 2026")

    res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={"file": ("aurahealth_guidelines.pdf", pdf_bytes, "application/pdf")},
        headers=headers["brand_owner"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["filename"] == "aurahealth_guidelines.pdf"
    assert data["file_type"] == "pdf"
    assert data["status"] == "uploaded"
    assert data["file_size_bytes"] == len(pdf_bytes)
    assert data["is_approved"] is False  # Uploaded sources are never auto-approved
    assert ws_id in data["storage_path"]


def test_authorized_brand_owner_can_upload_docx_guideline():
    """Brand Owner can upload a valid DOCX guideline (HTTP 201)."""
    client, ws_id, headers, _ = setup_workspace_with_roles()
    docx_bytes = make_valid_docx_bytes()

    res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={
            "file": (
                "editorial_style.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers["brand_owner"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["file_type"] == "docx"
    assert data["status"] == "uploaded"
    assert data["is_approved"] is False


def test_unauthorized_roles_cannot_upload_guidelines():
    """2. Unauthorized roles (Creator, Reviewer, Manager) cannot upload guidelines (HTTP 403)."""
    client, ws_id, headers, _ = setup_workspace_with_roles()
    pdf_bytes = make_valid_pdf_bytes()

    for unauthorized_role in ["creator", "reviewer", "manager"]:
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/sources/upload",
            files={"file": ("unauth_upload.pdf", pdf_bytes, "application/pdf")},
            headers=headers[unauthorized_role],
        )
        assert res.status_code == 403
        assert (
            "brand_owner" in res.json()["error"]["message"].lower()
            or "admin" in res.json()["error"]["message"].lower()
        )


def test_invalid_file_types_and_corrupted_headers_rejected():
    """6. Files with unsupported extensions or corrupted magic bytes are rejected (HTTP 422)."""
    client, ws_id, headers, _ = setup_workspace_with_roles()

    # Disguised executable (.pdf extension with non-PDF binary)
    res_fake = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={
            "file": (
                "malicious.pdf",
                b"MZ\x90\x00\x03\x00\x00\x00This is an executable",
                "application/pdf",
            )
        },
        headers=headers["brand_owner"],
    )
    assert res_fake.status_code == 422
    assert "magic bytes '%PDF-' missing" in res_fake.json()["error"]["message"]

    # Disguised text file (.docx extension without ZIP structure)
    res_fake_docx = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={
            "file": (
                "plain.docx",
                b"Hello plain text masquerading as docx",
                "application/octet-stream",
            )
        },
        headers=headers["brand_owner"],
    )
    assert res_fake_docx.status_code == 422

    # Unsupported format (.txt)
    res_txt = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={"file": ("notes.txt", b"Plain notes", "text/plain")},
        headers=headers["brand_owner"],
    )
    assert res_txt.status_code == 422
    assert "Only .pdf and .docx documents are accepted" in res_txt.json()["error"]["message"]


def test_oversized_files_rejected():
    """7. Files exceeding the configured max size are rejected (HTTP 422)."""
    client, ws_id, headers, _ = setup_workspace_with_roles()
    # Create oversized payload (>20MB)
    oversized_content = b"%PDF-1.4\n" + b"0" * (20 * 1024 * 1024 + 1024)

    res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={"file": ("huge_brandbook.pdf", oversized_content, "application/pdf")},
        headers=headers["brand_owner"],
    )
    assert res.status_code == 422
    assert "exceeds maximum permitted limit" in res.json()["error"]["message"]


def test_cross_workspace_source_isolation_list_and_get():
    """3 & 4. Users in Workspace Alpha cannot list or retrieve sources belonging to Workspace Beta."""
    client = TestClient(app)

    # Workspace Alpha
    user_a = str(uuid.uuid4())
    token_a = create_user_in_postgres(user_a, f"user_a_{user_a[:8]}@iso.demo", "User A")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    ws_a = client.post(
        "/api/v1/workspaces",
        json={"name": "WS Alpha", "slug": f"ws-a-{user_a[:8]}"},
        headers=headers_a,
    ).json()["id"]

    # Workspace Beta
    user_b = str(uuid.uuid4())
    token_b = create_user_in_postgres(user_b, f"user_b_{user_b[:8]}@iso.demo", "User B")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    ws_b = client.post(
        "/api/v1/workspaces",
        json={"name": "WS Beta", "slug": f"ws-b-{user_b[:8]}"},
        headers=headers_b,
    ).json()["id"]

    # Upload source in Workspace Alpha
    pdf_bytes = make_valid_pdf_bytes("Confidential Alpha Blueprint")
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_a}/sources/upload",
        files={"file": ("alpha_secret.pdf", pdf_bytes, "application/pdf")},
        headers=headers_a,
    )
    assert upload_res.status_code == 201
    source_a_id = upload_res.json()["id"]

    # 3. User B lists sources in Workspace Alpha -> 403 Forbidden
    res_list = client.get(f"/api/v1/workspaces/{ws_a}/sources", headers=headers_b)
    assert res_list.status_code == 403

    # User B lists sources in Workspace Beta -> 0 items
    res_b_list = client.get(f"/api/v1/workspaces/{ws_b}/sources", headers=headers_b)
    assert res_b_list.status_code == 200
    assert len(res_b_list.json()["items"]) == 0

    # 4. User B attempts to retrieve Alpha source metadata -> 403 Forbidden
    res_get_a = client.get(f"/api/v1/workspaces/{ws_a}/sources/{source_a_id}", headers=headers_b)
    assert res_get_a.status_code == 403

    # User B attempts to access Alpha source by faking workspace path -> 404
    res_fake_ws = client.get(f"/api/v1/workspaces/{ws_b}/sources/{source_a_id}", headers=headers_b)
    assert res_fake_ws.status_code == 404


def test_cross_workspace_source_retirement_blocked():
    """5. User in Workspace Beta cannot delete or retire a source in Workspace Alpha."""
    client = TestClient(app)

    # Workspace Alpha
    user_a = str(uuid.uuid4())
    token_a = create_user_in_postgres(user_a, f"user_a_{user_a[:8]}@retire.demo", "User A")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    ws_a = client.post(
        "/api/v1/workspaces",
        json={"name": "WS Alpha Retire", "slug": f"ws-ar-{user_a[:8]}"},
        headers=headers_a,
    ).json()["id"]

    # Workspace Beta
    user_b = str(uuid.uuid4())
    token_b = create_user_in_postgres(user_b, f"user_b_{user_b[:8]}@retire.demo", "User B")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    ws_b = client.post(
        "/api/v1/workspaces",
        json={"name": "WS Beta Retire", "slug": f"ws-br-{user_b[:8]}"},
        headers=headers_b,
    ).json()["id"]

    # Upload source in Alpha
    pdf_bytes = make_valid_pdf_bytes("Protected Policy")
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_a}/sources/upload",
        files={"file": ("protected_doc.pdf", pdf_bytes, "application/pdf")},
        headers=headers_a,
    )
    source_a_id = upload_res.json()["id"]

    # User B attempts to retire Alpha source -> 403 Forbidden
    res_retire = client.delete(
        f"/api/v1/workspaces/{ws_a}/sources/{source_a_id}", headers=headers_b
    )
    assert res_retire.status_code == 403

    # User B attempts to retire targeting WS Beta path -> 404 Not Found
    res_retire_fake = client.delete(
        f"/api/v1/workspaces/{ws_b}/sources/{source_a_id}", headers=headers_b
    )
    assert res_retire_fake.status_code == 404


def test_source_retirement_preserves_metadata_and_marks_retired():
    """10. Retiring a source document marks status as 'retired' and preserves audit history."""
    client, ws_id, headers, _ = setup_workspace_with_roles()
    pdf_bytes = make_valid_pdf_bytes("Old Tone Guidelines")

    # Upload
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/sources/upload",
        files={"file": ("old_tone_2025.pdf", pdf_bytes, "application/pdf")},
        headers=headers["brand_owner"],
    )
    source_id = upload_res.json()["id"]
    assert upload_res.json()["status"] == "uploaded"

    # Brand Owner retires source
    retire_res = client.delete(
        f"/api/v1/workspaces/{ws_id}/sources/{source_id}",
        headers=headers["brand_owner"],
    )
    assert retire_res.status_code == 200
    assert retire_res.json()["status"] == "retired"

    # Confirm metadata retrieval reflects retired status
    get_res = client.get(
        f"/api/v1/workspaces/{ws_id}/sources/{source_id}",
        headers=headers["brand_owner"],
    )
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "retired"
    assert get_res.json()["is_approved"] is False  # A retired source can never be approved
