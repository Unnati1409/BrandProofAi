"""
Test utilities for generating cryptographically valid and invalid Supabase JWT tokens.
Used exclusively in automated security and integration test suites.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

DEFAULT_TEST_SECRET = "super-secret-supabase-jwt-test-key-32-chars-min!"


def generate_test_jwt(
    sub: str | None = None,
    email: str = "test.user@aurahealth.demo",
    role: str = "authenticated",
    exp_delta_seconds: int = 3600,
    secret: str = DEFAULT_TEST_SECRET,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str = "authenticated",
    extra_claims: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
) -> str:
    """Generates a genuine signed JWT formatted identically to Supabase Auth access tokens."""
    user_id = sub or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=exp_delta_seconds)

    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "aud": audience,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "app_metadata": {"provider": "email", "providers": ["email"]},
        "user_metadata": {"full_name": email.split("@")[0].title()},
    }

    if issuer is not None:
        payload["iss"] = issuer

    if extra_claims:
        payload.update(extra_claims)

    if algorithm.lower() == "none":
        return jwt.encode(payload, key="", algorithm="none")

    return jwt.encode(payload, key=secret, algorithm=algorithm, headers=headers)
