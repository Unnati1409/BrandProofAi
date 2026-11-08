"""
Comprehensive PostgreSQL Integration & Security Hardening Test Suite (Stage 1).
Executes all 22 security, RLS, trigger, and constraint test cases against real PostgreSQL 18
using the restricted 'brandproof_app' login and transaction-local identity switching.
"""

import os
import threading
import uuid

import psycopg
import pytest
from psycopg import errors


# Load connection settings from .env.test if present
def get_db_configs():
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.test")
    configs = {
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "54322",
        "BRANDPROOF_APP_USER": "brandproof_app",
        "BRANDPROOF_APP_PASSWORD": "",
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
APP_URL = f"postgresql://{CONFIGS['BRANDPROOF_APP_USER']}:{CONFIGS['BRANDPROOF_APP_PASSWORD']}@{CONFIGS['POSTGRES_HOST']}:{CONFIGS['POSTGRES_PORT']}/postgres"
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


def setup_auth_context(cur, user_id: str, role: str = "authenticated"):
    """Inject transaction-local identity context mimicking FastAPI get_db."""
    cur.execute("SET LOCAL ROLE authenticated;")
    cur.execute(f"SELECT set_config('request.jwt.claim.sub', '{user_id}', true);")
    cur.execute(f"SELECT set_config('request.jwt.claim.role', '{role}', true);")


@pytest.fixture(scope="session")
def super_conn():
    conn = psycopg.connect(SUPER_URL, autocommit=True)
    yield conn
    conn.close()


@pytest.fixture
def seed_data(super_conn):
    """Seed test profiles and workspaces using superuser, then test via restricted role."""
    suffix = uuid.uuid4().hex[:6]
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())
    user_c_id = str(uuid.uuid4())
    ws_a_id = str(uuid.uuid4())
    ws_b_id = str(uuid.uuid4())

    email_a = f"usera_{suffix}@aurahealth.com"
    email_b = f"userb_{suffix}@competitor.com"
    email_c = f"userc_{suffix}@aurahealth.com"

    with super_conn.cursor() as cur:
        # Create auth users (handle_new_user trigger automatically creates public.profiles)
        cur.execute(
            "INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s)",
            (
                user_a_id,
                email_a,
                '{"full_name": "User A"}',
                user_b_id,
                email_b,
                '{"full_name": "User B"}',
                user_c_id,
                email_c,
                '{"full_name": "User C"}',
            ),
        )
        # Create workspaces
        cur.execute(
            "INSERT INTO public.workspaces (id, name, slug, created_by) VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)",
            (
                ws_a_id,
                "AuraHealth Workspace",
                f"aura-{suffix}",
                user_a_id,
                ws_b_id,
                "Competitor Workspace",
                f"comp-{suffix}",
                user_b_id,
            ),
        )
        # Add members:
        # User A is Admin + Creator in WS A
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, %s)",
            (ws_a_id, user_a_id, ["admin", "creator"]),
        )
        # User C is Reviewer in WS A
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, %s)",
            (ws_a_id, user_c_id, ["reviewer"]),
        )
        # User B is Admin in WS B
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, %s)",
            (ws_b_id, user_b_id, ["admin", "creator"]),
        )

    return {
        "user_a": user_a_id,
        "user_b": user_b_id,
        "user_c": user_c_id,
        "ws_a": ws_a_id,
        "ws_b": ws_b_id,
    }


# ==============================================================================
# 1. Privilege Escalation & DDL Tests
# ==============================================================================


def test_sec01_role_escalation_postgres():
    """SEC-01: brandproof_app cannot execute SET ROLE postgres."""
    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("SET ROLE postgres;")


def test_sec02_role_escalation_service_role():
    """SEC-02: brandproof_app cannot execute SET ROLE service_role."""
    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("SET ROLE service_role;")


def test_sec03_schema_immutability_ddl():
    """SEC-03: brandproof_app cannot perform DDL (e.g. DROP TABLE)."""
    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("DROP TABLE public.content_items;")


# ==============================================================================
# 2. GUC Manipulation & Tenant Isolation Tests
# ==============================================================================


