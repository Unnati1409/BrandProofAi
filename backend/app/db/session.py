import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.base import Base

logger = logging.getLogger("brandproof.db")

settings = get_settings()

DATABASE_URL = settings.DATABASE_URL or "sqlite:///./brandproof_dev.db"

# Normalize PostgreSQL driver to psycopg (v3) when postgresql:// scheme is used
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Engine configuration
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
    "connect_args": connect_args,
}

if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 1800,
        }
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Connection pool sanitization listener
@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection: Any, connection_record: Any) -> None:
    """
    Sanitizes pooled PostgreSQL connections upon checkin back to the pool.
    Ensures that transaction-local GUCs, session-level GUCs, temporary objects,
    and role switches are completely cleared and never leak to subsequent requests.
    If sanitization fails, the connection is invalidated and purged from the pool.
    """
    if not str(engine.url).startswith("sqlite"):
        # Safely handle already-invalidated or closed connections where dbapi_connection is None
        if dbapi_connection is None:
            return

        try:
            # 1. Roll back any active or aborted transaction to ensure IDLE status
            if hasattr(dbapi_connection, "rollback"):
                dbapi_connection.rollback()

            # 2. In psycopg 3, sanitize connection in autocommit mode without starting an implicit transaction.
            # We explicitly execute RESET ROLE, RESET ALL, and DISCARD TEMP.
            # We avoid DISCARD PLANS / DISCARD ALL because discarding prepared plans invalidates psycopg 3's
            # client-side statement cache and causes subsequent executions to fail with 'prepared statement does not exist'.
            orig_autocommit = getattr(dbapi_connection, "autocommit", False)
            try:
                dbapi_connection.autocommit = True
                cursor = dbapi_connection.cursor()
                cursor.execute("RESET ROLE; RESET ALL; DISCARD TEMP;")
                cursor.close()
            finally:
                dbapi_connection.autocommit = orig_autocommit
        except Exception as exc:
            logger.error(
                "Connection pool checkin sanitization failed; invalidating connection: %s", exc
            )
            if connection_record is not None and hasattr(connection_record, "invalidate"):
                connection_record.invalidate(exc)
            try:
                if hasattr(dbapi_connection, "close"):
                    dbapi_connection.close()
            except Exception:
                pass


class PrematureCommitError(RuntimeError):
    """
    Raised when application code attempts to commit a database session directly
    instead of allowing the request-scoped unit of work to manage the transaction.
    """

    pass


class EnforcedUnitOfWorkSession:
    """
    Wraps an active SQLAlchemy Session to strictly enforce unit-of-work boundaries.
    Route handlers and domain services must flush pending operations using `flush()`.
    Direct `commit()` calls from route handlers are prohibited.
    The unit-of-work lifecycle container commits once at the end of the request upon clean completion.
    """

    def __init__(self, session: Session):
        self._session = session
        self._active_uow = True

    @property
    def bind(self) -> Any:
        return self._session.bind

    def commit(self) -> None:
        """Prohibits direct commits from route handlers to prevent premature transaction completion."""
        raise PrematureCommitError(
            "Premature commit is prohibited. Route handlers must not call db.commit(); "
            "use db.flush() for intermediate validation and allow the unit of work to commit."
        )

    def uow_commit(self) -> None:
        """Called exclusively by the dependency lifecycle upon request completion."""
        if self._active_uow:
            self._session.commit()

    def rollback(self) -> None:
        """Rolls back all uncommitted changes in the transaction."""
        self._session.rollback()

    def flush(self) -> None:
        """Flushes pending changes to PostgreSQL so triggers and constraints execute immediately."""
        self._session.flush()

    def refresh(self, instance: Any, *args: Any, **kwargs: Any) -> None:
        self._session.refresh(instance, *args, **kwargs)

    def close(self) -> None:
        self._active_uow = False
        self._session.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    def __enter__(self) -> "EnforcedUnitOfWorkSession":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.uow_commit()


def init_db(target_engine: Any = engine) -> None:
    """Creates database tables defined in SQLAlchemy metadata (used for test setup)."""
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[EnforcedUnitOfWorkSession, None, None]:
    """
    FastAPI request-scoped dependency providing an EnforcedUnitOfWorkSession.
    Begins a transaction, commits only upon clean completion, rolls back on any
    exception or cancellation, and ensures connection sanitization.
    """
    session = SessionLocal()
    uow = EnforcedUnitOfWorkSession(session)
    try:
        yield uow
        uow.uow_commit()
    except BaseException:
        uow.rollback()
        raise
    finally:
        uow.close()
