"""Agent Server Package.

This package provides the core server functionality for the Agent OpenAI Agents SDK.

Main Components:
- config: Configuration management with Pydantic Settings
- agent: Agent creation and management
- start_server: FastAPI application and server startup
- security: Authentication and rate limiting
- monitoring: Prometheus metrics and structured logging
- memory_store: Message storage backends
- utils: Utility functions and helpers
- client_contract: Client contract and capabilities

Usage:
    from agent_server.start_server import app
    from agent_server.config import get_config
    from agent_server.security import validate_auth_header
"""

from agent_server.config import get_config, config
from agent_server.security import (
    RATE_LIMITER,
    TOKEN_MANAGER,
    auth_required,
    validate_auth_header,
    extract_request_context,
    InputValidator,
)
from agent_server.monitoring import (
    logger,
    setup_monitoring,
    get_metrics,
    record_agent_invocation,
    record_retry_attempt,
    record_fallback,
    record_rate_limit,
    record_auth_failure,
    record_error,
)

__all__ = [
    # Configuration
    "get_config",
    "config",
    # Security
    "RATE_LIMITER",
    "TOKEN_MANAGER",
    "auth_required",
    "validate_auth_header",
    "extract_request_context",
    "InputValidator",
    # Monitoring
    "logger",
    "setup_monitoring",
    "get_metrics",
    "record_agent_invocation",
    "record_retry_attempt",
    "record_fallback",
    "record_rate_limit",
    "record_auth_failure",
    "record_error",
]

__version__ = "0.2.0"