def test_sec04_direct_guc_spoofing_sole_admin(seed_data):
    """SEC-04: Setting app.in_workspace_deletion GUC does NOT bypass sole-Admin protection."""
    ws_b = seed_data["ws_b"]
    user_b = seed_data["user_b"]
    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_b)
            # Attacker attempts to spoof GUC
            cur.execute(f"SELECT set_config('app.in_workspace_deletion', '{ws_b}', true);")
            # Deleting the sole admin must still be blocked by prevent_orphan_workspace trigger
            with pytest.raises(errors.CheckViolation):
                cur.execute(
                    "DELETE FROM public.workspace_members WHERE workspace_id = %s AND user_id = %s;",
                    (ws_b, user_b),
                )


def test_sec05_cross_tenant_read_isolation(seed_data, super_conn):
    """SEC-05: User B in WS B cannot read content items belonging to WS A."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    user_b = seed_data["user_b"]
    item_id = str(uuid.uuid4())

    # Create content item in WS A
    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "AuraHealth Secret Memo", "pasted_text", user_a),
        )

    # User B queries content items
    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_b)
            cur.execute("SELECT * FROM public.content_items WHERE workspace_id = %s;", (ws_a,))
            rows = cur.fetchall()
            assert len(rows) == 0, "Tenant leak: User B was able to read WS A content items!"


def test_sec06_cross_tenant_write_isolation(seed_data):
    """SEC-06: User B in WS B cannot insert content items into WS A."""
    ws_a = seed_data["ws_a"]
    user_b = seed_data["user_b"]
    item_id = str(uuid.uuid4())

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_b)
            with pytest.raises((errors.InsufficientPrivilege, errors.CheckViolation)):
                cur.execute(
                    "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) "
                    "VALUES (%s, %s, %s, %s, %s);",
                    (item_id, ws_a, "Tampered Title", "pasted_text", user_b),
                )


# ==============================================================================
# 3. Creator Workflow Mutation & Self-Approval Protection
# ==============================================================================


def test_sec07_creator_workflow_state_mutation(seed_data, super_conn):
    """SEC-07: Creator direct SQL UPDATE content_items SET state = 'approved' is blocked."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    item_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by, state) "
            "VALUES (%s, %s, %s, %s, %s, 'draft')",
            (item_id, ws_a, "Draft Article", "pasted_text", user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_a)
            with pytest.raises(errors.CheckViolation) as exc_info:
                cur.execute(
                    "UPDATE public.content_items SET state = 'approved' WHERE id = %s;", (item_id,)
                )
            assert "Workflow violation" in str(exc_info.value)


