"""Enhanced agent module with caching, circuit breaker, and improved error handling.

This module provides the core agent functionality with:
- Model caching for better performance
- Circuit breaker pattern for resilience
- Enhanced retry logic with exponential backoff
- Comprehensive error handling
- Token counting and metrics
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from functools import lru_cache
from typing import Any, AsyncGenerator

# Default to local SQLite-backed MLflow tracking before any mlflow import.
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")

from openai import AsyncOpenAI

try:
    from databricks.sdk import WorkspaceClient
except ImportError:  # pragma: no cover - optional in OpenAI-only mode
    WorkspaceClient = Any

import mlflow
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.config import get_config
from agent_server.utils import (
    build_mcp_url,
    get_user_workspace_client,
    process_agent_stream_events,
    sanitize_output_items,
)
from agent_server.memory_store import build_memory_store
from agent_server.monitoring import (
    logger,
    record_agent_invocation,
    record_fallback,
    record_retry_attempt,
)
from agent_server.security import InputValidator


# ============================================================================
# Circuit Breaker Implementation
# ============================================================================

class CircuitBreaker:
    """Circuit breaker pattern for external API calls.

    Prevents cascading failures by temporarily blocking calls to failing services.
    """

    def __init__(
        self,
        max_failures: int = 5,
        reset_timeout: float = 30.0,
        half_open_after: float = 10.0,
    ):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.half_open_after = half_open_after
        self._state = "closed"  # closed, open, half-open
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._next_attempt_time = 0.0
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            now = time.time()

            if self._state == "open":
                if now < self._next_attempt_time:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is open. Retry after {self._next_attempt_time - now:.1f}s"
                    )
                # Transition to half-open
                self._state = "half-open"

            try:
                result = await func(*args, **kwargs)
                # Success - reset circuit breaker
                self._reset()
                return result
            except Exception as e:
                self._record_failure(now)
                raise

    def _reset(self):
        """Reset circuit breaker state."""
        self._state = "closed"
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._next_attempt_time = 0.0

    def _record_failure(self, failure_time: float):
        """Record a failure."""
        self._failure_count += 1
        self._last_failure_time = failure_time

        if self._failure_count >= self.max_failures:
            self._state = "open"
            self._next_attempt_time = failure_time + self.reset_timeout


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


# ============================================================================
# Model Cache
# ============================================================================

class ModelCache:
    """Cache for agent instances to avoid repeated initialization."""

    def __init__(self, max_size: int = 10):
        self._cache: dict[str, Agent] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._access_times: dict[str, float] = {}

    async def get(self, key: str, create_func) -> Agent:
        """Get agent from cache or create new one."""
        async with self._lock:
            if key in self._cache:
                # Update access time for LRU
                self._access_times[key] = time.time()
                return self._cache[key]

            # Create new agent
            agent = await create_func()
            self._cache[key] = agent
            self._access_times[key] = time.time()

            # Evict oldest if cache is full
            if len(self._cache) > self._max_size:
                self._evict_oldest()

            return agent

    def _evict_oldest(self):
        """Evict least recently used agent."""
        if not self._access_times:
            return

        oldest_key = min(self._access_times.keys(), key=self._access_times.get)
        self._cache.pop(oldest_key, None)
        self._access_times.pop(oldest_key, None)

    def clear(self):
        """Clear all cached agents."""
        self._cache.clear()
        self._access_times.clear()

    def invalidate(self, key: str):
        """Invalidate a specific agent."""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)


# Global model cache
model_cache = ModelCache(max_size=10)


# ============================================================================
# Connection Cache
# ============================================================================

class ConnectionCache:
    """Cache for OpenAI client connections."""

    def __init__(self):
        self._clients: dict[str, AsyncOpenAI] = {}
        self._lock = asyncio.Lock()

    async def get_client(self, base_url: str | None, api_key: str | None) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        cache_key = f"{base_url}:{bool(api_key)}"

        async with self._lock:
            if cache_key in self._clients:
                return self._clients[cache_key]

            client = AsyncOpenAI(base_url=base_url, api_key=api_key)
            self._clients[cache_key] = client
            return client

    def clear(self):
        """Clear all cached clients."""
        self._clients.clear()


connection_cache = ConnectionCache()


# ============================================================================
# Configuration and State
# ============================================================================

config = get_config()

BACKEND = config.backend
USE_DATABRICKS = BACKEND == "databricks"
MODEL = config.model
FALLBACK_MODEL = config.fallback_model or None
MAX_RETRIES = config.max_retries
RETRY_BASE_SECONDS = config.retry_base_seconds
MAX_TOKENS = config.max_tokens
LOGGER = logging.getLogger(__name__)
MEMORY_STORE = build_memory_store()
DEFAULT_MEMORY_TENANT = config.memory_tenant
DEFAULT_MEMORY_USER = config.memory_user

# Circuit breakers for different services
openai_circuit_breaker = CircuitBreaker(max_failures=5, reset_timeout=60.0)
databricks_circuit_breaker = CircuitBreaker(max_failures=3, reset_timeout=120.0)

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
_OPENAI_CLIENT: AsyncOpenAI | None = None
OPENAI_CREDENTIALS_CONFIGURED = config.openai_credentials_configured

# Initialize OpenAI client with caching
async def _get_openai_client() -> AsyncOpenAI | None:
    """Get OpenAI client with connection caching."""
    global _OPENAI_CLIENT

    if _OPENAI_CLIENT is not None:
        return _OPENAI_CLIENT

    if USE_DATABRICKS:
        try:
            from databricks_openai import AsyncDatabricksOpenAI

            _OPENAI_CLIENT = AsyncDatabricksOpenAI()
            set_default_openai_client(_OPENAI_CLIENT)
            set_default_openai_api("chat_completions")
            return _OPENAI_CLIENT
        except ImportError as exc:
            LOGGER.warning("Databricks backend selected but databricks-openai is not installed: %s", exc)
            return None
    else:
        if OPENAI_CREDENTIALS_CONFIGURED:
            _OPENAI_CLIENT = await connection_cache.get_client(
                base_url=config.openai_base_url,
                api_key=config.openai_api_key or config.openai_admin_key
            )
            set_default_openai_client(_OPENAI_CLIENT)
            set_default_openai_api("chat_completions")
            return _OPENAI_CLIENT
        else:
            LOGGER.warning(
                "OPENAI_API_KEY/OPENAI_ADMIN_KEY is not set. Server can start, but /invocations will fail "
                "until OpenAI credentials are configured."
            )
            return None


# ============================================================================
# Agent Creation
# ============================================================================

async def _load_databricks_openai():
    try:
        from databricks_openai import AsyncDatabricksOpenAI, McpServer

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


async def init_mcp_server(workspace_client: WorkspaceClient | None = None):
    _require_databricks_sdk()
    AsyncDatabricksOpenAI, McpServer = await _load_databricks_openai()
    return McpServer(
        url=build_mcp_url("/api/2.0/mcp/functions/system/ai", workspace_client=workspace_client),
        name="system.ai UC function MCP server",
        workspace_client=workspace_client,
    )


async def _create_agent_for_model(model: str, mcp_server=None) -> Agent:
    """Create agent instance for specific model."""
    if not USE_DATABRICKS and _OPENAI_CLIENT is None:
        raise RuntimeError(
            "OpenAI backend is not configured. Set OPENAI_API_KEY (or OPENAI_ADMIN_KEY) and restart the server."
        )

    # When using a custom base_url (e.g. OpenRouter), the Agents SDK doesn't
    # recognise non-standard model name prefixes (e.g. "nvidia/...", "qwen/...").
    # Wrap in OpenAIChatCompletionsModel so the SDK uses the custom client directly.
    if _OPENAI_CLIENT is not None and "/" in model:
        resolved_model = OpenAIChatCompletionsModel(
            model=model,
            openai_client=_OPENAI_CLIENT,
        )
    else:
        resolved_model = model  # type: ignore[assignment]

    return Agent(
        name="Code execution agent",
        instructions=CODING_INSTRUCTIONS,
        model=resolved_model,
        model_settings=ModelSettings(max_tokens=MAX_TOKENS),
        mcp_servers=[mcp_server] if mcp_server else [],
    )


async def create_coding_agent(mcp_server=None) -> Agent:
    """Create coding agent with caching."""
    cache_key = f"{MODEL}:{id(mcp_server)}"
    return await model_cache.get(cache_key, lambda: _create_agent_for_model(MODEL, mcp_server))


async def create_coding_agent_for_model(model: str, mcp_server=None) -> Agent:
    """Create coding agent for specific model with caching."""
    cache_key = f"{model}:{id(mcp_server)}"
    return await model_cache.get(cache_key, lambda: _create_agent_for_model(model, mcp_server))


# ============================================================================
# Candidate Models
# ============================================================================

def _candidate_models() -> list[str]:
    candidates = [MODEL]
    if FALLBACK_MODEL and FALLBACK_MODEL != MODEL:
        candidates.append(FALLBACK_MODEL)
    return candidates


# ============================================================================
# Retry Logic with Circuit Breaker
# ============================================================================

async def _run_with_retries(messages: list[dict], mcp_server=None):
    """Run agent with retry logic and circuit breaker."""
    last_error = None
    start_time = time.time()

    for model_idx, candidate_model in enumerate(_candidate_models(), start=1):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Use circuit breaker for OpenAI calls
                async def run_agent():
                    agent = await create_coding_agent_for_model(candidate_model, mcp_server=mcp_server)
                    return await Runner.run(agent, messages)

                result = await openai_circuit_breaker.call(run_agent)

                # Record metrics
                duration = time.time() - start_time
                record_agent_invocation(
                    model=candidate_model,
                    streaming=False,
                    status="success",
                    duration=duration,
                )

                return result

            except CircuitBreakerOpenError as exc:
                LOGGER.warning("Circuit breaker open for model %s: %s", candidate_model, exc)
                record_agent_invocation(
                    model=candidate_model,
                    streaming=False,
                    status="circuit_breaker_open",
                )
                last_error = exc
                break  # Don't retry if circuit breaker is open

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                record_retry_attempt(candidate_model, attempt)

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
            record_fallback(candidate_model, _candidate_models()[model_idx])

    raise RuntimeError(f"Agent failed after retries and fallback. Last error: {last_error}")


async def _stream_with_retries(
    messages: list[dict],
    mcp_server=None,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Stream agent response with retry logic."""
    last_error = None
    start_time = time.time()

    for model_idx, candidate_model in enumerate(_candidate_models(), start=1):
        for attempt in range(1, MAX_RETRIES + 1):
            emitted_any = False
            try:
                async def stream_agent():
                    agent = await create_coding_agent_for_model(candidate_model, mcp_server=mcp_server)
                    result = Runner.run_streamed(agent, input=messages)
                    return result.stream_events()

                async for event in process_agent_stream_events(
                    await openai_circuit_breaker.call(stream_agent)
                ):
                    emitted_any = True
                    yield event

                # Record metrics
                duration = time.time() - start_time
                record_agent_invocation(
                    model=candidate_model,
                    streaming=True,
                    status="success",
                    duration=duration,
                )
                return

            except CircuitBreakerOpenError as exc:
                LOGGER.warning("Circuit breaker open for streaming model %s: %s", candidate_model, exc)
                record_agent_invocation(
                    model=candidate_model,
                    streaming=True,
                    status="circuit_breaker_open",
                )
                last_error = exc
                break

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                record_retry_attempt(candidate_model, attempt)

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
            record_fallback(candidate_model, _candidate_models()[model_idx])

    raise RuntimeError(f"Agent stream failed after retries and fallback. Last error: {last_error}")


