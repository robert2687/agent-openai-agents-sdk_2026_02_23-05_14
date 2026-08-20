"""Monitoring and observability module.

Provides Prometheus metrics, structured logging, and request tracing.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Any

from fastapi import Request
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    REGISTRY,
)
from prometheus_client.openmetrics.exporter import CONTENT_TYPE_LATEST
from starlette.responses import Response

from agent_server.config import get_config


# Context variable for request ID
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


# ============================================================================
# Metrics Definitions
# ============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    "agent_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status_code", "backend"],
)

REQUEST_DURATION = Histogram(
    "agent_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint", "backend"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_SIZE = Histogram(
    "agent_request_size_bytes",
    "Request size in bytes",
    ["endpoint"],
    buckets=[100, 1000, 10000, 100000, 1000000],
)

RESPONSE_SIZE = Histogram(
    "agent_response_size_bytes",
    "Response size in bytes",
    ["endpoint"],
    buckets=[100, 1000, 10000, 100000, 1000000],
)

# Agent metrics
AGENT_INVOCATIONS = Counter(
    "agent_invocations_total",
    "Total agent invocations",
    ["model", "streaming", "status"],
)

AGENT_TOKENS = Counter(
    "agent_tokens_total",
    "Total tokens processed",
    ["model", "token_type"],  # token_type: input, output
)

AGENT_DURATION = Histogram(
    "agent_processing_duration_seconds",
    "Agent processing duration",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# Retry metrics
RETRY_ATTEMPTS = Counter(
    "agent_retry_attempts_total",
    "Total retry attempts",
    ["model", "attempt_number"],
)

FALLBACK_INVOCATIONS = Counter(
    "agent_fallback_invocations_total",
    "Total fallback model invocations",
    ["from_model", "to_model"],
)

# Error metrics
ERROR_COUNT = Counter(
    "agent_errors_total",
    "Total errors",
    ["error_type", "endpoint"],
)

# Rate limiting metrics
RATE_LIMITED_REQUESTS = Counter(
    "agent_rate_limited_requests_total",
    "Total rate-limited requests",
    ["user_id", "tenant_id"],
)

AUTH_FAILED_REQUESTS = Counter(
    "agent_auth_failed_requests_total",
    "Total authentication failed requests",
)

# Active connections
ACTIVE_CONNECTIONS = Gauge(
    "agent_active_connections",
    "Number of active connections",
)

# Memory metrics
MEMORY_MESSAGES = Gauge(
    "agent_memory_messages_total",
    "Total messages stored in memory",
    ["tenant_id", "user_id"],
)


# ============================================================================
# Structured Logging
# ============================================================================

class StructuredLogger:
    """Structured logger with context support."""

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: dict[str, Any] = {}

    def bind(self, **kwargs: Any) -> "StructuredLogger":
        """Add context to logger."""
        new_logger = StructuredLogger(self._logger.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _format_message(self, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Format log message with context."""
        log_data = {
            "timestamp": time.time(),
            "level": self._logger.level,
            "logger": self._logger.name,
            "message": message,
            **self._context,
        }
        if extra:
            log_data.update(extra)
        return log_data

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(message, extra=self._format_message(message, kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(message, extra=self._format_message(message, kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(message, extra=self._format_message(message, kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(message, extra=self._format_message(message, kwargs))

    def exception(self, message: str, **kwargs: Any) -> None:
        self._logger.exception(message, extra=self._format_message(message, kwargs))


# Create module-level logger
logger = StructuredLogger("agent_server")


# ============================================================================
# Middleware
# ============================================================================

async def monitoring_middleware(request: Request, call_next):
    """FastAPI middleware for monitoring requests."""
    config = get_config()

    # Skip monitoring if disabled
    if not config.enable_prometheus:
        return await call_next(request)

    # Extract request info
    method = request.method
    path = request.url.path
    backend = config.backend

    # Generate request ID
    request_id = request.headers.get("x-request-id", str(time.time()).replace(".", ""))
    request_id_var.set(request_id)

    # Track active connections
    ACTIVE_CONNECTIONS.inc()

    # Measure request size
    request_size = len(await request.body())

    # Process request
    start_time = time.time()
    status_code = 500  # Default, will be updated

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        ERROR_COUNT.labels(error_type=type(e).__name__, endpoint=path).inc()
        raise
    finally:
        # Record metrics
        duration = time.time() - start_time

        REQUEST_COUNT.labels(
            method=method,
            endpoint=path,
            status_code=str(status_code),
            backend=backend,
        ).inc()

        REQUEST_DURATION.labels(
            method=method,
            endpoint=path,
            backend=backend,
        ).observe(duration)

        REQUEST_SIZE.labels(endpoint=path).observe(request_size)

        # Track active connections
        ACTIVE_CONNECTIONS.dec()

        # Clean up request ID
        request_id_var.set(None)


async def get_metrics() -> str:
    """Get Prometheus metrics."""
    return generate_latest(REGISTRY)


# ============================================================================
# Helper Functions
# ============================================================================

def get_request_id() -> str | None:
    """Get current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set request ID in context."""
    request_id_var.set(request_id)


def record_agent_invocation(
    model: str,
    streaming: bool = False,
    status: str = "success",
    duration: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    """Record agent invocation metrics."""
    config = get_config()
    if not config.enable_prometheus:
        return

    AGENT_INVOCATIONS.labels(model=model, streaming=str(streaming), status=status).inc()

    if duration is not None:
        AGENT_DURATION.labels(model=model).observe(duration)

    if input_tokens is not None:
        AGENT_TOKENS.labels(model=model, token_type="input").inc(input_tokens)

    if output_tokens is not None:
        AGENT_TOKENS.labels(model=model, token_type="output").inc(output_tokens)


def record_retry_attempt(model: str, attempt_number: int) -> None:
    """Record retry attempt."""
    config = get_config()
    if not config.enable_prometheus:
        return

    RETRY_ATTEMPTS.labels(model=model, attempt_number=str(attempt_number)).inc()


def record_fallback(from_model: str, to_model: str) -> None:
    """Record fallback to another model."""
    config = get_config()
    if not config.enable_prometheus:
        return

    FALLBACK_INVOCATIONS.labels(from_model=from_model, to_model=to_model).inc()


def record_rate_limit(user_id: str, tenant_id: str) -> None:
    """Record rate limited request."""
    config = get_config()
    if not config.enable_prometheus:
        return

    RATE_LIMITED_REQUESTS.labels(user_id=user_id, tenant_id=tenant_id).inc()


def record_auth_failure() -> None:
    """Record authentication failure."""
    config = get_config()
    if not config.enable_prometheus:
        return

    AUTH_FAILED_REQUESTS.inc()


def record_error(error_type: str, endpoint: str) -> None:
    """Record error."""
    config = get_config()
    if not config.enable_prometheus:
        return

    ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()


# ============================================================================
# Setup Functions
# ============================================================================

def setup_logging(level: int = logging.INFO) -> None:
    """Setup structured logging."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler()],
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("mlflow").setLevel(logging.WARNING)


def setup_monitoring() -> None:
    """Setup monitoring and metrics."""
    config = get_config()

    if config.enable_prometheus:
        setup_logging()
        logger.info("Prometheus metrics enabled")
    else:
        logger.info("Prometheus metrics disabled")
