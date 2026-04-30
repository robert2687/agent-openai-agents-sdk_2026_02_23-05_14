import json
import logging
from typing import Any, AsyncGenerator, AsyncIterator, Optional
from uuid import uuid4

from agents.result import StreamEvent
from mlflow.genai.agent_server import get_request_headers
from mlflow.types.responses import ResponsesAgentStreamEvent

try:
    from databricks.sdk import WorkspaceClient
except ImportError:  # pragma: no cover - optional in OpenAI-only mode
    WorkspaceClient = Any


def _require_databricks_sdk() -> None:
    if WorkspaceClient is Any:
        raise RuntimeError(
            "Databricks backend selected but databricks-sdk is not installed. "
            "Install optional Databricks dependencies or switch to AGENT_BACKEND=openai."
        )


def get_databricks_host(workspace_client: WorkspaceClient | None = None) -> Optional[str]:
    _require_databricks_sdk()
    workspace_client = workspace_client or WorkspaceClient()
    try:
        return workspace_client.config.host
    except Exception as e:
        logging.exception(f"Error getting databricks host from env: {e}")
        return None


def build_mcp_url(path: str, workspace_client: WorkspaceClient | None = None) -> str:
    if not path.startswith("/"):
        return path
    hostname = get_databricks_host(workspace_client)
    return f"{hostname}{path}"


def get_user_workspace_client() -> Optional[WorkspaceClient]:
    """Return a WorkspaceClient authenticated as the requesting user via OBO OAuth.

    The Databricks Apps platform forwards the user's OAuth access token in the
    ``x-forwarded-access-token`` request header.  When that header is absent
    (e.g. during local development) ``None`` is returned so the caller can fall
    back to the app service-principal credentials.
    """
    token = get_request_headers().get("x-forwarded-access-token")
    if not token:
        return None
    _require_databricks_sdk()
    return WorkspaceClient(token=token, auth_type="pat")


def _sanitize_item(input_item: dict) -> dict:
    """Sanitize a single output item dict for Pydantic validation.

    MCP tool calls (e.g. Genie) can return items where the ``output`` field is
    a *list* of content objects instead of a plain string. MLflow's Pydantic
    models expect ``output`` to be a string, so this serialises any non-string
    values to JSON.

    TODO: Remove once https://github.com/mlflow/mlflow/pull/20777 is released.
    """
    if not isinstance(input_item.get("output"), str):
        try:
            input_item["output"] = json.dumps(input_item.get("output"))
        except (TypeError, ValueError):
            input_item["output"] = str(input_item.get("output"))
    return input_item


def sanitize_output_items(items) -> list[dict]:
    """Convert agent output items to dicts safe for ResponsesAgentResponse."""
    return [_sanitize_item(item.to_input_item()) for item in items]


async def process_agent_stream_events(
    async_stream: AsyncIterator[StreamEvent],
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    curr_item_id = str(uuid4())
    async for event in async_stream:
        if event.type == "raw_response_event":
            event_data = event.data.model_dump()
            if event_data["type"] == "response.output_item.added":
                curr_item_id = str(uuid4())
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item") is not None and event_data["item"].get("id") is not None:
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item_id") is not None:
                event_data["item_id"] = curr_item_id
            yield event_data
        elif event.type == "run_item_stream_event" and event.item.type == "tool_call_output_item":
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=_sanitize_item(event.item.to_input_item()),
            )