# ============================================================================
# Helper Functions
# ============================================================================

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


def _missing_credentials_output() -> list[dict[str, Any]]:
    return [
        {
            "id": "msg-config-missing",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": (
                        "OpenAI backend is not configured yet. "
                        "Set OPENAI_API_KEY (or OPENAI_ADMIN_KEY), restart the server, "
                        "and retry your request."
                    ),
                }
            ],
        }
    ]


# ============================================================================
# Memory Persistence
# ============================================================================

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


# ============================================================================
# Handler Functions
# ============================================================================

@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    """Handle non-streaming agent invocations."""
    # Validate input
    messages = [i.model_dump() for i in request.input]
    is_valid, error_msg = InputValidator.validate_messages(messages)
    if not is_valid:
        raise ValueError(f"Invalid input: {error_msg}")

    # Initialize OpenAI client if needed
    if _OPENAI_CLIENT is None:
        await _get_openai_client()

    if USE_DATABRICKS:
        workspace_client = get_user_workspace_client() or WorkspaceClient()
        async with await init_mcp_server(workspace_client) as mcp_server:
            result = await _run_with_retries(messages, mcp_server=mcp_server)
            output_items = sanitize_output_items(result.new_items)
            await _persist_memory(messages, output_items)
            return ResponsesAgentResponse(output=output_items)

    try:
        result = await _run_with_retries(messages)
        output_items = sanitize_output_items(result.new_items)
        await _persist_memory(messages, output_items)
        return ResponsesAgentResponse(output=output_items)
    except RuntimeError as exc:
        if "OpenAI backend is not configured" not in str(exc):
            raise

        LOGGER.warning("Invocation fallback due to missing OpenAI credentials: %s", exc)
        return ResponsesAgentResponse(output=_missing_credentials_output())


@stream()
async def stream_handler(request: dict) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Handle streaming agent invocations."""
    # Validate input
    messages = [i.model_dump() for i in request.input]
    is_valid, error_msg = InputValidator.validate_messages(messages)
    if not is_valid:
        raise ValueError(f"Invalid input: {error_msg}")

    # Initialize OpenAI client if needed
    if _OPENAI_CLIENT is None:
        await _get_openai_client()

    if USE_DATABRICKS:
        workspace_client = get_user_workspace_client() or WorkspaceClient()
        async with await init_mcp_server(workspace_client) as mcp_server:
            async for event in _stream_with_retries(messages, mcp_server=mcp_server):
                yield event
        return

    async for event in _stream_with_retries(messages):
        yield event


# ============================================================================
# Initialization
# ============================================================================

# Set up MLflow tracing
set_trace_processors([])  # only use mlflow for trace processing
if os.getenv("AGENT_ENABLE_MLFLOW_AUTOLOG", "0") == "1":
    mlflow.openai.autolog()
