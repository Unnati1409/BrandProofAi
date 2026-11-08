"""
RBAC & Multi-Tenant Authorization Security Tests.
Verifies role enforcement, creator separation of concerns, cross-workspace isolation,
immunity to forged headers, and database-driven role freshness against real PostgreSQL 18.4.
"""

import os
import uuid

import psycopg
import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.security.jwt_test_helpers import DEFAULT_TEST_SECRET, generate_test_jwt

settings = get_settings()


def get_db_configs():
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.test")
    configs = {
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "54322",
        "SUPERUSER_DATABASE_URL": "postgresql://postgres@127.0.0.1:54322/postgres",
    }
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    configs[k.strip()] = v.strip()
    return configs


CONFIGS = get_db_configs()
SUPER_URL = CONFIGS["SUPERUSER_DATABASE_URL"]


def is_postgres_available() -> bool:
    try:
        with psycopg.connect(SUPER_URL, autocommit=True, connect_timeout=1):
            return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not is_postgres_available(),
        reason="Requires running Supabase/PostgreSQL instance on port 54322 with migrations applied",
    ),
]


def create_user_in_postgres(user_id: str, email: str, name: str) -> str:
    """Provisions user into auth.users (PostgreSQL) or profiles (SQLite) and returns valid Supabase JWT."""
    from app.db.session import SessionLocal, engine
    from app.models.profile import Profile

    if str(engine.url).startswith("sqlite"):
        with SessionLocal() as db:
            existing = db.get(Profile, user_id)
            if not existing:
                profile = Profile(id=user_id, email=email, full_name=name)
                db.add(profile)
                db.commit()
    else:
        try:
            with psycopg.connect(SUPER_URL, autocommit=True, connect_timeout=2) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth.users (id, email, raw_user_meta_data)
                    VALUES (%s, %s, json_build_object('full_name', %s::text)::jsonb)
                    ON CONFLICT (id) DO UPDATE SET raw_user_meta_data = EXCLUDED.raw_user_meta_data;
                    """,
                    (user_id, email, name),
                )
        except Exception:
            with SessionLocal() as db:
                existing = db.get(Profile, user_id)
                if not existing:
                    profile = Profile(id=user_id, email=email, full_name=name)
                    db.add(profile)
                    db.commit()

    return generate_test_jwt(sub=user_id, email=email)


@pytest.fixture(autouse=True)
def configure_auth_environment(monkeypatch):
    """Sets test JWT configuration."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", DEFAULT_TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_URL", None)


def test_creator_cannot_perform_admin_operations():
    """
    Creator role is strictly prohibited from administrative operations:
    inviting members, updating retention/AI settings, or deleting workspaces.
    """
    client = TestClient(app)

    # 1. Setup Admin user and workspace
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(
        admin_id, f"admin_{admin_id[:8]}@aurahealth.demo", "Admin User"
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Governance Test Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    # 2. Admin invites a Creator
    creator_id = str(uuid.uuid4())
    creator_token = create_user_in_postgres(
        creator_id, f"creator_{creator_id[:8]}@aurahealth.demo", "Creator User"
    )
    creator_headers = {"Authorization": f"Bearer {creator_token}"}

    invite_res = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"creator_{creator_id[:8]}@aurahealth.demo", "roles": ["creator"]},
        headers=admin_headers,
    )
    assert invite_res.status_code == 201

    # 3. Creator attempts Admin action (invite member) -> 403 Forbidden
    unauth_invite = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": "third_user@aurahealth.demo", "roles": ["reviewer"]},
        headers=creator_headers,
    )
    assert unauth_invite.status_code == 403
    assert unauth_invite.json()["error"]["code"] == "FORBIDDEN"

    # 4. Creator attempts Admin action (update settings) -> 403 Forbidden
    unauth_settings = client.patch(
        f"/api/v1/workspaces/{ws_id}/settings",
        json={"retention_days": 180},
        headers=creator_headers,
    )
    assert unauth_settings.status_code == 403
    assert unauth_settings.json()["error"]["code"] == "FORBIDDEN"

    # 5. Creator attempts Admin action (delete workspace) -> 403 Forbidden
    unauth_delete = client.delete(
        f"/api/v1/workspaces/{ws_id}",
        headers=creator_headers,
    )
    assert unauth_delete.status_code == 403