def test_sec08_creator_created_by_immutability(seed_data, super_conn):
    """SEC-08: created_by is immutable on content_items."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    user_c = seed_data["user_c"]
    item_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Immutability Test", "pasted_text", user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_a)
            with pytest.raises(errors.CheckViolation) as exc_info:
                cur.execute(
                    "UPDATE public.content_items SET created_by = %s WHERE id = %s;",
                    (user_c, item_id),
                )
            assert "created_by is immutable" in str(exc_info.value)


def test_sec09_creator_workspace_immutability(seed_data, super_conn):
    """SEC-09: workspace_id is immutable on content_items."""
    ws_a = seed_data["ws_a"]
    ws_b = seed_data["ws_b"]
    user_a = seed_data["user_a"]
    item_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Workspace Transfer Attempt", "pasted_text", user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_a)
            with pytest.raises(errors.CheckViolation) as exc_info:
                cur.execute(
                    "UPDATE public.content_items SET workspace_id = %s WHERE id = %s;",
                    (ws_b, item_id),
                )
            assert "workspace_id is immutable" in str(exc_info.value)


def test_sec10_creator_self_approval_blocked(seed_data, super_conn):
    """SEC-10: Content creator cannot approve their own content submission."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    item_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        # Assign reviewer role to user_a (while retaining admin to satisfy sole-admin trigger)
        # so RLS policy allows approval evaluation, reaching creator separation trigger
        cur.execute(
            "UPDATE public.workspace_members SET roles = ARRAY['admin', 'creator', 'reviewer']::TEXT[] WHERE workspace_id = %s AND user_id = %s;",
            (ws_a, user_a),
        )
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Self Approval Item", "pasted_text", user_a),
        )
        cur.execute(
            "INSERT INTO public.content_versions (id, workspace_id, content_id, version_number, raw_text, normalized_text, created_by) "
            "VALUES (%s, %s, %s, 1, 'Self approval text', 'Self approval text', %s)",
            (version_id, ws_a, item_id, user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_a)
            with pytest.raises(errors.CheckViolation) as exc_info:
                cur.execute(
                    "INSERT INTO public.content_approvals (workspace_id, content_id, content_version_id, decision, decided_by) "
                    "VALUES (%s, %s, %s, 'approved', %s);",
                    (ws_a, item_id, version_id, user_a),
                )
            assert "Creator cannot approve their own content" in str(exc_info.value)


def test_sec11_forged_approver_identity_blocked(seed_data, super_conn):
    """SEC-11: Approver cannot forge decided_by identity to another user."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    user_c = seed_data["user_c"]
    item_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Forged Approval Item", "pasted_text", user_a),
        )
        cur.execute(
            "INSERT INTO public.content_versions (id, workspace_id, content_id, version_number, raw_text, normalized_text, created_by) "
            "VALUES (%s, %s, %s, 1, 'Forged approval text', 'Forged approval text', %s)",
            (version_id, ws_a, item_id, user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            # User C (Reviewer) attempts to submit approval listing User A as decided_by
            setup_auth_context(cur, user_c)
            # Blocked by RLS WITH CHECK (decided_by = auth.uid()) and trigger check_creator_not_approver
            with pytest.raises((errors.InsufficientPrivilege, errors.CheckViolation)):
                cur.execute(
                    "INSERT INTO public.content_approvals (workspace_id, content_id, content_version_id, decision, decided_by) "
                    "VALUES (%s, %s, %s, 'approved', %s);",
                    (ws_a, item_id, version_id, user_a),
                )


def test_sec12_legitimate_reviewer_approval_succeeds(seed_data, super_conn):
    """SEC-12: Legitimate reviewer approval succeeds and transitions content state to 'approved'."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    user_c = seed_data["user_c"]
    item_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by, state) "
            "VALUES (%s, %s, %s, %s, %s, 'in_review')",
            (item_id, ws_a, "Legit Review Item", "pasted_text", user_a),
        )
        cur.execute(
            "INSERT INTO public.content_versions (id, workspace_id, content_id, version_number, raw_text, normalized_text, created_by) "
            "VALUES (%s, %s, %s, 1, 'Good compliant text', 'Good compliant text', %s)",
            (version_id, ws_a, item_id, user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_c)
            cur.execute(
                "INSERT INTO public.content_approvals (workspace_id, content_id, content_version_id, decision, decided_by) "
                "VALUES (%s, %s, %s, 'approved', %s);",
                (ws_a, item_id, version_id, user_c),
            )
            # Update state after approval (allowed by trg_protect_content_item_state)
            cur.execute(
                "UPDATE public.content_items SET state = 'approved' WHERE id = %s;",
                (item_id,),
            )
            # Check state transition
            cur.execute("SELECT state FROM public.content_items WHERE id = %s;", (item_id,))
            new_state = cur.fetchone()[0]
            assert new_state == "approved", f"Expected approved, got {new_state}"


# ==============================================================================
# 4. Same-Parent Relational Integrity & Stored Procedure Tests
# ==============================================================================


def test_sec13_same_parent_version_mismatch(seed_data, super_conn):
    """SEC-13: Inserting finding referencing review_run of Version A with content_version_id = Version B fails FK."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    item_id = str(uuid.uuid4())
    ver_1_id = str(uuid.uuid4())
    ver_2_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Version Mismatch Test", "pasted_text", user_a),
        )
        cur.execute(
            "INSERT INTO public.content_versions (id, workspace_id, content_id, version_number, raw_text, normalized_text, created_by) "
            "VALUES (%s, %s, %s, 1, 'v1', 'v1', %s), (%s, %s, %s, 2, 'v2', 'v2', %s)",
            (ver_1_id, ws_a, item_id, user_a, ver_2_id, ws_a, item_id, user_a),
        )
        # Review run belongs to ver_1_id
        cur.execute(
            "INSERT INTO public.review_runs (id, workspace_id, content_version_id, status, created_by) "
            "VALUES (%s, %s, %s, 'running', %s)",
            (run_id, ws_a, ver_1_id, user_a),
        )

    # Attempt to insert finding with mismatched version (ver_2_id instead of ver_1_id)
    # Tested using superuser to prove foreign key constraint fk_findings_run_ver_ws enforces same-parent integrity
    with super_conn.cursor() as cur:
        with pytest.raises(errors.ForeignKeyViolation):
            cur.execute(
                "INSERT INTO public.findings ("
                "  workspace_id, content_version_id, run_id, category, severity, basis_label, "
                "  start_offset, end_offset, quoted_submitted_content, quoted_approved_source, "
                "  source_reference, explanation"
                ") VALUES (%s, %s, %s, 'terminology', 'low', 'rule_based', 0, 5, 'hello', 'world', 'ref-1', 'Typo detected');",
                (ws_a, ver_2_id, run_id),
            )


def test_sec14_cross_workspace_rule_reference(seed_data, super_conn):
    """SEC-14: Calling record_review_finding with rule_id from another workspace is rejected."""
    ws_a = seed_data["ws_a"]
    ws_b = seed_data["ws_b"]
    user_a = seed_data["user_a"]
    item_id = str(uuid.uuid4())
    ver_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    rule_b_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        # Create rule in WS B
        cur.execute(
            "INSERT INTO public.rules (id, workspace_id, rule_type, severity, explanation) "
            "VALUES (%s, %s, 'terminology', 'high', 'Rule B Desc')",
            (rule_b_id, ws_b),
        )
        # Create run in WS A
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Rule Cross Test", "pasted_text", user_a),
        )
        cur.execute(
            "INSERT INTO public.content_versions (id, workspace_id, content_id, version_number, raw_text, normalized_text, created_by) "
            "VALUES (%s, %s, %s, 1, 'text', 'text', %s)",
            (ver_id, ws_a, item_id, user_a),
        )
        cur.execute(
            "INSERT INTO public.review_runs (id, workspace_id, content_version_id, status, created_by) "
            "VALUES (%s, %s, %s, 'running', %s)",
            (run_id, ws_a, ver_id, user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_a)
            with pytest.raises(errors.ForeignKeyViolation) as exc_info:
                cur.execute(
                    "SELECT public.record_review_finding(%s, %s, %s, 'brand_guideline', 'critical', 'rule_basis', 0, 4, 'test', 'approved', 'doc-1', 'Rule mismatch explanation', %s);",
                    (ws_a, run_id, ver_id, rule_b_id),
                )
            assert "Cross-workspace reference rejected" in str(exc_info.value)


def test_sec15_unauthorized_audit_logging(seed_data):
    """SEC-15: Non-member calling record_audit_event fails with insufficient_privilege."""
    ws_a = seed_data["ws_a"]
    user_b = seed_data["user_b"]  # User B is NOT in WS A

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_b)
            with pytest.raises(errors.InsufficientPrivilege) as exc_info:
                cur.execute(
                    "SELECT public.record_audit_event(%s, 'workspace.updated', 'workspace', %s);",
                    (ws_a, ws_a),
                )
            assert "not a workspace member" in str(exc_info.value)


def test_sec16_creator_logging_administrative_event(seed_data, super_conn):
    """SEC-16: Creator member attempting to record administrative audit event is rejected."""
    ws_a = seed_data["ws_a"]
    user_d_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex[:6]

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES (%s, %s, %s)",
            (user_d_id, f"userd_{suffix}@aurahealth.com", '{"full_name": "User D"}'),
        )
        # User D has ONLY creator role
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, %s)",
            (ws_a, user_d_id, ["creator"]),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_d_id)
            with pytest.raises(errors.InsufficientPrivilege) as exc_info:
                cur.execute(
                    "SELECT public.record_audit_event(%s, 'member.role_changed', 'member', %s);",
                    (ws_a, user_d_id),
                )
            assert "Unauthorized: Caller lacks administrative privileges" in str(exc_info.value)


def test_sec17_unauthorized_review_finding(seed_data, super_conn):
    """SEC-17: Non-member cannot call record_review_finding."""
    ws_a = seed_data["ws_a"]
    user_b = seed_data["user_b"]
    item_id = str(uuid.uuid4())
    ver_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Item", "pasted_text", seed_data["user_a"]),
        )
        cur.execute(
            "INSERT INTO public.content_versions (id, workspace_id, content_id, version_number, raw_text, normalized_text, created_by) VALUES (%s, %s, %s, 1, 'text', 'text', %s)",
            (ver_id, ws_a, item_id, seed_data["user_a"]),
        )
        cur.execute(
            "INSERT INTO public.review_runs (id, workspace_id, content_version_id, status, created_by) "
            "VALUES (%s, %s, %s, 'running', %s)",
            (run_id, ws_a, ver_id, seed_data["user_a"]),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_b)
            with pytest.raises(errors.InsufficientPrivilege) as exc_info:
                cur.execute(
                    "SELECT public.record_review_finding(%s, %s, %s, 'brand_guideline', 'critical', 'rule', 0, 4, 't', 'a', 'ref', 'Explanation here');",
                    (ws_a, run_id, ver_id),
                )
            assert "not an active member" in str(exc_info.value)


def test_sec18_finding_on_completed_run_blocked(seed_data, super_conn):
    """SEC-18: Findings cannot be recorded on a completed review run."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    item_id = str(uuid.uuid4())
    ver_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.content_items (id, workspace_id, title, file_type, created_by) VALUES (%s, %s, %s, %s, %s)",
            (item_id, ws_a, "Completed Run Item", "pasted_text", user_a),
        )
        cur.execute(
            "INSERT INTO public.content_versions (id, workspace_id, content_id, version_number, raw_text, normalized_text, created_by) VALUES (%s, %s, %s, 1, 'text', 'text', %s)",
            (ver_id, ws_a, item_id, user_a),
        )
        cur.execute(
            "INSERT INTO public.review_runs (id, workspace_id, content_version_id, status, created_by) "
            "VALUES (%s, %s, %s, 'complete', %s)",
            (run_id, ws_a, ver_id, user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_a)
            with pytest.raises(errors.CheckViolation) as exc_info:
                cur.execute(
                    "SELECT public.record_review_finding(%s, %s, %s, 'brand_guideline', 'minor', 'rule', 0, 4, 't', 'a', 'ref', 'Late finding explanation');",
                    (ws_a, run_id, ver_id),
                )
            assert "cannot accept new findings" in str(exc_info.value)


# ==============================================================================
# 5. Sole-Admin Protection & Controlled Workspace Deletion
# ==============================================================================


def test_sec19_sole_admin_removal_blocked(seed_data):
    """SEC-19: Sole admin cannot be removed or demoted from a workspace."""
    ws_b = seed_data["ws_b"]
    user_b = seed_data["user_b"]

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, user_b)
            # Attempt to demote sole admin to creator only
            with pytest.raises(errors.CheckViolation) as exc_info:
                cur.execute(
                    "UPDATE public.workspace_members SET roles = ARRAY['creator']::TEXT[] WHERE workspace_id = %s AND user_id = %s;",
                    (ws_b, user_b),
                )
            assert "Cannot remove or demote the sole Administrator" in str(exc_info.value)


