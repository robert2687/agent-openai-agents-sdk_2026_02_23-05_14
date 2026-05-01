from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RequestContext:
    user_id: str
    tenant_id: str


class InMemoryRateLimiter:
    """Simple per-user sliding-window limiter.

    This is a local development implementation and should be replaced with
    Redis or another shared backend for multi-instance deployments.
    """

    def __init__(self, max_requests_per_minute: int) -> None:
        self._max = max(1, max_requests_per_minute)
        self._bucket: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - 60.0

        with self._lock:
            q = self._bucket.setdefault(key, deque())
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self._max:
                return False

            q.append(now)
            return True


def auth_required() -> bool:
    return os.getenv("AGENT_REQUIRE_AUTH", "0") == "1"


def validate_auth_header(authorization_header: str | None) -> bool:
    """Basic token auth placeholder.

    Expected format: Authorization: Bearer <token>
    """
    expected = os.getenv("AGENT_API_TOKEN", "").strip()
    if not auth_required():
        return True

    if not expected:
        return False

    if not authorization_header:
        return False

    prefix = "Bearer "
    if not authorization_header.startswith(prefix):
        return False

    token = authorization_header[len(prefix) :].strip()
    return token == expected


def extract_request_context(headers: dict[str, str]) -> RequestContext:
    user_id = headers.get("x-user-id", "anonymous")
    tenant_id = headers.get("x-tenant-id", "default")
    return RequestContext(user_id=user_id, tenant_id=tenant_id)


def write_action_allowed(confirm_header: str | None) -> bool:
    """Write policy gate for future write actions.

    Clients should send X-Write-Confirm: true before any write operation.
    """
    return (confirm_header or "").strip().lower() == "true"