def test_creator_cannot_approve_own_content():
    """
    Core editorial security rule: A content creator can NEVER approve their own submission,
    even if they subsequently hold an administrative or reviewer role.
    """
    client = TestClient(app)

    # 1. Admin creates workspace
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(
        admin_id, f"admin_{admin_id[:8]}@aurahealth.demo", "Admin User"
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Creator Separation Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    # 2. Admin invites Creator
    creator_id = str(uuid.uuid4())
    creator_token = create_user_in_postgres(
        creator_id, f"creator_{creator_id[:8]}@aurahealth.demo", "Creator User"
    )
    creator_headers = {"Authorization": f"Bearer {creator_token}"}

    client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={
            "email": f"creator_{creator_id[:8]}@aurahealth.demo",
            "roles": ["creator", "reviewer"],
        },
        headers=admin_headers,
    )

    # 3. Creator submits content
    content_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json={
            "title": "Summer Campaign Post",
            "file_type": "pasted_text",
            "raw_text": "Clinically proven to reverse skin aging by 15 years in 2 days.",
        },
        headers=creator_headers,
    )
    assert content_res.status_code == 201
    content_id = content_res.json()["id"]

    # 4. Creator attempts to approve their own content -> Expect 403 CREATOR_SELF_APPROVAL
    self_approve_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/approve",
        json={"decision": "approved", "notes": "Self approval attempt"},
        headers=creator_headers,
    )
    assert self_approve_res.status_code == 403
    assert self_approve_res.json()["error"]["code"] == "CREATOR_CANNOT_APPROVE_OWN_CONTENT"


def test_legitimate_reviewer_approval_succeeds():
    """Independent Reviewer who did not author the content can successfully approve it."""
    client = TestClient(app)

    # Setup Workspace
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(
        admin_id, f"admin_{admin_id[:8]}@aurahealth.demo", "Admin User"
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Reviewer Approval Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    # Creator submits
    creator_id = str(uuid.uuid4())
    creator_token = create_user_in_postgres(
        creator_id, f"creator_{creator_id[:8]}@aurahealth.demo", "Creator User"
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"creator_{creator_id[:8]}@aurahealth.demo", "roles": ["creator"]},
        headers=admin_headers,
    )
    content_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json={
            "title": "Valid Draft",
            "file_type": "pasted_text",
            "raw_text": "Contains fully verified brand statements.",
        },
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    content_id = content_res.json()["id"]

    # Reviewer approves
    reviewer_id = str(uuid.uuid4())
    reviewer_token = create_user_in_postgres(
        reviewer_id, f"reviewer_{reviewer_id[:8]}@aurahealth.demo", "Reviewer User"
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"reviewer_{reviewer_id[:8]}@aurahealth.demo", "roles": ["reviewer"]},
        headers=admin_headers,
    )

    approval_res = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{content_id}/approve",
        json={"decision": "approved", "notes": "Thoroughly verified."},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert approval_res.status_code == 200
    assert approval_res.json()["decision"] == "approved"
    assert approval_res.json()["new_state"] == "approved"


def test_reviewer_cannot_manage_workspace_membership():
    """Reviewers are limited to editorial governance; member management is strictly blocked."""
    client = TestClient(app)

    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(
        admin_id, f"admin_{admin_id[:8]}@aurahealth.demo", "Admin User"
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Reviewer Membership Boundary", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    reviewer_id = str(uuid.uuid4())
    reviewer_token = create_user_in_postgres(
        reviewer_id, f"reviewer_{reviewer_id[:8]}@aurahealth.demo", "Reviewer User"
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"reviewer_{reviewer_id[:8]}@aurahealth.demo", "roles": ["reviewer"]},
        headers=admin_headers,
    )
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}

    # Reviewer attempts to invite
    invite_res = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": "unauth@aurahealth.demo", "roles": ["creator"]},
        headers=reviewer_headers,
    )
    assert invite_res.status_code == 403

    # Reviewer attempts to remove member
    remove_res = client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{admin_id}",
        headers=reviewer_headers,
    )
    assert remove_res.status_code == 403