def test_sec20_concurrent_sole_admin_demotion(super_conn):
    """SEC-20: Concurrent demotions of the last admin are serialized; at least one admin remains."""
    ws_temp = str(uuid.uuid4())
    user_1 = str(uuid.uuid4())
    user_2 = str(uuid.uuid4())
    suffix = uuid.uuid4().hex[:6]

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES (%s, %s, %s), (%s, %s, %s)",
            (
                user_1,
                f"u1_{suffix}@test.com",
                '{"full_name": "U1"}',
                user_2,
                f"u2_{suffix}@test.com",
                '{"full_name": "U2"}',
            ),
        )
        cur.execute(
            "INSERT INTO public.workspaces (id, name, slug, created_by) VALUES (%s, 'Temp WS', %s, %s)",
            (ws_temp, f"temp-{suffix}", user_1),
        )
        # 2 Admins
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, ARRAY['admin']::TEXT[]), (%s, %s, ARRAY['admin']::TEXT[])",
            (ws_temp, user_1, ws_temp, user_2),
        )

    results = []

    def demote_user(target_user):
        try:
            with psycopg.connect(APP_URL) as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        setup_auth_context(cur, target_user)
                        cur.execute(
                            "UPDATE public.workspace_members SET roles = ARRAY['creator']::TEXT[] WHERE workspace_id = %s AND user_id = %s;",
                            (ws_temp, target_user),
                        )
                results.append("success")
        except errors.CheckViolation:
            results.append("blocked")
        except Exception as e:
            results.append(f"error: {e}")

    t1 = threading.Thread(target=demote_user, args=(user_1,))
    t2 = threading.Thread(target=demote_user, args=(user_2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one must succeed, and one must be blocked!
    assert "success" in results, f"Expected at least one success: {results}"
    assert "blocked" in results, f"Expected one blocked: {results}"

    # Verify at least 1 admin remains in database
    with super_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM public.workspace_members WHERE workspace_id = %s AND 'admin' = ANY(roles);",
            (ws_temp,),
        )
        count = cur.fetchone()[0]
        assert count == 1, f"Expected 1 admin remaining, got {count}"


def test_sec21_controlled_workspace_deletion(seed_data, super_conn):
    """SEC-21: delete_workspace procedure deletes workspace and all cascading members cleanly."""
    ws_del_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex[:6]

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES (%s, %s, %s)",
            (admin_id, f"del_admin_{suffix}@test.com", '{"full_name": "Delete Admin"}'),
        )
        cur.execute(
            "INSERT INTO public.workspaces (id, name, slug, created_by) VALUES (%s, 'To Delete', %s, %s)",
            (ws_del_id, f"del-{suffix}", admin_id),
        )
        cur.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, roles) VALUES (%s, %s, ARRAY['admin']::TEXT[])",
            (ws_del_id, admin_id),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            setup_auth_context(cur, admin_id)
            cur.execute("SELECT public.delete_workspace(%s);", (ws_del_id,))

    # Confirm workspace and members are gone
    with super_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM public.workspaces WHERE id = %s;", (ws_del_id,))
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT COUNT(*) FROM public.workspace_members WHERE workspace_id = %s;", (ws_del_id,)
        )
        assert cur.fetchone()[0] == 0


