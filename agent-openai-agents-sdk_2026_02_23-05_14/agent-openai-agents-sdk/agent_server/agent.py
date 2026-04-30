from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, AsyncGenerator

# Default to local SQLite-backed MLflow tracking before any mlflow import.
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")

from openai import AsyncOpenAI

try:
    from databricks.sdk import WorkspaceClient
except ImportError:  # pragma: no cover - optional in OpenAI-only mode
    WorkspaceClient = Any

import mlflow
from agents import Agent, Runner, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.utils import (
    build_mcp_url,
    get_user_workspace_client,
    process_agent_stream_events,
    sanitize_output_items,
)
from agent_server.memory_store import build_memory_store

BACKEND = os.getenv("AGENT_BACKEND", "").strip().lower()
if BACKEND not in {"databricks", "openai"}:
    BACKEND = "openai" if os.getenv("OPENAI_API_KEY") else "databricks"

USE_DATABRICKS = BACKEND == "databricks"
MODEL = os.getenv(
    "AGENT_MODEL",
    "databricks-gpt-5-2" if USE_DATABRICKS else "gpt-4.1-mini",
)
DEFAULT_FALLBACK_MODEL = "databricks-gpt-5-2" if USE_DATABRICKS else "gpt-4.1"
FALLBACK_MODEL = os.getenv("AGENT_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL).strip()


def _load_databricks_openai():
    try:
        from databricks_openai import AsyncDatabricksOpenAI
        from databricks_openai.agents import McpServer

        return AsyncDatabricksOpenAI, McpServer
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Databricks backend selected but databricks-openai is not installed. "
            "Install optional Databricks dependencies to use AGENT_BACKEND=databricks."
        ) from exc


def _require_databricks_sdk() -> None:
    if WorkspaceClient is Any:
        raise RuntimeError(
            "Databricks backend selected but databricks-sdk is not installed. "
            "Install optional Databricks dependencies or switch to AGENT_BACKEND=openai."
        )


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _read_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


MAX_RETRIES = max(1, _read_int_env("AGENT_MAX_RETRIES", 3))
RETRY_BASE_SECONDS = max(0.1, _read_float_env("AGENT_RETRY_BASE_SECONDS", 1.5))
LOGGER = logging.getLogger(__name__)
MEMORY_STORE = build_memory_store()
DEFAULT_MEMORY_TENANT = os.getenv("AGENT_MEMORY_TENANT", "default-tenant")
DEFAULT_MEMORY_USER = os.getenv("AGENT_MEMORY_USER", "default-user")

CODING_INSTRUCTIONS = """
You are a senior coding assistant.

Behavior requirements:
1) If the request is ambiguous, ask concise clarifying questions before coding.
2) Prefer correct, runnable solutions over clever but brittle ones.
3) Return code in fenced blocks and include short usage/test snippets when relevant.
4) For bug fixes/refactors, explain what changed and why in 3-6 bullets.
5) If tools are unavailable, say so clearly and provide the best no-tool fallback.
""".strip()

# Databricks models are served via Chat Completions-compatible APIs.
if USE_DATABRICKS:
    AsyncDatabricksOpenAI, _ = _load_databricks_openai()
    set_default_openai_client(AsyncDatabricksOpenAI())
    set_default_openai_api("chat_completions")
else:
    # Extension-like mode: standard OpenAI key + model.
    # Optional OPENAI_BASE_URL is supported by the OpenAI SDK.
    set_default_openai_client(AsyncOpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None))
    set_default_openai_api("chat_completions")

set_trace_processors([])  # only use mlflow for trace processing
if os.getenv("AGENT_ENABLE_MLFLOW_AUTOLOG", "0") == "1":
    mlflow.openai.autolog()


async def init_mcp_server(workspace_client: WorkspaceClient | None = None):
    _require_databricks_sdk()
    _, McpServer = _load_databricks_openai()
    return McpServer(
        url=build_mcp_url("/api/2.0/mcp/functions/system/ai", workspace_client=workspace_client),
        name="system.ai UC function MCP server",
        workspace_client=workspace_client,
    )


def create_coding_agent(mcp_server=None) -> Agent:
    mcp_servers = [mcp_server] if mcp_server else []
    return create_coding_agent_for_model(model=MODEL, mcp_server=mcp_server)


def create_coding_agent_for_model(model: str, mcp_server=None) -> Agent:
    mcp_servers = [mcp_server] if mcp_server else []
    return Agent(
        name="Code execution agent",
        instructions=CODING_INSTRUCTIONS,
        model=model,
        mcp_servers=mcp_servers,
    )


