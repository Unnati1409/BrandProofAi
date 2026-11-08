"""
Unit and API integration tests for BrandProof AI rate limiting infrastructure.
Verifies sliding-window in-memory rate limiting across IP, User, and Workspace scopes.
"""

import uuid

import pytest
from starlette.testclient import TestClient

from app.core.errors import RateLimitExceededError
from app.core.rate_limit import InMemoryRateLimiter, rate_limiter
from app.main import app
from tests.security.jwt_test_helpers import DEFAULT_TEST_SECRET
from tests.security.test_rbac_authorization import create_user_in_postgres


@pytest.fixture(autouse=True)
def clean_rate_limits(monkeypatch):
    """Resets rate limit buckets and sets up JWT test secret before each test."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", DEFAULT_TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_URL", None)

    rate_limiter.reset()
    yield
    rate_limiter.reset()


def test_in_memory_limiter_allows_under_threshold():
    """Requests below configured max threshold succeed without raising exceptions."""
    limiter = InMemoryRateLimiter()
    key = "test:user:123"

    # Limit of 5 requests per 60s
    for _ in range(5):
        limiter.check_rate_limit(key, max_requests=5, window_seconds=60)


def test_in_memory_limiter_blocks_on_threshold_exceeded():
    """Requests exceeding configured max threshold raise RateLimitExceededError with retry_after."""
    limiter = InMemoryRateLimiter()
    key = "test:ws:abc"

    for _ in range(3):
        limiter.check_rate_limit(key, max_requests=3, window_seconds=60)

    # 4th request must be rejected
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check_rate_limit(key, max_requests=3, window_seconds=60)

    err = exc_info.value
    assert err.status_code == 429
    assert err.code == "RATE_LIMIT_EXCEEDED"
    assert err.retry_after >= 1
    assert "maximum 3 requests" in err.message


def test_workspace_isolation_in_rate_limits():
    """Exhausting rate limit in Workspace Alpha does not affect Workspace Beta."""
    limiter = InMemoryRateLimiter()
    ws_alpha = "ws_alpha_1"
    ws_beta = "ws_beta_2"

    # Exhaust limit for alpha
    for _ in range(5):
        limiter.check_rate_limit(
            f"rl:workspace:{ws_alpha}:invites", max_requests=5, window_seconds=60
        )

    with pytest.raises(RateLimitExceededError):
        limiter.check_rate_limit(
            f"rl:workspace:{ws_alpha}:invites", max_requests=5, window_seconds=60
        )

    # Beta should still be completely unthrottled
    for _ in range(5):
        limiter.check_rate_limit(
            f"rl:workspace:{ws_beta}:invites", max_requests=5, window_seconds=60
        )


def test_user_isolation_in_rate_limits():
    """Exhausting user rate limit for User 1 does not throttle User 2."""
    limiter = InMemoryRateLimiter()
    user_1 = "user_uuid_1"
    user_2 = "user_uuid_2"

    # Exhaust limit for user 1
    for _ in range(20):
        limiter.check_rate_limit(f"rl:user:{user_1}:uploads", max_requests=20, window_seconds=60)

    with pytest.raises(RateLimitExceededError):
        limiter.check_rate_limit(f"rl:user:{user_1}:uploads", max_requests=20, window_seconds=60)

    # User 2 must still succeed
    limiter.check_rate_limit(f"rl:user:{user_2}:uploads", max_requests=20, window_seconds=60)


def test_api_invitation_rate_limit_exceeded_returns_429_with_headers():
    """
    Integration test: Sending >10 invitation requests in a single workspace triggers
    HTTP 429 with Retry-After header and typed error envelope.
    """
    client = TestClient(app)

    # Setup Workspace with Admin
    admin_id = str(uuid.uuid4())
    admin_token = create_user_in_postgres(admin_id, f"admin_{admin_id[:8]}@limiter.demo", "Admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Rate Limit Workspace", "slug": f"ws-{admin_id[:8]}"},
        headers=admin_headers,
    )
    ws_id = ws_res.json()["id"]

    # 10 invitations succeed (workspace limit is 10/min)
    for i in range(10):
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/members/invite",
            json={"email": f"member_{i}_{admin_id[:8]}@limiter.demo", "roles": ["creator"]},
            headers=admin_headers,
        )
        assert res.status_code == 201

    # 11th invitation in same workspace exceeds limit -> 429
    res_blocked = client.post(
        f"/api/v1/workspaces/{ws_id}/members/invite",
        json={"email": f"overflow_{admin_id[:8]}@limiter.demo", "roles": ["creator"]},
        headers=admin_headers,
    )
    assert res_blocked.status_code == 429
    assert res_blocked.headers.get("Retry-After") is not None
    assert int(res_blocked.headers.get("Retry-After")) >= 1

    body = res_blocked.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "maximum 10 requests allowed" in body["error"]["message"]
    assert "retry_after" in body["error"]["details"][0]
