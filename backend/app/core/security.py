import uuid
from typing import Any

import jwt
from jwt import PyJWKClient, PyJWKClientError
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import CreatorSelfApprovalError, UnauthorizedError

settings = get_settings()

# Cache for JWKS clients by URL to avoid refetching on every request
_jwks_clients: dict[str, PyJWKClient] = {}


def get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Returns or creates a cached PyJWKClient with key set caching enabled."""
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_clients[jwks_url]


class TokenPayload(BaseModel):
    """Verified claims from a genuine Supabase access token."""

    sub: str  # Verified user UUID
    email: str
    exp: int
    iat: int | None = None
    role: str = "authenticated"
    raw_claims: dict[str, Any] = {}


def decode_and_verify_token(token: str) -> TokenPayload:
    """
    Cryptographically verifies a genuine Supabase JWT access token.
    Validates signature, expiration, audience, issuer (if configured), and subject UUID.
    Supports asymmetric JWKS (RS256, ES256) and symmetric (HS256 via SUPABASE_JWT_SECRET).
    Strictly prohibits unsigned tokens ('none' algorithm) and hardcoded secret fallbacks.
    """
    if not token or not token.strip():
        raise UnauthorizedError("Missing authentication token.")

    # 1. Inspect token headers to determine algorithm and key ID
    try:
        unverified_headers = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise UnauthorizedError("Malformed authentication token header.") from None
    except Exception as exc:
        raise UnauthorizedError(f"Invalid token format: {str(exc)}") from None

    alg = unverified_headers.get("alg")
    if not alg or alg.lower() == "none":
        raise UnauthorizedError("Unsigned tokens ('none' algorithm) are strictly prohibited.")

    # 2. Select key and algorithm verification strategy
    key: Any
    allowed_algorithms: list[str] = [alg]

    if alg.startswith("RS") or alg.startswith("ES") or alg.startswith("PS"):
        # Asymmetric signing: verify against trusted Supabase JWKS endpoint
        jwks_url = settings.effective_jwks_url
        if not jwks_url:
            raise UnauthorizedError(
                "Asymmetric token received but SUPABASE_URL or SUPABASE_JWKS_URL is not configured."
            )
        try:
            jwks_client = get_jwks_client(jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            key = signing_key.key
        except PyJWKClientError as exc:
            raise UnauthorizedError(f"Unable to verify signing key from JWKS: {str(exc)}") from None
        except Exception as exc:
            raise UnauthorizedError(f"JWKS key resolution failed: {str(exc)}") from None

    elif alg.startswith("HS"):
        # Symmetric signing: verify using SUPABASE_JWT_SECRET
        if not settings.SUPABASE_JWT_SECRET:
            raise UnauthorizedError(
                "Symmetric token received but SUPABASE_JWT_SECRET is not configured on the backend. "
                "Hardcoded secret fallbacks and service-role key signing are strictly forbidden."
            )
        key = settings.SUPABASE_JWT_SECRET

    else:
        raise UnauthorizedError(f"Unsupported JWT signing algorithm: '{alg}'.")

    # 3. Configure strict verification options
    expected_issuer = (
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1" if settings.SUPABASE_URL else None
    )
    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True,
        "require": ["sub", "exp"],
    }
    if expected_issuer:
        options["verify_iss"] = True

    try:
        decoded: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=allowed_algorithms,
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=expected_issuer,
            options=options,
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Authentication token has expired. Please log in again.") from None
    except jwt.InvalidAudienceError:
        raise UnauthorizedError(
            f"Invalid token audience. Expected '{settings.SUPABASE_JWT_AUDIENCE}'."
        ) from None
    except jwt.InvalidIssuerError:
        raise UnauthorizedError(f"Invalid token issuer. Expected '{expected_issuer}'.") from None
    except jwt.InvalidSignatureError:
        raise UnauthorizedError(
            "Invalid token signature. Cryptographic verification failed."
        ) from None
    except jwt.DecodeError:
        raise UnauthorizedError("Malformed authentication token payload.") from None
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f"Invalid authentication token: {str(exc)}") from None

    # 4. Strict subject validation (must be a valid UUID)
    sub = decoded.get("sub")
    if not sub:
        raise UnauthorizedError("Token missing required 'sub' claim.")
    try:
        uuid.UUID(str(sub))
    except (ValueError, TypeError):
        raise UnauthorizedError("Invalid token subject: 'sub' must be a valid UUID.")

    # 5. Extract email and role
    email = decoded.get("email", "")
    role = decoded.get("role", "authenticated")

    return TokenPayload(
        sub=str(sub),
        email=email,
        exp=decoded["exp"],
        iat=decoded.get("iat"),
        role=role,
        raw_claims=decoded,
    )


# Alias for explicit naming
verify_supabase_jwt = decode_and_verify_token


def enforce_creator_separation(content_creator_id: str, approver_id: str) -> None:
    """
    Core security rule: A creator cannot approve content they submitted.
    Enforced server-side in API routes and backed up by database constraints.
    """
    if str(content_creator_id).strip() == str(approver_id).strip():
        raise CreatorSelfApprovalError()
