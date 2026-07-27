"""Enhanced security module with improved authentication and rate limiting.

This module provides:
- Token-based authentication with rotation support
- Distributed rate limiting (in-memory or Redis)
- Request context extraction
- Input validation utilities
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from agent_server.config import get_config


@dataclass
class RequestContext:
    """Request context for audit and rate limiting."""

    user_id: str
    tenant_id: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_ip: str | None = None
    user_agent: str | None = None


class TokenManager:
    """Token management with rotation and expiry support.

    Provides secure token validation with optional expiry and rotation.
    """

    def __init__(self) -> None:
        self._valid_tokens: set[str] = set()
        self._token_expiry: dict[str, float] = {}
        self._token_metadata: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def add_token(
        self,
        token: str,
        expiry_hours: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a valid token with optional expiry and metadata."""
        with self._lock:
            # Store hashed version for security
            hashed = self._hash_token(token)
            self._valid_tokens.add(hashed)

            if expiry_hours is not None:
                self._token_expiry[hashed] = time.time() + (expiry_hours * 3600)

            if metadata:
                self._token_metadata[hashed] = metadata

    def remove_token(self, token: str) -> bool:
        """Remove a token. Returns True if token was valid."""
        with self._lock:
            hashed = self._hash_token(token)
            was_valid = hashed in self._valid_tokens
            self._valid_tokens.discard(hashed)
            self._token_expiry.pop(hashed, None)
            self._token_metadata.pop(hashed, None)
            return was_valid

    def validate(self, token: str) -> bool:
        """Validate a token, checking expiry if applicable."""
        with self._lock:
            hashed = self._hash_token(token)
            if hashed not in self._valid_tokens:
                return False

            # Check expiry
            expiry = self._token_expiry.get(hashed)
            if expiry is not None and time.time() > expiry:
                self._valid_tokens.discard(hashed)
                self._token_expiry.pop(hashed, None)
                self._token_metadata.pop(hashed, None)
                return False

            return True

    def get_metadata(self, token: str) -> dict[str, Any] | None:
        """Get metadata for a valid token."""
        with self._lock:
            hashed = self._hash_token(token)
            if hashed in self._valid_tokens:
                return self._token_metadata.get(hashed)
            return None

    def rotate_token(self, old_token: str, new_token: str) -> bool:
        """Rotate a token. Returns True if old token was valid."""
        with self._lock:
            old_hashed = self._hash_token(old_token)
            new_hashed = self._hash_token(new_token)

            if old_hashed not in self._valid_tokens:
                return False

            # Transfer expiry and metadata to new token
            expiry = self._token_expiry.pop(old_hashed, None)
            metadata = self._token_metadata.pop(old_hashed, None)

            self._valid_tokens.discard(old_hashed)
            self._valid_tokens.add(new_hashed)

            if expiry is not None:
                self._token_expiry[new_hashed] = expiry
            if metadata:
                self._token_metadata[new_hashed] = metadata

            return True

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()


class BaseRateLimiter:
    """Abstract base class for rate limiters."""

    def allow(self, key: str) -> bool:
        """Check if request is allowed. Must be implemented by subclasses."""
        raise NotImplementedError

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for key. Must be implemented by subclasses."""
        raise NotImplementedError

    def reset(self, key: str) -> None:
        """Reset rate limit for key. Must be implemented by subclasses."""
        raise NotImplementedError


class InMemoryRateLimiter(BaseRateLimiter):
    """Simple per-user sliding-window limiter.

    This is a local development implementation and should be replaced with
    Redis or another shared backend for multi-instance deployments.
    """

    def __init__(self, max_requests_per_minute: int) -> None:
        self._max = max(1, max_requests_per_minute)
        self._bucket: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Check if request is allowed using sliding window algorithm."""
        now = time.time()
        cutoff = now - 60.0

        with self._lock:
            q = self._bucket.setdefault(key, deque())
            # Remove expired timestamps
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self._max:
                return False

            q.append(now)
            return True

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for key."""
        now = time.time()
        cutoff = now - 60.0

        with self._lock:
            q = self._bucket.get(key, deque())
            # Remove expired timestamps
            while q and q[0] < cutoff:
                q.popleft()
            return max(0, self._max - len(q))

    def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        with self._lock:
            self._bucket.pop(key, None)


class RedisRateLimiter(BaseRateLimiter):
    """Distributed rate limiter using Redis.

    Uses Redis sorted sets for efficient sliding window rate limiting.
    Requires redis package: pip install redis
    """

    def __init__(self, redis_client: Any, max_requests_per_minute: int) -> None:
        self._redis = redis_client
        self._max = max(1, max_requests_per_minute)
        self._window = 60.0

    def allow(self, key: str) -> bool:
        """Check if request is allowed using Redis sorted sets."""
        now = time.time()
        cutoff = now - self._window

        # Use pipeline for atomic operations
        pipe = self._redis.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, cutoff)

        # Add current timestamp
        pipe.zadd(key, {str(now): now})

        # Count current entries
        pipe.zcard(key)

        # Set expiry on key (window + 1 second)
        pipe.expire(key, int(self._window) + 1)

        _, _, count, _ = pipe.execute()
        return count <= self._max

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for key."""
        now = time.time()
        cutoff = now - self._window

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zcard(key)
        _, count = pipe.execute()

        return max(0, self._max - count)

    def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        self._redis.delete(key)