def test_cross_workspace_access_denied():
    """Multi-tenant isolation: Users in Workspace Alpha cannot access Workspace Beta."""
    client = TestClient(app)

    # Workspace Alpha
    user_alpha = str(uuid.uuid4())
    token_alpha = create_user_in_postgres(
        user_alpha, f"alpha_{user_alpha[:8]}@company-a.demo", "Alpha Admin"
    )
    res_a = client.post(
        "/api/v1/workspaces",
        json={"name": "Company Alpha", "slug": f"alpha-{user_alpha[:8]}"},
        headers={"Authorization": f"Bearer {token_alpha}"},
    )
    ws_a_id = res_a.json()["id"]

    # Workspace Beta
    user_beta = str(uuid.uuid4())
    token_beta = create_user_in_postgres(
        user_beta, f"beta_{user_beta[:8]}@company-b.demo", "Beta Admin"
    )
    headers_beta = {"Authorization": f"Bearer {token_beta}"}

    # Beta attempts to read Alpha details -> 403
    cross_details = client.get(f"/api/v1/workspaces/{ws_a_id}", headers=headers_beta)
    assert cross_details.status_code == 403
    assert "not a member" in cross_details.json()["error"]["message"].lower()

    # Beta attempts to list Alpha content -> 403
    cross_content = client.get(f"/api/v1/workspaces/{ws_a_id}/content", headers=headers_beta)
    assert cross_content.status_code == 403

    # Beta attempts to list Alpha members -> 403
    cross_members = client.get(f"/api/v1/workspaces/{ws_a_id}/members", headers=headers_beta)
    assert cross_members.status_code == 403


def test_forged_workspace_headers_rejected():
    """Forged X-Workspace-ID headers do not bypass database membership verification."""
    client = TestClient(app)

    user_alpha = str(uuid.uuid4())
    token_alpha = create_user_in_postgres(
        user_alpha, f"alpha_{user_alpha[:8]}@company-a.demo", "Alpha Admin"
    )
    res_a = client.post(
        "/api/v1/workspaces",
        json={"name": "Company Alpha Header Test", "slug": f"alpha-{user_alpha[:8]}"},
        headers={"Authorization": f"Bearer {token_alpha}"},
    )
    ws_a_id = res_a.json()["id"]

    user_beta = str(uuid.uuid4())
    token_beta = create_user_in_postgres(
        user_beta, f"beta_{user_beta[:8]}@company-b.demo", "Beta Admin"
    )

    # Attacker beta supplies forged X-Workspace-ID header targeting Workspace Alpha on Alpha content endpoint
    forged_res = client.get(
        f"/api/v1/workspaces/{ws_a_id}/content",
        headers={
            "Authorization": f"Bearer {token_beta}",
            "X-Workspace-ID": ws_a_id,
        },
    )
    # The endpoint rejects because user_beta is not a member of ws_a_id
    assert forged_res.status_code == 403
    assert "not a member" in forged_res.json()["error"]["message"].lower()


def test_role_changes_in_database_take_effect_immediately():
    """
    Authorization is read directly from PostgreSQL on EVERY request.
    When an admin changes roles in the database, subsequent requests using the SAME token
    immediately reflect the updated permissions without trusting stale client tokens.
    """
    client = TestClient(app)

    # Admin creates workspace
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(
        admin_id, f"admin_{admin_id[:8]}@aurahealth.demo", "Admin User"
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Dynamic Role Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    # Target user created with single token
    user_id = str(uuid.uuid4())
    user_token = create_user_in_postgres(
        user_id, f"target_{user_id[:8]}@aurahealth.demo", "Target User"
    )
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Step 1: User invited as "creator" only
    client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"target_{user_id[:8]}@aurahealth.demo", "roles": ["creator"]},
        headers=admin_headers,
    )

    # User cannot update settings -> 403 Forbidden
    res_1 = client.patch(
        f"/api/v1/workspaces/{ws_id}/settings",
        json={"retention_days": 60},
        headers=user_headers,
    )
    assert res_1.status_code == 403

    # Step 2: Admin promotes user to "admin"
    promote_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{user_id}",
        json={"roles": ["creator", "admin"]},
        headers=admin_headers,
    )
    assert promote_res.status_code == 200

    # User makes request with SAME original user_token -> now SUCCEEDS (200 OK)!
    res_2 = client.patch(
        f"/api/v1/workspaces/{ws_id}/settings",
        json={"retention_days": 60},
        headers=user_headers,
    )
    assert res_2.status_code == 200
    assert res_2.json()["retention_days"] == 60