def _candidate_models() -> list[str]:
    candidates = [MODEL]
    if FALLBACK_MODEL and FALLBACK_MODEL != MODEL:
        candidates.append(FALLBACK_MODEL)
    return candidates


async def _run_with_retries(messages: list[dict], mcp_server=None):
    last_error = None
    for model_idx, candidate_model in enumerate(_candidate_models(), start=1):
        agent = create_coding_agent_for_model(candidate_model, mcp_server=mcp_server)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await Runner.run(agent, messages)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= MAX_RETRIES:
                    break
                delay = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                LOGGER.warning(
                    "Agent run failed (model=%s, attempt=%s/%s). Retrying in %.1fs. Error=%s",
                    candidate_model,
                    attempt,
                    MAX_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

        if model_idx < len(_candidate_models()):
            LOGGER.warning(
                "Switching to fallback model after failures: %s -> %s",
                candidate_model,
                _candidate_models()[model_idx],
            )

    raise RuntimeError(f"Agent failed after retries and fallback. Last error: {last_error}")


async def _stream_with_retries(
    messages: list[dict],
    mcp_server=None,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    last_error = None
    for model_idx, candidate_model in enumerate(_candidate_models(), start=1):
        agent = create_coding_agent_for_model(candidate_model, mcp_server=mcp_server)
        for attempt in range(1, MAX_RETRIES + 1):
            emitted_any = False
            try:
                result = Runner.run_streamed(agent, input=messages)
                async for event in process_agent_stream_events(result.stream_events()):
                    emitted_any = True
                    yield event
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                # Avoid duplicate partial streams if output has already started.
                if emitted_any:
                    raise
                if attempt >= MAX_RETRIES:
                    break
                delay = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                LOGGER.warning(
                    "Agent stream failed (model=%s, attempt=%s/%s). Retrying in %.1fs. Error=%s",
                    candidate_model,
                    attempt,
                    MAX_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

        if model_idx < len(_candidate_models()):
            LOGGER.warning(
                "Switching to fallback model for streaming: %s -> %s",
                candidate_model,
                _candidate_models()[model_idx],
            )

    raise RuntimeError(f"Agent stream failed after retries and fallback. Last error: {last_error}")


def _latest_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [p.get("text") for p in content if isinstance(p, dict) and p.get("text")]
            if parts:
                return "\n".join(parts)
    return ""


def _response_text(output_items: list[dict]) -> str:
    chunks: list[str] = []
    for item in output_items:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("text"):
                chunks.append(str(part["text"]))
    return "\n".join(chunks).strip()


async def _persist_memory(messages: list[dict], output_items: list[dict]) -> None:
    """Persist simple request/response memory with safe fallbacks.

    This is intentionally best-effort and should never break agent responses.
    """
    user_text = _latest_user_text(messages)
    assistant_text = _response_text(output_items)
    if not user_text and not assistant_text:
        return

    try:
        if user_text:
            await MEMORY_STORE.add_message(
                tenant_id=DEFAULT_MEMORY_TENANT,
                user_id=DEFAULT_MEMORY_USER,
                role="user",
                content=user_text,
            )
        if assistant_text:
            await MEMORY_STORE.add_message(
                tenant_id=DEFAULT_MEMORY_TENANT,
                user_id=DEFAULT_MEMORY_USER,
                role="assistant",
                content=assistant_text,
            )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Memory persistence skipped due to error: %s", exc)


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    messages = [i.model_dump() for i in request.input]

    if USE_DATABRICKS:
        workspace_client = get_user_workspace_client() or WorkspaceClient()
        async with await init_mcp_server(workspace_client) as mcp_server:
            result = await _run_with_retries(messages, mcp_server=mcp_server)
            output_items = sanitize_output_items(result.new_items)
            await _persist_memory(messages, output_items)
            return ResponsesAgentResponse(output=output_items)

    result = await _run_with_retries(messages)
    output_items = sanitize_output_items(result.new_items)
    await _persist_memory(messages, output_items)
    return ResponsesAgentResponse(output=output_items)


@stream()
async def stream_handler(request: dict) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    messages = [i.model_dump() for i in request.input]

    if USE_DATABRICKS:
        workspace_client = get_user_workspace_client() or WorkspaceClient()
        async with await init_mcp_server(workspace_client) as mcp_server:
            async for event in _stream_with_retries(messages, mcp_server=mcp_server):
                yield event
        return

    async for event in _stream_with_retries(messages):
        yield event