def create_rate_limiter() -> BaseRateLimiter:
    """Factory function to create appropriate rate limiter."""
    config = get_config()

    # Try Redis first if configured
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis.asyncio as redis

            redis_client = redis.from_url(redis_url, decode_responses=True)
            return RedisRateLimiter(redis_client, config.rate_limit_per_minute)
        except ImportError:
            pass

    # Fall back to in-memory
    return InMemoryRateLimiter(config.rate_limit_per_minute)


# Global instances
RATE_LIMITER = create_rate_limiter()
TOKEN_MANAGER = TokenManager()


def auth_required() -> bool:
    """Check if authentication is required."""
    return get_config().require_auth


def validate_auth_header(authorization_header: str | None) -> bool:
    """Validate Authorization header.

    Expected format: Authorization: Bearer <token>
    Supports both configured API token and token manager.
    """
    config = get_config()

    if not auth_required():
        return True

    # Check if using token manager
    if TOKEN_MANAGER._valid_tokens:
        if not authorization_header:
            return False

        prefix = "Bearer "
        if not authorization_header.startswith(prefix):
            return False

        token = authorization_header[len(prefix) :].strip()
        return TOKEN_MANAGER.validate(token)

    # Fall back to configured API token
    expected = config.api_token
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
    """Extract request context from headers."""
    user_id = headers.get("x-user-id", "anonymous")
    tenant_id = headers.get("x-tenant-id", "default")
    client_ip = headers.get("x-forwarded-for", headers.get("x-real-ip"))
    user_agent = headers.get("user-agent")

    return RequestContext(
        user_id=user_id,
        tenant_id=tenant_id,
        client_ip=client_ip,
        user_agent=user_agent,
    )


def write_action_allowed(confirm_header: str | None) -> bool:
    """Write policy gate for future write actions.

    Clients should send X-Write-Confirm: true before any write operation.
    """
    return (confirm_header or "").strip().lower() == "true"


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


# Input validation utilities
class InputValidator:
    """Utilities for input validation."""

    MAX_INPUT_LENGTH = 100000  # 100KB max input size
    MAX_MESSAGE_COUNT = 100  # Max messages in a conversation
    MAX_TOKENS_PER_MESSAGE = 32768

    @classmethod
    def validate_messages(cls, messages: list[dict]) -> tuple[bool, str]:
        """Validate messages list.

        Returns (is_valid, error_message)
        """
        if not isinstance(messages, list):
            return False, "Input must be a list of messages"

        if len(messages) > cls.MAX_MESSAGE_COUNT:
            return False, f"Maximum {cls.MAX_MESSAGE_COUNT} messages allowed"

        if len(messages) == 0:
            return False, "At least one message is required"

        # Check each message
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                return False, f"Message {i} must be a dictionary"

            if "role" not in msg:
                return False, f"Message {i} missing 'role' field"

            if "content" not in msg:
                return False, f"Message {i} missing 'content' field"

            role = msg.get("role")
            if role not in {"system", "user", "assistant", "tool"}:
                return False, f"Message {i} has invalid role: {role}"

            content = msg.get("content")
            if isinstance(content, str):
                if len(content) > cls.MAX_INPUT_LENGTH:
                    return False, f"Message {i} content exceeds maximum length"
            elif isinstance(content, list):
                for j, part in enumerate(content):
                    if isinstance(part, dict) and "text" in part:
                        if len(part["text"]) > cls.MAX_INPUT_LENGTH:
                            return False, f"Message {i} part {j} exceeds maximum length"

        return True, ""

    @classmethod
    def validate_model(cls, model: str) -> tuple[bool, str]:
        """Validate model name."""
        if not model or not isinstance(model, str):
            return False, "Model must be a non-empty string"

        if len(model) > 200:
            return False, "Model name too long"

        # Basic sanity check
        if not all(c.isalnum() or c in {"-", ".", ":", "_", "/"} for c in model):
            return False, "Model name contains invalid characters"

        return True, ""


# Initialize token manager with configured token
_config = get_config()
if _config.api_token:
    TOKEN_MANAGER.add_token(_config.api_token)
