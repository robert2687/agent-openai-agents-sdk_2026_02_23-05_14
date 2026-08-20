"""Tests for security module."""

import os
import time

import pytest

from agent_server.security import (
    InMemoryRateLimiter,
    RequestContext,
    TokenManager,
    InputValidator,
    auth_required,
    validate_auth_header,
    extract_request_context,
    write_action_allowed,
)


class TestTokenManager:
    """Tests for TokenManager class."""

    def test_add_and_validate_token(self):
        """Test adding and validating tokens."""
        manager = TokenManager()
        token = "test-token-123"

        manager.add_token(token)
        assert manager.validate(token) is True

    def test_validate_invalid_token(self):
        """Test validating invalid token."""
        manager = TokenManager()
        assert manager.validate("invalid-token") is False

    def test_token_with_expiry(self):
        """Test token with expiry."""
        manager = TokenManager()
        token = "expiring-token"

        manager.add_token(token, expiry_hours=1)
        assert manager.validate(token) is True

        # Wait for expiry (simulate by setting expiry in the past)
        manager._token_expiry[manager._hash_token(token)] = time.time() - 1
        assert manager.validate(token) is False

    def test_remove_token(self):
        """Test removing token."""
        manager = TokenManager()
        token = "removable-token"

        manager.add_token(token)
        assert manager.validate(token) is True

        result = manager.remove_token(token)
        assert result is True
        assert manager.validate(token) is False

    def test_remove_nonexistent_token(self):
        """Test removing nonexistent token."""
        manager = TokenManager()
        result = manager.remove_token("nonexistent")
        assert result is False

    def test_rotate_token(self):
        """Test token rotation."""
        manager = TokenManager()
        old_token = "old-token"
        new_token = "new-token"

        manager.add_token(old_token, expiry_hours=1, metadata={"role": "admin"})
        assert manager.validate(old_token) is True

        result = manager.rotate_token(old_token, new_token)
        assert result is True
        assert manager.validate(old_token) is False
        assert manager.validate(new_token) is True

        # Check metadata was transferred
        metadata = manager.get_metadata(new_token)
        assert metadata == {"role": "admin"}

    def test_rotate_nonexistent_token(self):
        """Test rotating nonexistent token."""
        manager = TokenManager()
        result = manager.rotate_token("nonexistent", "new-token")
        assert result is False

    def test_get_metadata(self):
        """Test getting token metadata."""
        manager = TokenManager()
        token = "metadata-token"
        metadata = {"user": "test", "role": "admin"}

        manager.add_token(token, metadata=metadata)
        result = manager.get_metadata(token)
        assert result == metadata

    def test_get_metadata_invalid_token(self):
        """Test getting metadata for invalid token."""
        manager = TokenManager()
        result = manager.get_metadata("invalid")
        assert result is None


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter class."""

    def test_allow_within_limit(self):
        """Test allowing requests within limit."""
        limiter = InMemoryRateLimiter(max_requests_per_minute=10)

        for _ in range(10):
            assert limiter.allow("user1") is True

    def test_deny_over_limit(self):
        """Test denying requests over limit."""
        limiter = InMemoryRateLimiter(max_requests_per_minute=5)

        for _ in range(5):
            assert limiter.allow("user1") is True

        # 6th request should be denied
        assert limiter.allow("user1") is False

    def test_different_users(self):
        """Test rate limiting for different users."""
        limiter = InMemoryRateLimiter(max_requests_per_minute=2)

        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is False

        # user2 should still be allowed
        assert limiter.allow("user2") is True
        assert limiter.allow("user2") is True
        assert limiter.allow("user2") is False

    def test_get_remaining(self):
        """Test getting remaining requests."""
        limiter = InMemoryRateLimiter(max_requests_per_minute=5)

        assert limiter.get_remaining("user1") == 5

        limiter.allow("user1")
        assert limiter.get_remaining("user1") == 4

        for _ in range(4):
            limiter.allow("user1")

        assert limiter.get_remaining("user1") == 0

    def test_reset(self):
        """Test resetting rate limit."""
        limiter = InMemoryRateLimiter(max_requests_per_minute=2)

        limiter.allow("user1")
        limiter.allow("user1")
        assert limiter.allow("user1") is False

        limiter.reset("user1")
        assert limiter.allow("user1") is True

    def test_sliding_window(self):
        """Test sliding window behavior."""
        limiter = InMemoryRateLimiter(max_requests_per_minute=3)

        # Use all requests
        for _ in range(3):
            assert limiter.allow("user1") is True

        assert limiter.allow("user1") is False

        # Simulate time passing (by directly manipulating the deque)
        # In real scenario, this would happen naturally over time
        limiter._bucket["user1"].clear()

        # Should be allowed again
        assert limiter.allow("user1") is True


class TestRequestContext:
    """Tests for RequestContext."""

    def test_extract_request_context(self):
        """Test extracting request context from headers."""
        headers = {
            "x-user-id": "test-user",
            "x-tenant-id": "test-tenant",
            "x-forwarded-for": "192.168.1.1",
            "user-agent": "Test Agent",
        }

        context = extract_request_context(headers)

        assert context.user_id == "test-user"
        assert context.tenant_id == "test-tenant"
        assert context.client_ip == "192.168.1.1"
        assert context.user_agent == "Test Agent"

    def test_extract_request_context_defaults(self):
        """Test extracting request context with defaults."""
        headers = {}

        context = extract_request_context(headers)

        assert context.user_id == "anonymous"
        assert context.tenant_id == "default"
        assert context.client_ip is None
        assert context.user_agent is None


class TestInputValidator:
    """Tests for InputValidator."""

    def test_validate_messages_valid(self):
        """Test validating valid messages."""
        messages = [
            {"role": "system", "content": "Hello"},
            {"role": "user", "content": "How are you?"},
        ]

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is True
        assert error == ""

    def test_validate_messages_empty(self):
        """Test validating empty messages."""
        messages = []

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is False
        assert "At least one message" in error

    def test_validate_messages_not_list(self):
        """Test validating non-list messages."""
        messages = "not a list"

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is False
        assert "must be a list" in error

    def test_validate_messages_missing_role(self):
        """Test validating messages with missing role."""
        messages = [{"content": "Hello"}]

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is False
        assert "missing 'role'" in error

    def test_validate_messages_missing_content(self):
        """Test validating messages with missing content."""
        messages = [{"role": "user"}]

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is False
        assert "missing 'content'" in error

    def test_validate_messages_invalid_role(self):
        """Test validating messages with invalid role."""
        messages = [{"role": "invalid", "content": "Hello"}]

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is False
        assert "invalid role" in error

    def test_validate_messages_too_many(self):
        """Test validating too many messages."""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(101)]

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is False
        assert "Maximum" in error

    def test_validate_messages_long_content(self):
        """Test validating messages with long content."""
        long_content = "x" * (InputValidator.MAX_INPUT_LENGTH + 1)
        messages = [{"role": "user", "content": long_content}]

        is_valid, error = InputValidator.validate_messages(messages)
        assert is_valid is False
        assert "exceeds maximum length" in error

    def test_validate_model_valid(self):
        """Test validating valid model."""
        is_valid, error = InputValidator.validate_model("gpt-4.1")
        assert is_valid is True
        assert error == ""

    def test_validate_model_empty(self):
        """Test validating empty model."""
        is_valid, error = InputValidator.validate_model("")
        assert is_valid is False
        assert "non-empty" in error

    def test_validate_model_too_long(self):
        """Test validating too long model name."""
        long_model = "x" * 201
        is_valid, error = InputValidator.validate_model(long_model)
        assert is_valid is False
        assert "too long" in error

    def test_validate_model_invalid_chars(self):
        """Test validating model with invalid characters."""
        is_valid, error = InputValidator.validate_model("model!@#")
        assert is_valid is False
        assert "invalid characters" in error


class TestAuthFunctions:
    """Tests for authentication functions."""

    def test_validate_auth_header_bearer(self):
        """Test validating Bearer token."""
        os.environ["AGENT_API_TOKEN"] = "test-token"
        os.environ["AGENT_REQUIRE_AUTH"] = "1"

        # Need to reload config
        from agent_server.config import reset_config
        reset_config()

        header = "Bearer test-token"
        assert validate_auth_header(header) is True

    def test_validate_auth_header_invalid(self):
        """Test validating invalid token."""
        os.environ["AGENT_API_TOKEN"] = "test-token"
        os.environ["AGENT_REQUIRE_AUTH"] = "1"

        from agent_server.config import reset_config
        reset_config()

        header = "Bearer wrong-token"
        assert validate_auth_header(header) is False

    def test_validate_auth_header_no_auth_required(self):
        """Test when auth is not required."""
        os.environ["AGENT_REQUIRE_AUTH"] = "0"

        from agent_server.config import reset_config
        reset_config()

        assert validate_auth_header(None) is True
        assert validate_auth_header("Bearer anything") is True

    def test_write_action_allowed(self):
        """Test write action confirmation."""
        assert write_action_allowed("true") is True
        assert write_action_allowed("True") is True
        assert write_action_allowed("TRUE") is True
        assert write_action_allowed("false") is False
        assert write_action_allowed(None) is False
        assert write_action_allowed("") is False
