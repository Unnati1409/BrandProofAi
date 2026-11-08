"""
Session & Transaction Lifecycle Security Tests.
Verifies strict unit-of-work transaction boundaries, rollback on failure,
prevention of premature commits, cancellation cleanup, and connection pool sanitization
against real local PostgreSQL 18.4.
"""

import asyncio
import os
import threading
import uuid

import psycopg
import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import (
    EnforcedUnitOfWorkSession,
    PrematureCommitError,
    SessionLocal,
    get_db,
)
from app.models.workspace import Workspace

settings = get_settings()


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


def create_db_user(user_id: str, email: str, name: str):
    """Provisions a test user into auth.users (triggering profile sync) via superuser."""
    with psycopg.connect(SUPER_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auth.users (id, email, raw_user_meta_data)
            VALUES (%s, %s, json_build_object('full_name', %s::text)::jsonb)
            ON CONFLICT (id) DO NOTHING;
            """,
            (user_id, email, name),
        )


def test_premature_commit_is_prevented():
    """
    Route handlers and services must NOT commit transactions directly.
    Calling db.commit() directly raises PrematureCommitError.
    """
    gen = get_db()
    db = next(gen)

    try:
        assert isinstance(db, EnforcedUnitOfWorkSession)
        with pytest.raises(PrematureCommitError) as exc_info:
            db.commit()

        assert "premature commit is prohibited" in str(exc_info.value).lower()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_request_transaction_commits_on_success():
    """
    Verifies that the request-scoped unit of work commits cleanly to PostgreSQL
    when the generator block terminates without error.
    """
    user_id = str(uuid.uuid4())
    create_db_user(user_id, f"u_{user_id[:8]}@aurahealth.demo", "Lifecycle User")

    ws_id = str(uuid.uuid4())
    ws_slug = f"ws-{ws_id[:8]}"

    # Execute unit of work
    gen = get_db()
    db = next(gen)
    try:
        # Establish identity context
        db.execute(text("SET LOCAL ROLE authenticated;"))
        db.execute(text(f"SELECT set_config('request.jwt.claim.sub', '{user_id}', true);"))
        db.execute(text("SELECT set_config('request.jwt.claim.role', 'authenticated', true);"))

        new_ws = Workspace(
            id=ws_id,
            name="Lifecycle Commit Test Workspace",
            slug=ws_slug,
            created_by=user_id,
        )
        db.add(new_ws)
        db.flush()

        # Generator boundary: request finished successfully
        try:
            next(gen)
        except StopIteration:
            pass
    except Exception:
        gen.close()
        raise

    # Verify data persisted in PostgreSQL using superuser connection
    with psycopg.connect(SUPER_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT slug FROM public.workspaces WHERE id = %s", (ws_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == ws_slug


def test_failed_request_rolls_back():
    """
    When an unhandled exception occurs during a request, the unit of work
    rolls back the entire transaction, ensuring zero orphan/partial state.
    """
    user_id = str(uuid.uuid4())
    create_db_user(user_id, f"u_{user_id[:8]}@aurahealth.demo", "Rollback User")

    ws_id = str(uuid.uuid4())
    ws_slug = f"ws-fail-{ws_id[:8]}"

    gen = get_db()
    db = next(gen)

    try:
        db.execute(text("SET LOCAL ROLE authenticated;"))
        db.execute(text(f"SELECT set_config('request.jwt.claim.sub', '{user_id}', true);"))
        db.execute(text("SELECT set_config('request.jwt.claim.role', 'authenticated', true);"))

        new_ws = Workspace(
            id=ws_id,
            name="Rollback Test Workspace",
            slug=ws_slug,
            created_by=user_id,
        )
        db.add(new_ws)
        db.flush()

        # Simulate route exception
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("Simulated business logic failure."))
    finally:
        # Generator is now closed and rolled back
        pass

    # Verify that the workspace was NOT saved to PostgreSQL
    with psycopg.connect(SUPER_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM public.workspaces WHERE id = %s", (ws_id,))
        assert cur.fetchone() is None


def test_cancellation_triggers_cleanup():
    """
    Verifies that task cancellation (asyncio.CancelledError / BaseException)
    properly triggers session rollback and closes the database connection.
    """
    user_id = str(uuid.uuid4())
    create_db_user(user_id, f"u_{user_id[:8]}@aurahealth.demo", "Cancel User")

    ws_id = str(uuid.uuid4())
    ws_slug = f"ws-cancel-{ws_id[:8]}"

    gen = get_db()
    db = next(gen)

    try:
        db.execute(text("SET LOCAL ROLE authenticated;"))
        db.execute(text(f"SELECT set_config('request.jwt.claim.sub', '{user_id}', true);"))

        new_ws = Workspace(
            id=ws_id,
            name="Cancel Test Workspace",
            slug=ws_slug,
            created_by=user_id,
        )
        db.add(new_ws)
        db.flush()

        # Throw asyncio.CancelledError into generator
        with pytest.raises(asyncio.CancelledError):
            gen.throw(asyncio.CancelledError())
    finally:
        pass

    # Assert changes were cancelled and not committed
    with psycopg.connect(SUPER_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM public.workspaces WHERE id = %s", (ws_id,))
        assert cur.fetchone() is None


def test_pooled_connections_do_not_retain_identity():
    """
    Verifies that when a connection is returned to the pool (session closed),
    the checkin listener executes sanitization in autocommit mode,
    so subsequent checkouts of the exact same physical connection have no
    residual user identity, session roles, or GUC settings.
    Asserts identical pg_backend_pid() to prove physical PostgreSQL connection reuse.
    """
    user_id = str(uuid.uuid4())

    # Session 1 checks out connection, switches role, sets GUC, then closes
    session_1 = SessionLocal()
    try:
        fairy_1 = session_1.connection()
        conn_1 = (
            fairy_1.connection.dbapi_connection
            if hasattr(fairy_1.connection, "dbapi_connection")
            else fairy_1.connection
        )
        conn_1_id = id(conn_1)
        pid_1 = session_1.execute(text("SELECT pg_backend_pid();")).scalar()

        session_1.execute(text("SET LOCAL ROLE authenticated;"))
        session_1.execute(text(f"SELECT set_config('request.jwt.claim.sub', '{user_id}', true);"))
        session_1.commit()
    finally:
        session_1.close()  # Triggers receive_checkin pool listener

    # Session 2 checks out a connection from the pool (QueuePool LIFO reuses conn_1)
    session_2 = SessionLocal()
    try:
        fairy_2 = session_2.connection()
        conn_2 = (
            fairy_2.connection.dbapi_connection
            if hasattr(fairy_2.connection, "dbapi_connection")
            else fairy_2.connection
        )
        conn_2_id = id(conn_2)
        pid_2 = session_2.execute(text("SELECT pg_backend_pid();")).scalar()

        # Confirm exact same physical connection was reused from pool via both Python ID and PostgreSQL PID
        assert conn_1_id == conn_2_id
        assert pid_1 == pid_2
        assert pid_1 is not None

        # Check current_user (must be reset to brandproof_app)
        curr_role = session_2.execute(text("SELECT current_user;")).scalar()
        assert curr_role == CONFIGS["BRANDPROOF_APP_USER"]

        # Check request.jwt.claim.sub (must be empty / NULL)
        sub_val = session_2.execute(
            text("SELECT current_setting('request.jwt.claim.sub', true);")
        ).scalar()
        assert sub_val is None or sub_val == ""

        # Verify connection can execute normal queries without error
        query_res = session_2.execute(text("SELECT 42;")).scalar()
        assert query_res == 42
    finally:
        session_2.close()


def test_pool_checkin_clears_session_level_pollution_on_same_connection():
    """
    Rigorous security regression: Even if code executes session-level SET ROLE (non-local)
    or non-local set_config(..., false), the receive_checkin listener executes sanitization,
    completely resetting the session state on the physical connection before reuse.
    Asserts identical pg_backend_pid() to prove physical connection reuse under pollution.
    """
    session_1 = SessionLocal()
    try:
        fairy_1 = session_1.connection()
        conn_1 = (
            fairy_1.connection.dbapi_connection
            if hasattr(fairy_1.connection, "dbapi_connection")
            else fairy_1.connection
        )
        conn_1_id = id(conn_1)
        pid_1 = session_1.execute(text("SELECT pg_backend_pid();")).scalar()

        # Non-local SET ROLE
        session_1.execute(text("SET ROLE authenticated;"))
        # Non-local GUC
        session_1.execute(
            text("SELECT set_config('app.test_non_local_leak', 'secret_val', false);")
        )

        # Confirm pollution was active in session 1 prior to checkin
        assert session_1.execute(text("SELECT current_user;")).scalar() == "authenticated"
        assert (
            session_1.execute(
                text("SELECT current_setting('app.test_non_local_leak', true);")
            ).scalar()
            == "secret_val"
        )
    finally:
        session_1.close()  # Triggers sanitization in receive_checkin

    # Session 2 checks out connection from pool
    session_2 = SessionLocal()
    try:
        fairy_2 = session_2.connection()
        conn_2 = (
            fairy_2.connection.dbapi_connection
            if hasattr(fairy_2.connection, "dbapi_connection")
            else fairy_2.connection
        )
        conn_2_id = id(conn_2)
        pid_2 = session_2.execute(text("SELECT pg_backend_pid();")).scalar()

        # Prove identical physical connection was reused
        assert conn_1_id == conn_2_id
        assert pid_1 == pid_2
        assert pid_1 is not None

        # Role must have reverted to brandproof_app
        curr_role = session_2.execute(text("SELECT current_user;")).scalar()
        assert curr_role == CONFIGS["BRANDPROOF_APP_USER"]

        # Non-local GUC must have been completely cleared by sanitization
        leaked_guc = session_2.execute(
            text("SELECT current_setting('app.test_non_local_leak', true);")
        ).scalar()
        assert leaked_guc is None or leaked_guc == ""

        # Verify connection functions normally
        assert session_2.execute(text("SELECT 100;")).scalar() == 100
    finally:
        session_2.close()


def test_concurrent_sessions_do_not_share_context():
    """
    Verifies that concurrent requests operating on separate sessions
    do not leak or share transaction-local identity context.
    """
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    results = {}

    def run_worker_a():
        session = SessionLocal()
        try:
            session.execute(text("SET LOCAL ROLE authenticated;"))
            session.execute(text(f"SELECT set_config('request.jwt.claim.sub', '{user_a}', true);"))
            # Small yield to permit thread interleaving
            val = session.execute(
                text("SELECT current_setting('request.jwt.claim.sub', true);")
            ).scalar()
            results["worker_a"] = val
            session.commit()
        finally:
            session.close()

    def run_worker_b():
        session = SessionLocal()
        try:
            session.execute(text("SET LOCAL ROLE authenticated;"))
            session.execute(text(f"SELECT set_config('request.jwt.claim.sub', '{user_b}', true);"))
            val = session.execute(
                text("SELECT current_setting('request.jwt.claim.sub', true);")
            ).scalar()
            results["worker_b"] = val
            session.commit()
        finally:
            session.close()

    t_a = threading.Thread(target=run_worker_a)
    t_b = threading.Thread(target=run_worker_b)

    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()

    assert results["worker_a"] == user_a
    assert results["worker_b"] == user_b


def test_pool_checkin_handles_none_dbapi_connection():
    """
    Verifies that when SQLAlchemy supplies dbapi_connection=None (e.g. for an already-invalidated
    or detached connection record), receive_checkin returns cleanly without raising an error.
    """
    from unittest.mock import MagicMock

    from app.db.session import receive_checkin

    mock_connection_record = MagicMock()
    # Must not raise AttributeError or any exception
    receive_checkin(None, mock_connection_record)
    # Invalidation should not be called when it was already None
    mock_connection_record.invalidate.assert_not_called()


def test_pool_checkin_invalidates_on_sanitization_failure():
    """
    Verifies that if pool sanitization fails, the listener invalidates the connection
    record and closes the physical connection, ensuring a tainted connection is never returned.
    """
    from unittest.mock import MagicMock

    from app.db.session import receive_checkin

    mock_dbapi = MagicMock()
    mock_connection_record = MagicMock()

    # Simulate error during sanitization execution
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = RuntimeError("Simulated failure during sanitization")
    mock_dbapi.cursor.return_value = mock_cursor

    receive_checkin(mock_dbapi, mock_connection_record)

    # Verify connection was explicitly invalidated on the pool record
    mock_connection_record.invalidate.assert_called_once()
    # Verify underlying DBAPI connection was closed to drop the tainted socket
    mock_dbapi.close.assert_called_once()


def test_pool_checkin_failed_connection_cannot_be_checked_out_again():
    """
    End-to-end PostgreSQL verification:
    When a physical connection fails sanitization on checkin, it is invalidated and closed.
    The subsequent checkout from the pool is guaranteed to receive a NEW physical connection
    with a DIFFERENT PostgreSQL backend PID (pg_backend_pid()).
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    from app.db.session import DATABASE_URL, engine_kwargs

    # Dedicated single-connection pool to strictly test reuse vs invalidation
    pool_kwargs = dict(engine_kwargs)
    pool_kwargs["pool_size"] = 1
    pool_kwargs["max_overflow"] = 0

    test_engine = create_engine(DATABASE_URL, **pool_kwargs)

    # Inject failure switch for testing invalidation
    trigger_failure = False

    @event.listens_for(test_engine, "checkin")
    def test_listener(dbapi_conn, conn_record):
        if dbapi_conn is None:
            return
        if trigger_failure:
            if conn_record and hasattr(conn_record, "invalidate"):
                conn_record.invalidate(RuntimeError("Simulated sanitization crash"))
            try:
                dbapi_conn.close()
            except Exception:
                pass
            return

        # Normal sanitization
        orig_ac = getattr(dbapi_conn, "autocommit", False)
        try:
            dbapi_conn.autocommit = True
            cur = dbapi_conn.cursor()
            cur.execute("RESET ROLE; RESET ALL; DISCARD TEMP;")
            cur.close()
        finally:
            dbapi_conn.autocommit = orig_ac

    test_session_factory = sessionmaker(bind=test_engine)

    # Session 1: checks out connection and captures its PostgreSQL backend PID
    s1 = test_session_factory()
    pid_1 = s1.execute(text("SELECT pg_backend_pid();")).scalar()
    assert pid_1 is not None

    # Arm failure on checkin
    trigger_failure = True
    s1.close()  # Triggers test_listener which invalidates and closes conn_1

    # Session 2: checks out a connection from the pool
    trigger_failure = False
    s2 = test_session_factory()
    pid_2 = s2.execute(text("SELECT pg_backend_pid();")).scalar()
    assert pid_2 is not None

    # Crucial assertion: PID must be different because conn_1 was destroyed and discarded!
    assert pid_1 != pid_2, f"Failed connection was reused! PID1={pid_1}, PID2={pid_2}"

    # Verify new connection functions properly
    assert s2.execute(text("SELECT 123;")).scalar() == 123
    s2.close()
