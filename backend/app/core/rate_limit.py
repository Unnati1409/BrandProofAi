"""
BrandProof AI — API Rate Limiting Infrastructure.
Provides sliding-window in-memory rate limiting across IP, User, and Workspace scopes.
Configured with standard BrandProof governance limits:
- AI review execution: 5 requests/minute/workspace
- File uploads: 20 requests/minute/user
- Invitations: 10 requests/minute/workspace
- General API: 120 requests/minute/IP
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Literal

from fastapi import Request

from app.core.errors import RateLimitExceededError
from app.core.security import decode_and_verify_token


class InMemoryRateLimiter:
    """
    Thread-safe, sliding-window in-memory rate limiter.
    Maintains a ring buffer of timestamps for each unique key.

    Multi-instance note:
    This in-memory implementation is self-contained and suitable for single-instance
    staging and development. In a multi-replica horizontally scaled production deployment,
    this limiter can be backed by a centralized Redis cluster without altering the
    FastAPI dependency signatures.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        """
        Records an access attempt under `key`.
        Raises `RateLimitExceededError` with computed `Retry-After` seconds
        if the threshold is exceeded within the current sliding window.
        """
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._buckets[key]

            # Prune timestamps outside the active sliding window
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                raise RateLimitExceededError(
                    message=f"Rate limit exceeded: maximum {max_requests} requests allowed per {window_seconds}s.",
                    retry_after=retry_after,
                    details=[
                        {
                            "key_scope": key.split(":")[1] if ":" in key else "general",
                            "limit": max_requests,
                            "window_seconds": window_seconds,
                            "retry_after": retry_after,
                        }
                    ],
                )

            timestamps.append(now)

    def reset(self) -> None:
        """Clears all rate limit buckets. Used primarily for test teardown."""
        with self._lock:
            self._buckets.clear()


# Global singleton rate limiter
rate_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    """Extracts client IP from X-Forwarded-For (if behind trusted proxy) or socket client."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def rate_limit(
    max_requests: int,
    window_seconds: int = 60,
    scope: Literal["ip", "user", "workspace"] = "ip",
    endpoint_name: str = "default",
) -> Callable:
    """
    FastAPI Dependency returning a callable that enforces rate limits for the requested scope:
    - 'workspace': Scoped to the active workspace ID. Different workspaces never share buckets.
    - 'user': Scoped to the authenticated JWT subject (or falls back to IP).
    - 'ip': Scoped to client IP address.
    """

    async def rate_limit_dependency(request: Request) -> None:
        if scope == "workspace":
            ws_id = request.path_params.get("workspace_id") or request.headers.get("X-Workspace-ID")
            key = f"rl:workspace:{ws_id or 'unknown'}:{endpoint_name}"
        elif scope == "user":
            user_id = None
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                try:
                    payload = decode_and_verify_token(token)
                    user_id = str(payload.sub)
                except Exception:
                    pass
            key = f"rl:user:{user_id or get_client_ip(request)}:{endpoint_name}"
        else:
            key = f"rl:ip:{get_client_ip(request)}:{endpoint_name}"

        rate_limiter.check_rate_limit(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

    return rate_limit_dependency
