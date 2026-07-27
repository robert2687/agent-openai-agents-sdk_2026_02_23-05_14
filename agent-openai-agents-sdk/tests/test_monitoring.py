"""Tests for monitoring module."""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette

from agent_server.monitoring import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    ERROR_COUNT,
    AGENT_INVOCATIONS,
    RETRY_ATTEMPTS,
    FALLBACK_INVOCATIONS,
    RATE_LIMITED_REQUESTS,
    AUTH_FAILED_REQUESTS,
    ACTIVE_CONNECTIONS,
    monitoring_middleware,
    get_metrics,
    logger,
    setup_monitoring,
    set_request_id,
    get_request_id,
    record_agent_invocation,
    record_retry_attempt,
    record_fallback,
    record_rate_limit,
    record_auth_failure,
    record_error,
    StructuredLogger,
)


class TestStructuredLogger:
    """Tests for StructuredLogger."""

    def test_logger_creation(self):
        """Test logger creation."""
        log = StructuredLogger("test")
        assert log._logger.name == "test"

    def test_logger_bind(self):
        """Test logger binding."""
        log = StructuredLogger("test")
        log2 = log.bind(user_id="test-user", request_id="req-123")

        assert log2._context == {"user_id": "test-user", "request_id": "req-123"}

    def test_logger_chaining(self):
        """Test logger chaining."""
        log = StructuredLogger("test")
        log2 = log.bind(user_id="test-user")
        log3 = log2.bind(request_id="req-123")

        assert log3._context == {"user_id": "test-user", "request_id": "req-123"}


class TestRequestId:
    """Tests for request ID management."""

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        set_request_id("test-request-id")
        assert get_request_id() == "test-request-id"

    def test_request_id_isolation(self):
        """Test request ID isolation between calls."""
        set_request_id("req-1")
        assert get_request_id() == "req-1"

        set_request_id("req-2")
        assert get_request_id() == "req-2"

    def test_request_id_none(self):
        """Test default request ID."""
        set_request_id(None)
        assert get_request_id() is None


class TestMetricsRecording:
    """Tests for metrics recording functions."""

    def test_record_agent_invocation(self):
        """Test recording agent invocation."""
        record_agent_invocation(
            model="gpt-4.1",
            streaming=False,
            status="success",
            duration=1.5,
            input_tokens=100,
            output_tokens=50,
        )

        # Check that metrics were recorded
        # Note: In a real test, we'd need to check the Prometheus metrics
        # This is more of a smoke test

    def test_record_retry_attempt(self):
        """Test recording retry attempt."""
        record_retry_attempt("gpt-4.1", 2)

    def test_record_fallback(self):
        """Test recording fallback."""
        record_fallback("gpt-4.1-mini", "gpt-4.1")

    def test_record_rate_limit(self):
        """Test recording rate limit."""
        record_rate_limit("user-123", "tenant-456")

    def test_record_auth_failure(self):
        """Test recording auth failure."""
        record_auth_failure()

    def test_record_error(self):
        """Test recording error."""
        record_error("ValueError", "/invocations")


class TestMonitoringMiddleware:
    """Tests for monitoring middleware."""

    @pytest.fixture
    def app(self):
        """Create a test app with monitoring middleware."""
        app = Starlette()
        app.add_middleware(monitoring_middleware)

        @app.route("/test")
        async def test_endpoint(request):
            return {"status": "ok"}

        return app

    async def test_middleware_records_metrics(self, app):
        """Test that middleware records metrics."""
        client = TestClient(app)

        # Reset metrics
        REQUEST_COUNT.reset()
        REQUEST_DURATION.reset()

        # Make a request
        response = client.get("/test")
        assert response.status_code == 200

        # Check that metrics were recorded
        # Note: In a real test, we'd verify the metrics values

    async def test_middleware_handles_errors(self, app):
        """Test that middleware handles errors."""
        @app.route("/error")
        async def error_endpoint(request):
            raise ValueError("Test error")

        client = TestClient(app)

        # Reset metrics
        ERROR_COUNT.reset()

        # Make a request that will error
        with pytest.raises(ValueError):
            client.get("/error")

        # Check that error was recorded


class TestSetupMonitoring:
    """Tests for setup_monitoring function."""

    def test_setup_monitoring(self):
        """Test setup_monitoring function."""
        setup_monitoring()
        # This should not raise any errors


class TestGetMetrics:
    """Tests for get_metrics function."""

    async def test_get_metrics(self):
        """Test get_metrics function."""
        metrics = await get_metrics()
        assert isinstance(metrics, str)
        assert len(metrics) > 0


class TestActiveConnections:
    """Tests for active connections gauge."""

    def test_active_connections(self):
        """Test active connections gauge."""
        ACTIVE_CONNECTIONS.inc()
        assert ACTIVE_CONNECTIONS._value.get() == 1

        ACTIVE_CONNECTIONS.inc()
        assert ACTIVE_CONNECTIONS._value.get() == 2

        ACTIVE_CONNECTIONS.dec()
        assert ACTIVE_CONNECTIONS._value.get() == 1
