import logging
from contextlib import asynccontextmanager
import os
import time

# Default to local SQLite-backed MLflow tracking to avoid deprecated file store.
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking
from agent_server.client_contract import build_client_contract
from agent_server.security import (
    InMemoryRateLimiter,
    extract_request_context,
    validate_auth_header,
)

# Load env vars from .env before importing the agent for proper auth
load_dotenv(dotenv_path=".env", override=True)

# Need to import the agent to register the functions with the server
from agent_server import agent as agent_module  # noqa: E402

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)
# Define the app as a module level variable to enable multiple workers
app = agent_server.app  # noqa: F841

LOGGER = logging.getLogger(__name__)
RATE_LIMITER = InMemoryRateLimiter(int(os.getenv("AGENT_RATE_LIMIT_PER_MINUTE", "120")))


@asynccontextmanager
async def _lifespan(_app):
    try:
        setup_mlflow_git_based_version_tracking()
    except Exception as _exc:  # pragma: no cover - optional Databricks feature
        LOGGER.warning("MLflow git-based version tracking unavailable (non-fatal): %s", _exc)
    LOGGER.warning(
        "Agent startup | backend=%s model=%s fallback_model=%s retries=%s base_retry_seconds=%s",
        agent_module.BACKEND,
        agent_module.MODEL,
        agent_module.FALLBACK_MODEL or "<none>",
        agent_module.MAX_RETRIES,
        agent_module.RETRY_BASE_SECONDS,
    )
    yield


app.router.lifespan_context = _lifespan


@app.middleware("http")
async def request_guardrails(request: Request, call_next):
    started_at = time.perf_counter()
    context = extract_request_context(dict(request.headers))

    if not validate_auth_header(request.headers.get("authorization")):
        return JSONResponse(
            status_code=401,
            content={
                "error": "unauthorized",
                "message": "Missing or invalid Authorization token",
            },
        )

    if not RATE_LIMITER.allow(context.user_id):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Per-user request limit exceeded",
            },
        )

    response = await call_next(request)
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    LOGGER.info(
        "audit request | tenant=%s user=%s method=%s path=%s status=%s duration_ms=%s",
        context.tenant_id,
        context.user_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "backend": agent_module.BACKEND,
        "openai_credentials_configured": agent_module.OPENAI_CREDENTIALS_CONFIGURED,
        "databricks_tools_enabled": agent_module.USE_DATABRICKS,
        "model": agent_module.MODEL,
        "fallback_model": agent_module.FALLBACK_MODEL or None,
        "max_retries": agent_module.MAX_RETRIES,
        "retry_base_seconds": agent_module.RETRY_BASE_SECONDS,
    }


@app.get("/")
async def root() -> dict:
    return {
        "service": "agent-openai-agents-sdk",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "invocations": "/invocations",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/client-capabilities")
async def client_capabilities() -> dict:
    contract = build_client_contract()
    contract["runtime"] = {
        "backend": agent_module.BACKEND,
        "model": agent_module.MODEL,
        "fallback_model": agent_module.FALLBACK_MODEL or None,
        "max_retries": agent_module.MAX_RETRIES,
    }
    return contract


def main():
    agent_server.run(app_import_string="agent_server.start_server:app")


if __name__ == "__main__":
    main()
