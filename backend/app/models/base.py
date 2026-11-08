import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CHAR, JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    Uses PostgreSQL native UUID type, falls back to CHAR(36) on SQLite.
    Accepts and returns string UUIDs.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return str(value)


class StringArray(TypeDecorator):
    """
    Platform-independent array of strings.
    Uses PostgreSQL native ARRAY(String), falls back to JSON on SQLite.
    Accepts and returns list[str].
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(String))
        return dialect.type_descriptor(JSON)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return []
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return []
        return list(value)


class Base(DeclarativeBase):
    """Base model providing shared serialization and timestamp defaults."""

    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
