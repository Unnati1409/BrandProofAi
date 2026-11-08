"""
Authentication & JWT Verification Security Tests.
Verifies cryptographic validation of Supabase access tokens, claim validation,
prohibition of unsigned tokens, and strict rejection of forged or expired tokens.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import decode_and_verify_token
from app.main import app
from tests.security.jwt_test_helpers import DEFAULT_TEST_SECRET, generate_test_jwt

settings = get_settings()


@pytest.fixture(autouse=True)
def configure_test_jwt_secret(monkeypatch):
    """Configures the symmetric test JWT secret for all tests in this module."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", DEFAULT_TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_JWKS_URL", None)


def test_valid_supabase_jwt_accepted():
    """Valid Supabase access token is cryptographically verified and decoded."""
    user_id = str(uuid.uuid4())
    token = generate_test_jwt(sub=user_id, email="alice@aurahealth.demo")

    payload = decode_and_verify_token(token)

    assert payload.sub == user_id
    assert payload.email == "alice@aurahealth.demo"
    assert payload.role == "authenticated"
    assert payload.exp > 0


def test_invalid_signature_rejected():
    """Tokens with an invalid or forged cryptographic signature must be rejected with 401."""
    token = generate_test_jwt(secret="wrong-untrusted-forged-secret-32-chars!")

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token(token)

    assert "signature" in exc_info.value.message.lower()


def test_expired_token_rejected():
    """Expired tokens must be immediately rejected with an explicit expiration message."""
    token = generate_test_jwt(exp_delta_seconds=-300)

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token(token)

    assert "expired" in exc_info.value.message.lower()


def test_wrong_audience_rejected():
    """Tokens issued for a different audience must be rejected."""
    token = generate_test_jwt(audience="unauthorized-service")

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token(token)

    assert "audience" in exc_info.value.message.lower()


def test_wrong_issuer_rejected(monkeypatch):
    """When an issuer is configured, tokens with mismatched issuers must be rejected."""
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://xyz-legit.supabase.co")

    # Generate token with a forged/mismatched issuer
    token = generate_test_jwt(issuer="https://evil-spoof.supabase.co/auth/v1")

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token(token)

    assert "issuer" in exc_info.value.message.lower()


def test_missing_or_empty_token_rejected():
    """Missing or empty token strings must raise UnauthorizedError."""
    with pytest.raises(UnauthorizedError) as exc_1:
        decode_and_verify_token("")
    assert "missing" in exc_1.value.message.lower()

    with pytest.raises(UnauthorizedError) as exc_2:
        decode_and_verify_token("   ")
    assert "missing" in exc_2.value.message.lower()


def test_malformed_token_rejected():
    """Garbage strings or broken JWT formats must be cleanly rejected."""
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token("not.a.valid.jwt.token.string")

    assert (
        "malformed" in exc_info.value.message.lower() or "invalid" in exc_info.value.message.lower()
    )


def test_unsigned_none_algorithm_rejected():
    """Tokens attempting algorithm confusion with 'none' must be strictly blocked."""
    token = generate_test_jwt(algorithm="none")

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token(token)

    assert "unsigned" in exc_info.value.message.lower() or "none" in exc_info.value.message.lower()


def test_non_uuid_subject_rejected():
    """Supabase Auth subject claims must be valid UUIDs; non-UUID subjects are rejected."""
    token = generate_test_jwt(sub="not-a-valid-uuid-12345")

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token(token)

    assert "uuid" in exc_info.value.message.lower()


def test_missing_secret_fails_securely(monkeypatch):
    """When SUPABASE_JWT_SECRET is not configured, symmetric verification fails with a clear error."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", None)

    token = generate_test_jwt()

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_and_verify_token(token)

    assert "supabase_jwt_secret is not configured" in exc_info.value.message.lower()


def test_asymmetric_rs256_jwks_verification(monkeypatch):
    """
    Validates asymmetric RS256 token verification via JWKS.
    Generates an ephemeral RSA private/public key pair, mocks the JWKS client,
    and asserts cryptographic verification passes for a legitimate RSA signature.
    """
    # 1. Generate RSA key pair for testing
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    user_id = str(uuid.uuid4())
    headers = {"kid": "test-rsa-key-1"}
    token = generate_test_jwt(
        sub=user_id,
        email="rsa.user@aurahealth.demo",
        algorithm="RS256",
        secret=private_key,
        headers=headers,
    )

    # 2. Configure JWKS URL
    monkeypatch.setattr(
        settings, "SUPABASE_JWKS_URL", "https://xyz.supabase.co/auth/v1/.well-known/jwks.json"
    )

    # 3. Mock PyJWKClient to return the corresponding public key
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    with patch("app.core.security.get_jwks_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_client.return_value = mock_client

        payload = decode_and_verify_token(token)

        assert payload.sub == user_id
        assert payload.email == "rsa.user@aurahealth.demo"
        mock_client.get_signing_key_from_jwt.assert_called_once_with(token)


def test_api_missing_auth_header_rejected():
    """FastAPI endpoint rejecting request without Authorization header."""
    client = TestClient(app)
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"
    assert "missing" in res.json()["error"]["message"].lower()


def test_api_unknown_user_rejected():
    """FastAPI endpoint rejecting valid token for user not present in database."""
    client = TestClient(app)
    unregistered_uuid = str(uuid.uuid4())
    token = generate_test_jwt(sub=unregistered_uuid, email="unknown@aurahealth.demo")

    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"
    assert "does not exist" in res.json()["error"]["message"].lower()
