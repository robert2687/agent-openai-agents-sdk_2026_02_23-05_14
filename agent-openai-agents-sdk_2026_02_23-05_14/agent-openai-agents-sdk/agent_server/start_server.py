"""Enhanced server startup with monitoring, error handling, and comprehensive middleware.

This module provides the main FastAPI application with:
- Request ID generation and tracking
- Enhanced error handling
- Monitoring and metrics
- Rate limiting
- Authentication
- Health checks
"""

import logging
import time
from contextlib import asynccontextmanager
import os

# Default to local SQLite-backed MLflow tracking to avoid deprecated file store.
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

from agent_server.config import get_config, reset_config
from agent_server.security import (
    RATE_LIMITER,
    TOKEN_MANAGER,
    auth_required,
    extract_request_context,
    validate_auth_header,
    InputValidator,
    generate_request_id,
)
from agent_server.monitoring import (
    monitoring_middleware,
    get_metrics,
    logger,
    setup_monitoring,
    set_request_id,
    get_request_id,
    record_auth_failure,
    record_rate_limit,
    record_error,
)
from agent_server.client_contract import build_client_contract

# Load env vars from .env before importing the agent for proper auth
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

# Need to import the agent to register the functions with the server
from agent_server import agent as agent_module  # noqa: E402

# Initialize monitoring
setup_monitoring()

# Create FastAPI app
app = FastAPI(
    title="Agent OpenAI Agents SDK",
    description="Multi-agent SDK with PERFECT-AGENT (Nemotron fallback)",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add monitoring middleware
app.middleware("http")(monitoring_middleware)

# Agent server setup
agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)

# Mount agent server routes
app.mount("/agent", agent_server.app)

LOGGER = logging.getLogger(__name__)


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Application lifespan manager."""
    config = get_config()

    # Setup MLflow git-based version tracking
    try:
        setup_mlflow_git_based_version_tracking()
    except Exception as _exc:  # pragma: no cover - optional Databricks feature
        LOGGER.warning("MLflow git-based version tracking unavailable (non-fatal): %s", _exc)

    # Initialize OpenAI client
    try:
        await agent_module._get_openai_client()
    except Exception as exc:
        LOGGER.warning("Failed to initialize OpenAI client: %s", exc)

    # Log startup information
    LOGGER.info(
        "Agent startup | backend=%s model=%s fallback_model=%s retries=%s base_retry_seconds=%s",
        agent_module.BACKEND,
        agent_module.MODEL,
        agent_module.FALLBACK_MODEL or "<none>",
        agent_module.MAX_RETRIES,
        agent_module.RETRY_BASE_SECONDS,
    )

    # Log configuration
    LOGGER.info(
        "Configuration | require_auth=%s rate_limit=%s max_tokens=%s",
        config.require_auth,
        config.rate_limit_per_minute,
        config.max_tokens,
    )

    yield

    # Cleanup on shutdown
    LOGGER.info("Agent shutdown initiated")


app.router.lifespan_context = _lifespan


# ============================================================================
# Request ID Middleware
# ============================================================================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add request ID to each request."""
    # Generate or use existing request ID
    request_id = request.headers.get("x-request-id", generate_request_id())
    set_request_id(request_id)

    # Process request
    response = await call_next(request)

    # Add request ID to response headers
    response.headers["x-request-id"] = request_id

    return response


