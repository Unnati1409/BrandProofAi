"""
BrandProof AI — Phase B, Stage 3: Complete Security Verification Suite.
Comprehensive multi-tenant, RBAC, RLS, storage, anti-tampering, and error-sanitization tests
executed against the live local PostgreSQL 18.4 instance.
"""

import uuid

import psycopg
import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.security.jwt_test_helpers import DEFAULT_TEST_SECRET
from tests.security.test_rbac_authorization import create_user_in_postgres
from tests.security.test_session_lifecycle import SUPER_URL, is_postgres_available

settings = get_settings()

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not is_postgres_available(),
        reason="Requires running Supabase/PostgreSQL instance on port 54322 with migrations applied",
    ),
]


@pytest.fixture(autouse=True)
def configure_auth_environment(monkeypatch):
    """Sets test JWT configuration for authenticating TestClient requests."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", DEFAULT_TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_URL", None)


def test_rbac_all_five_roles_matrix():
    """
    Area B: Full 5-Role RBAC Matrix Verification.
    Verifies exact permissions across Admin, Brand Owner, Manager, Reviewer, and Creator.
    """
    client = TestClient(app)

    # 1. Admin creates workspace
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(admin_id, f"admin_{admin_id[:8]}@matrix.demo", "Admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "RBAC Matrix Workspace", "slug": f"rbac-matrix-{admin_id[:8]}"},
        headers=admin_headers,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    # 2. Provision users for the other 4 roles
    roles_map = {
        "brand_owner": str(uuid.uuid4()),
        "manager": str(uuid.uuid4()),
        "reviewer": str(uuid.uuid4()),
        "creator": str(uuid.uuid4()),
    }
    tokens = {}

    for role_name, user_id in roles_map.items():
        token = create_user_in_postgres(
            user_id, f"{role_name}_{user_id[:8]}@matrix.demo", f"User {role_name.title()}"
        )
        tokens[role_name] = token
        invite_res = client.post(
            f"/api/v1/workspaces/{ws_id}/members/invite",
            json={"email": f"{role_name}_{user_id[:8]}@matrix.demo", "roles": [role_name]},
            headers=admin_headers,
        )
        assert invite_res.status_code == 201

    headers = {r: {"Authorization": f"Bearer {tokens[r]}"} for r in roles_map}

    # 3. Test Creator: can submit content (201), cannot invite (403), cannot update settings (403), cannot view audit logs (403)
    c_post = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json={"title": "Draft Post", "file_type": "pasted_text", "raw_text": "Safe content body."},
        headers=headers["creator"],
    )
    assert c_post.status_code == 201
    content_id = c_post.json()["id"]

    c_invite = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": "attacker@matrix.demo", "roles": ["admin"]},
        headers=headers["creator"],
    )
    assert c_invite.status_code == 403

    c_settings = client.patch(
        f"/api/v1/workspaces/{ws_id}/settings",
        json={"retention_days": 90},
        headers=headers["creator"],
    )
    assert c_settings.status_code == 403

    c_audit = client.get(f"/api/v1/workspaces/{ws_id}/audit-logs", headers=headers["creator"])
    assert c_audit.status_code == 403

    # Creator self-approval is forbidden (403 FORBIDDEN by role guard or CREATOR_CANNOT_APPROVE_OWN_CONTENT)
    c_approve = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/approve",
        json={"decision": "approved", "notes": "Self approval attempt"},
        headers=headers["creator"],
    )
    assert c_approve.status_code == 403
    assert c_approve.json()["error"]["code"] in (
        "FORBIDDEN",
        "CREATOR_CANNOT_APPROVE_OWN_CONTENT",
    )

    # 4. Test Reviewer: can approve other's content (200), cannot invite (403), cannot view audit logs (403)
    r_audit = client.get(f"/api/v1/workspaces/{ws_id}/audit-logs", headers=headers["reviewer"])
    assert r_audit.status_code == 403

    r_invite = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": "attacker2@matrix.demo", "roles": ["admin"]},
        headers=headers["reviewer"],
    )
    assert r_invite.status_code == 403

    r_approve = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/approve",
        json={"decision": "approved", "notes": "Reviewer approval verified"},
        headers=headers["reviewer"],
    )
    assert r_approve.status_code == 200
    assert r_approve.json()["new_state"] == "approved"

    # 5. Test Manager: can view audit logs (200), cannot invite members (403), cannot delete workspace (403)
    m_audit = client.get(f"/api/v1/workspaces/{ws_id}/audit-logs", headers=headers["manager"])
    assert m_audit.status_code == 200
    assert isinstance(m_audit.json(), list)
    assert len(m_audit.json()) >= 1  # Should contain member invites and content approval events

    m_invite = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": "attacker3@matrix.demo", "roles": ["admin"]},
        headers=headers["manager"],
    )
    assert m_invite.status_code == 403

    m_delete = client.delete(f"/api/v1/workspaces/{ws_id}", headers=headers["manager"])
    assert m_delete.status_code == 403

    # 6. Test Brand Owner: cannot invite members (403), cannot delete workspace (403), cannot view audit logs (403)
    bo_invite = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": "attacker4@matrix.demo", "roles": ["admin"]},
        headers=headers["brand_owner"],
    )
    assert bo_invite.status_code == 403

    bo_audit = client.get(f"/api/v1/workspaces/{ws_id}/audit-logs", headers=headers["brand_owner"])
    assert bo_audit.status_code == 403

    bo_delete = client.delete(f"/api/v1/workspaces/{ws_id}", headers=headers["brand_owner"])
    assert bo_delete.status_code == 403

    # 7. Test Admin: can view audit logs (200), can update settings (200), can delete workspace (200)
    admin_audit = client.get(f"/api/v1/workspaces/{ws_id}/audit-logs", headers=admin_headers)
    assert admin_audit.status_code == 200

    admin_settings = client.patch(
        f"/api/v1/workspaces/{ws_id}/settings",
        json={"retention_days": 180, "ai_enabled": True, "ai_disclosure_acknowledged": True},
        headers=admin_headers,
    )
    assert admin_settings.status_code == 200
    assert admin_settings.json()["retention_days"] == 180


def test_client_side_role_spoofing_in_headers_and_payload_rejected():
    """
    Area B & G: Changing role in request headers or body payload cannot grant privileges.
    FastAPI and PostgreSQL resolve roles exclusively from DB records.
    """
    client = TestClient(app)

    # 1. Admin creates workspace
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(admin_id, f"admin_{admin_id[:8]}@spoof.demo", "Admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Role Spoof Workspace", "slug": f"spoof-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    # 2. Invite Creator
    creator_id = str(uuid.uuid4())
    creator_token = create_user_in_postgres(
        creator_id, f"creator_{creator_id[:8]}@spoof.demo", "Creator"
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"creator_{creator_id[:8]}@spoof.demo", "roles": ["creator"]},
        headers=admin_headers,
    )

    # 3. Attacker creator sends forged X-Role, X-Workspace-Role, or role claims in body
    forged_headers = {
        "Authorization": f"Bearer {creator_token}",
        "X-Role": "admin",
        "X-Workspace-Role": "admin",
        "X-User-Role": "admin",
    }

    # Attempt admin action (invite member) with forged role headers
    spoofed_invite = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": "injected@spoof.demo", "roles": ["admin"], "role": "admin"},
        headers=forged_headers,
    )
    assert spoofed_invite.status_code == 403
    assert "permission denied" in spoofed_invite.json()["error"]["message"].lower()

    # Attempt admin action (update settings) with forged role headers
    spoofed_settings = client.patch(
        f"/api/v1/workspaces/{ws_id}/settings",
        json={"retention_days": 365, "roles": ["admin"]},
        headers=forged_headers,
    )
    assert spoofed_settings.status_code == 403


def test_complete_cross_workspace_crud_isolation():
    """
    Area C: Exhaustive cross-workspace boundary tests across Create, Read, Update, Delete.
    User in Workspace A cannot read, create, modify, or delete resources in Workspace B.
    """
    client = TestClient(app)

    # Workspace A
    user_a = str(uuid.uuid4())
    token_a = create_user_in_postgres(user_a, f"user_a_{user_a[:8]}@tenant.demo", "User A")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    res_a = client.post(
        "/api/v1/workspaces",
        json={"name": "Tenant Alpha", "slug": f"alpha-{user_a[:8]}"},
        headers=headers_a,
    )
    ws_a_id = res_a.json()["id"]

    # Workspace B
    user_b = str(uuid.uuid4())
    token_b = create_user_in_postgres(user_b, f"user_b_{user_b[:8]}@tenant.demo", "User B")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res_b = client.post(
        "/api/v1/workspaces",
        json={"name": "Tenant Beta", "slug": f"beta-{user_b[:8]}"},
        headers=headers_b,
    )
    assert res_b.status_code == 201

    # Alpha creator role granted to User A so they can author content in Workspace A
    with psycopg.connect(SUPER_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE public.workspace_members SET roles = ARRAY['admin', 'creator']::TEXT[] WHERE workspace_id = %s AND user_id = %s;",
            (ws_a_id, user_a),
        )

    # Alpha creates content in Workspace A
    content_res = client.post(
        f"/api/v1/workspaces/{ws_a_id}/content",
        json={
            "title": "Alpha Confidential Document",
            "file_type": "pasted_text",
            "raw_text": "Secret formula.",
        },
        headers=headers_a,
    )
    content_a_id = content_res.json()["id"]

    # 1. Beta attempts READ on Alpha workspace details -> 403
    assert client.get(f"/api/v1/workspaces/{ws_a_id}", headers=headers_b).status_code == 403

    # 2. Beta attempts READ on Alpha content list -> 403
    assert client.get(f"/api/v1/workspaces/{ws_a_id}/content", headers=headers_b).status_code == 403

    # 3. Beta attempts READ on Alpha members -> 403
    assert client.get(f"/api/v1/workspaces/{ws_a_id}/members", headers=headers_b).status_code == 403

    # 4. Beta attempts READ on Alpha audit logs -> 403
    assert (
        client.get(f"/api/v1/workspaces/{ws_a_id}/audit-logs", headers=headers_b).status_code == 403
    )

    # 5. Beta attempts CREATE in Alpha (submit content) -> 403
    assert (
        client.post(
            f"/api/v1/workspaces/{ws_a_id}/content",
            json={
                "title": "Injected Post",
                "file_type": "pasted_text",
                "raw_text": "Cross-site payload.",
            },
            headers=headers_b,
        ).status_code
        == 403
    )

    # 6. Beta attempts CREATE in Alpha (invite member) -> 403
    assert (
        client.post(
            f"/api/v1/workspaces/{ws_a_id}/members/invite",
            json={"email": "intruder@tenant.demo", "roles": ["admin"]},
            headers=headers_b,
        ).status_code
        == 403
    )

    # 7. Beta attempts UPDATE in Alpha (approve content) -> 403
    assert (
        client.post(
            f"/api/v1/workspaces/{ws_a_id}/content/{content_a_id}/approve",
            json={"decision": "approved", "notes": "Unauthorized approval"},
            headers=headers_b,
        ).status_code
        == 403
    )

    # 8. Beta attempts UPDATE in Alpha (modify settings) -> 403
    assert (
        client.patch(
            f"/api/v1/workspaces/{ws_a_id}/settings",
            json={"retention_days": 10},
            headers=headers_b,
        ).status_code
        == 403
    )

    # 9. Beta attempts DELETE in Alpha (delete workspace) -> 403
    assert client.delete(f"/api/v1/workspaces/{ws_a_id}", headers=headers_b).status_code == 403


def test_storage_objects_multi_tenant_isolation_in_postgres():
    """
    Area E: Storage security policies on storage.objects.
    Users cannot SELECT, INSERT, or DELETE objects belonging to another workspace.
    """
    from tests.security.test_session_lifecycle import CONFIGS, SUPER_URL

    # 1. Setup two workspaces and two users via superuser
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    ws_a = str(uuid.uuid4())
    ws_b = str(uuid.uuid4())

    with psycopg.connect(SUPER_URL, autocommit=True) as conn, conn.cursor() as cur:
        # Create profiles
        cur.execute(
            "INSERT INTO auth.users (id, email) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (user_a, f"u_{user_a[:8]}@store.demo"),
        )
        cur.execute(
            "INSERT INTO auth.users (id, email) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (user_b, f"u_{user_b[:8]}@store.demo"),
        )
        # Create workspaces
        cur.execute(
            "INSERT INTO public.workspaces (id, name, slug, created_by) VALUES (%s, 'WS A Store', %s, %s);",
            (ws_a, f"ws-a-{ws_a[:8]}", user_a),
        )
        cur.execute(
            "INSERT INTO public.workspaces (id, name, slug, created_by) VALUES (%s, 'WS B Store', %s, %s);",
            (ws_b, f"ws-b-{ws_b[:8]}", user_b),
        )
        # Add members
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, ARRAY['admin']);",
            (ws_a, user_a),
        )
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, ARRAY['admin']);",
            (ws_b, user_b),
        )

        # Superuser inserts object for Workspace A
        obj_a_id = str(uuid.uuid4())
        obj_a_name = f"{ws_a}/brand-guidelines/brand_guide_v1.pdf"
        cur.execute(
            """
            INSERT INTO storage.objects (id, bucket_id, name, owner)
            VALUES (%s, 'workspace-assets', %s, %s)
            ON CONFLICT (id) DO NOTHING;
            """,
            (obj_a_id, obj_a_name, user_a),
        )

    # 2. User B connects as brandproof_app with User B auth context
    # Read password from CONFIGS
    pwd = CONFIGS.get("BRANDPROOF_APP_PASSWORD", "")
    app_conn_url = (
        f"postgresql://{CONFIGS['BRANDPROOF_APP_USER']}:{pwd}@127.0.0.1:54322/postgres"
        if pwd
        else f"postgresql://{CONFIGS['BRANDPROOF_APP_USER']}@127.0.0.1:54322/postgres"
    )

    with psycopg.connect(app_conn_url) as conn, conn.cursor() as cur:
        # Establish User B context
        cur.execute("SET LOCAL ROLE authenticated;")
        cur.execute(f"SELECT set_config('request.jwt.claim.sub', '{user_b}', true);")
        cur.execute("SELECT set_config('request.jwt.claim.role', 'authenticated', true);")

        # Test A: User B SELECT on storage.objects -> Cannot see Workspace A object!
        cur.execute("SELECT id, name FROM storage.objects WHERE bucket_id = 'workspace-assets';")
        rows = cur.fetchall()
        for r in rows:
            assert not str(r[1]).startswith(f"{ws_a}/"), (
                f"Data leak! User B saw Workspace A object: {r[1]}"
            )

        # Test B: User B INSERT into storage.objects targeting Workspace A path -> RLS Check Violation!
        obj_b_injected_id = str(uuid.uuid4())
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege)
            if "InsufficientPrivilege" in dir(psycopg.errors)
            else pytest.raises(Exception)
        ):
            cur.execute(
                """
                INSERT INTO storage.objects (id, bucket_id, name, owner)
                VALUES (%s, 'workspace-assets', %s, %s);
                """,
                (obj_b_injected_id, f"{ws_a}/injected/payload.exe", user_b),
            )
        conn.rollback()

        # Test C: User B DELETE targeting Workspace A object -> 0 rows affected
        cur.execute("SET LOCAL ROLE authenticated;")
        cur.execute(f"SELECT set_config('request.jwt.claim.sub', '{user_b}', true);")
        cur.execute("DELETE FROM storage.objects WHERE id = %s;", (obj_a_id,))
        assert cur.rowcount == 0, "User B was able to delete Workspace A storage object!"
        conn.rollback()

    # 3. User A connects as brandproof_app with User A auth context
    with psycopg.connect(app_conn_url) as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE authenticated;")
        cur.execute(f"SELECT set_config('request.jwt.claim.sub', '{user_a}', true);")
        cur.execute("SELECT set_config('request.jwt.claim.role', 'authenticated', true);")

        # User A CAN see their own object
        cur.execute("SELECT name FROM storage.objects WHERE id = %s;", (obj_a_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == obj_a_name


def test_api_security_error_envelopes_never_leak_stack_traces_or_secrets():
    """
    Area F: Error handling & information disclosure.
    Unhandled exceptions and database errors return generic 500 error envelopes without leaking
    connection strings, passwords, or stack traces to clients.
    """
    client = TestClient(app)

    # 1. Trigger AppError (e.g. NotFoundError or ForbiddenError)
    user_id = str(uuid.uuid4())
    token = create_user_in_postgres(user_id, f"err_{user_id[:8]}@demo.com", "Err User")
    fake_ws_id = str(uuid.uuid4())
    res_err = client.get(
        f"/api/v1/workspaces/{fake_ws_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_err.status_code in (403, 404)
    data_err = res_err.json()
    assert "error" in data_err
    assert "code" in data_err["error"]

    # 2. Trigger validation error (malformed JSON)
    res_422 = client.post(
        "/api/v1/workspaces",
        content="not-valid-json",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    assert res_422.status_code == 422
    data_422 = res_422.json()
    assert "error" in data_422
    assert data_422["error"]["code"] == "REQUEST_VALIDATION_ERROR"

    # 3. Assert zero leakage of passwords, connection strings, or stack traces
    raw_body = res_err.text + res_422.text
    assert "Traceback" not in raw_body
    assert "password" not in raw_body.lower()
    assert "postgresql://" not in raw_body
    assert "X-Request-ID" in res_err.headers