def test_disabled_or_empty_role_membership_rejected():
    """Users whose workspace_members record has empty roles are rejected with 403 Forbidden."""
    client = TestClient(app)

    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(
        admin_id, f"admin_{admin_id[:8]}@aurahealth.demo", "Admin User"
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Empty Role Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    user_id = str(uuid.uuid4())
    user_token = create_user_in_postgres(
        user_id, f"inactive_{user_id[:8]}@aurahealth.demo", "Inactive User"
    )
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Directly insert membership with empty roles via superuser
    with psycopg.connect(SUPER_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.workspace_members (workspace_id, user_id, roles)
            VALUES (%s, %s, '{}');
            """,
            (ws_id, user_id),
        )

    # Inactive member attempts to read workspace details -> 403 Forbidden
    res = client.get(f"/api/v1/workspaces/{ws_id}", headers=user_headers)
    assert res.status_code == 403
    assert (
        "inactive" in res.json()["error"]["message"].lower()
        or "no assigned roles" in res.json()["error"]["message"].lower()
    )


def test_task1_five_role_submission_and_approval_matrix():
    """
    Task 1: Strict Five-Role Submission and Approval Matrix.
    Verifies all 12 authorization invariants:
    1. Creator can submit content (201).
    2. Manager cannot submit content (403).
    3. Reviewer cannot submit content (403).
    4. Admin cannot submit content (403).
    5. Brand Owner cannot submit content (403).
    6. Manager can approve eligible content (200).
    7. Reviewer can approve eligible content (200).
    8. Admin cannot approve content (403).
    9. Brand Owner cannot approve content (403).
    10. Creator cannot approve content (403).
    11. Creator holding approval role cannot approve own content (403 CREATOR_CANNOT_APPROVE_OWN_CONTENT).
    12. Direct backend requests cannot bypass restrictions via header or payload spoofing.
    """
    client = TestClient(app)

    # 1. Setup workspace with Admin
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(admin_id, f"admin_{admin_id[:8]}@sakhi.demo", "Admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Task 1 Matrix Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    # 2. Provision members for the other 4 roles
    tokens = {"admin": admin_token}
    for role_name in ["brand_owner", "manager", "reviewer", "creator"]:
        uid = str(uuid.uuid4())
        tok = create_user_in_postgres(uid, f"{role_name}_{uid[:8]}@sakhi.demo", role_name.title())
        tokens[role_name] = tok
        inv_res = client.post(
            f"/api/v1/workspaces/{ws_id}/members/invite",
            json={"email": f"{role_name}_{uid[:8]}@sakhi.demo", "roles": [role_name]},
            headers=admin_headers,
        )
        assert inv_res.status_code == 201

    headers = {r: {"Authorization": f"Bearer {tokens[r]}"} for r in tokens}

    # --------------------------------------------------------------------------
    # SUBMISSION PERMISSION CHECKS
    # --------------------------------------------------------------------------
    content_payload = {
        "title": "Launch Copy v1",
        "file_type": "pasted_text",
        "raw_text": "Clinically proven formula.",
    }

    # 1. Creator CAN submit
    res_creator = client.post(
        f"/api/v1/workspaces/{ws_id}/content", json=content_payload, headers=headers["creator"]
    )
    assert res_creator.status_code == 201
    item_1_id = res_creator.json()["id"]

    # 2. Manager CANNOT submit
    res_mgr = client.post(
        f"/api/v1/workspaces/{ws_id}/content", json=content_payload, headers=headers["manager"]
    )
    assert res_mgr.status_code == 403
    assert "creator" in res_mgr.json()["error"]["message"].lower()

    # 3. Reviewer CANNOT submit
    res_rev = client.post(
        f"/api/v1/workspaces/{ws_id}/content", json=content_payload, headers=headers["reviewer"]
    )
    assert res_rev.status_code == 403
    assert "creator" in res_rev.json()["error"]["message"].lower()

    # 4. Admin CANNOT submit
    res_adm = client.post(
        f"/api/v1/workspaces/{ws_id}/content", json=content_payload, headers=headers["admin"]
    )
    assert res_adm.status_code == 403
    assert "creator" in res_adm.json()["error"]["message"].lower()

    # 5. Brand Owner CANNOT submit
    res_bo = client.post(
        f"/api/v1/workspaces/{ws_id}/content", json=content_payload, headers=headers["brand_owner"]
    )
    assert res_bo.status_code == 403
    assert "creator" in res_bo.json()["error"]["message"].lower()

    # --------------------------------------------------------------------------
    # APPROVAL PERMISSION CHECKS (on item_1_id created by Creator)
    # --------------------------------------------------------------------------
    approval_payload = {"decision": "approved", "notes": "Governance review complete."}

    # 8. Admin CANNOT approve
    res_adm_app = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{item_1_id}/approve",
        json=approval_payload,
        headers=headers["admin"],
    )
    assert res_adm_app.status_code == 403
    assert (
        "manager" in res_adm_app.json()["error"]["message"].lower()
        or "reviewer" in res_adm_app.json()["error"]["message"].lower()
    )

    # 9. Brand Owner CANNOT approve
    res_bo_app = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{item_1_id}/approve",
        json=approval_payload,
        headers=headers["brand_owner"],
    )
    assert res_bo_app.status_code == 403

    # 10. Creator CANNOT approve (even if calling approve endpoint)
    res_cr_app = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{item_1_id}/approve",
        json=approval_payload,
        headers=headers["creator"],
    )
    assert res_cr_app.status_code == 403

    # 7. Reviewer CAN approve eligible content
    res_rev_app = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{item_1_id}/approve",
        json=approval_payload,
        headers=headers["reviewer"],
    )
    assert res_rev_app.status_code == 200
    assert res_rev_app.json()["decision"] == "approved"
    assert res_rev_app.json()["new_state"] == "approved"

    # 6. Manager CAN approve eligible content (create item 2 by creator)
    res_creator_2 = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json={"title": "Copy Item 2", "file_type": "pasted_text", "raw_text": "Sample text"},
        headers=headers["creator"],
    )
    assert res_creator_2.status_code == 201
    item_2_id = res_creator_2.json()["id"]

    res_mgr_app = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{item_2_id}/approve",
        json=approval_payload,
        headers=headers["manager"],
    )
    assert res_mgr_app.status_code == 200
    assert res_mgr_app.json()["decision"] == "approved"

    # 11. Creator holding approval role (Creator + Reviewer) CANNOT approve own content
    dual_id = str(uuid.uuid4())
    dual_token = create_user_in_postgres(dual_id, f"dual_{dual_id[:8]}@sakhi.demo", "Dual Role")
    client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"dual_{dual_id[:8]}@sakhi.demo", "roles": ["creator", "reviewer"]},
        headers=admin_headers,
    )
    dual_headers = {"Authorization": f"Bearer {dual_token}"}

    # Dual user submits content
    res_dual_create = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json={"title": "Dual Submission", "file_type": "pasted_text", "raw_text": "Self text"},
        headers=dual_headers,
    )
    assert res_dual_create.status_code == 201
    dual_content_id = res_dual_create.json()["id"]

    # Dual user attempts approval of own submission -> 403 CREATOR_CANNOT_APPROVE_OWN_CONTENT
    res_dual_app = client.post(
        f"/api/v1/workspaces/{ws_id}/content/{dual_content_id}/approve",
        json=approval_payload,
        headers=dual_headers,
    )
    assert res_dual_app.status_code == 403
    assert res_dual_app.json()["error"]["code"] == "CREATOR_CANNOT_APPROVE_OWN_CONTENT"

    # 12. Direct backend requests cannot bypass via forged headers
    res_spoof = client.post(
        f"/api/v1/workspaces/{ws_id}/content",
        json=content_payload,
        headers={
            "Authorization": f"Bearer {tokens['manager']}",
            "X-Role": "creator",
            "X-Workspace-Role": "creator",
        },
    )
    assert res_spoof.status_code == 403