# ============================================================================
# Error Handling Middleware
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for all unhandled exceptions."""
    request_id = get_request_id() or "unknown"
    config = get_config()

    # Log the error
    logger.exception(
        "Unhandled exception",
        request_id=request_id,
        path=str(request.url),
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )

    # Record metrics
    if config.enable_prometheus:
        record_error(error_type=type(exc).__name__, endpoint=str(request.url))

    # Return appropriate response
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
                "request_id": request_id,
            },
        )

    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail.get("error", "http_error"),
                "message": exc.detail.get("message", str(exc.detail)),
                "request_id": request_id,
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "request_id": request_id,
        },
    )


# ============================================================================
# Request Guardrails Middleware
# ============================================================================

@app.middleware("http")
async def request_guardrails(request: Request, call_next):
    """Middleware for authentication, rate limiting, and request validation."""
    started_at = time.perf_counter()
    context = extract_request_context(dict(request.headers))
    request_id = get_request_id() or generate_request_id()

    # Skip guardrails for health and metrics endpoints
    if request.url.path in {"/health", "/", "/metrics", "/favicon.ico", "/client-capabilities"}:
        response = await call_next(request)
        return response

    # Authentication check
    if not validate_auth_header(request.headers.get("authorization")):
        record_auth_failure()
        return JSONResponse(
            status_code=401,
            content={
                "error": "unauthorized",
                "message": "Missing or invalid Authorization token",
                "request_id": request_id,
            },
        )

    # Rate limiting check
    if not RATE_LIMITER.allow(context.user_id):
        record_rate_limit(context.user_id, context.tenant_id)
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Per-user request limit exceeded",
                "retry_after": 60,
                "request_id": request_id,
            },
        )

    # Process request
    response = await call_next(request)

    # Log request
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    LOGGER.info(
        "audit request | request_id=%s tenant=%s user=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        context.tenant_id,
        context.user_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    return response


# ============================================================================
# Health and Status Endpoints
# ============================================================================

@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    config = get_config()
    return {
        "status": "ok",
        "backend": agent_module.BACKEND,
        "openai_credentials_configured": agent_module.OPENAI_CREDENTIALS_CONFIGURED,
        "databricks_tools_enabled": agent_module.USE_DATABRICKS,
        "model": agent_module.MODEL,
        "fallback_model": agent_module.FALLBACK_MODEL or None,
        "max_retries": agent_module.MAX_RETRIES,
        "retry_base_seconds": agent_module.RETRY_BASE_SECONDS,
        "max_tokens": config.max_tokens,
        "rate_limit_per_minute": config.rate_limit_per_minute,
        "require_auth": config.require_auth,
        "memory_backend": config.memory_backend,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with service information."""
    return {
        "service": "agent-openai-agents-sdk",
        "status": "ok",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "invocations": "/invocations",
        "metrics": "/metrics",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Favicon endpoint."""
    return Response(status_code=204)


@app.get("/client-capabilities")
async def client_capabilities() -> dict:
    """Client capabilities endpoint."""
    config = get_config()
    contract = build_client_contract()
    contract["runtime"] = {
        "backend": agent_module.BACKEND,
        "model": agent_module.MODEL,
        "fallback_model": agent_module.FALLBACK_MODEL or None,
        "max_retries": agent_module.MAX_RETRIES,
        "max_tokens": config.max_tokens,
        "rate_limit_per_minute": config.rate_limit_per_minute,
    }
    return contract


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    config = get_config()
    if not config.enable_prometheus:
        return Response(
            status_code=404,
            content={"error": "Prometheus metrics disabled"},
        )

    metrics_data = await get_metrics()
    return Response(
        content=metrics_data,
        media_type="text/plain",
    )


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get("/config")
async def get_configuration() -> dict:
    """Get current configuration (non-sensitive values only)."""
    config = get_config()
    return {
        "backend": config.backend,
        "model": config.model,
        "fallback_model": config.fallback_model,
        "max_retries": config.max_retries,
        "retry_base_seconds": config.retry_base_seconds,
        "max_tokens": config.max_tokens,
        "require_auth": config.require_auth,
        "rate_limit_per_minute": config.rate_limit_per_minute,
        "memory_backend": config.memory_backend,
        "enable_prometheus": config.enable_prometheus,
        "app_name": config.app_name,
    }


@app.post("/config/reload")
async def reload_configuration() -> dict:
    """Reload configuration from environment variables."""
    reset_config()
    return {
        "status": "ok",
        "message": "Configuration reloaded",
    }


# ============================================================================
# Token Management Endpoints
# ============================================================================

@app.post("/tokens")
async def create_token(
    request: Request,
    expiry_hours: int | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create a new API token (admin only)."""
    # In production, add proper authentication for this endpoint
    import secrets

    token = secrets.token_urlsafe(32)
    TOKEN_MANAGER.add_token(token, expiry_hours=expiry_hours, metadata=metadata)

    return {
        "status": "ok",
        "token": token,  # In production, only return token once
        "expires_in": expiry_hours * 3600 if expiry_hours else None,
    }


@app.delete("/tokens/{token}")
async def revoke_token(token: str) -> dict:
    """Revoke an API token (admin only)."""
    success = TOKEN_MANAGER.remove_token(token)
    return {
        "status": "ok" if success else "not_found",
        "message": "Token revoked" if success else "Token not found",
    }


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the server."""
    agent_server.run(app_import_string="agent_server.start_server:app")


if __name__ == "__main__":
    main()