def test_sec22_storage_objects_isolation(seed_data, super_conn):
    """SEC-22: Member of WS B attempting to read WS A storage objects receives 0 rows."""
    ws_a = seed_data["ws_a"]
    user_a = seed_data["user_a"]
    user_b = seed_data["user_b"]
    obj_id = str(uuid.uuid4())

    with super_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO storage.objects (id, bucket_id, name, owner) VALUES (%s, 'workspace-assets', %s, %s)",
            (obj_id, f"{ws_a}/asset-1/logo.png", user_a),
        )

    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            # User B attempts to read storage objects
            setup_auth_context(cur, user_b)
            cur.execute("SELECT * FROM storage.objects WHERE bucket_id = 'workspace-assets';")
            rows = cur.fetchall()
            # User B should see 0 rows from WS A
            for r in rows:
                assert not str(r[2]).startswith(f"{ws_a}/"), "Storage tenant leak detected!"


def test_sec23_security_definer_search_path_and_schema_isolation(super_conn):
    """
    SEC-23: Reconcile all SECURITY DEFINER functions in PostgreSQL:
    1. All SECURITY DEFINER functions in public must have search_path explicitly set to '' (empty string).
    2. All functions must be owned by superuser 'postgres'.
    3. Untrusted roles ('brandproof_app', 'authenticated') cannot CREATE objects in 'public' or 'auth' schemas.
    """
    # 1. Inspect all SECURITY DEFINER functions in public schema
    with super_conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.proname, r.rolname, p.proconfig
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_roles r ON r.oid = p.proowner
            WHERE p.prosecdef = true AND n.nspname = 'public'
            ORDER BY p.proname;
            """
        )
        funcs = cur.fetchall()
        assert len(funcs) >= 11, (
            f"Expected at least 11 SECURITY DEFINER functions, found {len(funcs)}"
        )

        for proname, owner, config in funcs:
            assert owner == "postgres", (
                f"Function {proname} is owned by '{owner}', expected 'postgres'"
            )
            assert config == ['search_path=""'], (
                f"Function {proname} has vulnerable or non-empty search_path: {config}. Expected ['search_path=\"\"']."
            )

    # 2. Verify 'brandproof_app' cannot CREATE objects in public or auth schemas
    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("CREATE TABLE public.sec23_hack_brandproof (id int);")
        conn.rollback()

        with conn.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("CREATE TABLE auth.sec23_hack_brandproof (id int);")
        conn.rollback()

    # 3. Verify 'authenticated' cannot CREATE objects in public or auth schemas
    with psycopg.connect(APP_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL ROLE authenticated;")
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("CREATE TABLE public.sec23_hack_authenticated (id int);")
        conn.rollback()

        with conn.cursor() as cur:
            cur.execute("SET LOCAL ROLE authenticated;")
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("CREATE TABLE auth.sec23_hack_authenticated (id int);")
        conn.rollback()
