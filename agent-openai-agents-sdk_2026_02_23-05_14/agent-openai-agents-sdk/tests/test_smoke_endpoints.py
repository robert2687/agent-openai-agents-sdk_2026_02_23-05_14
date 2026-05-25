import importlib
import os

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("mlflow")
pytest.importorskip("agents")


def _prepare_env() -> None:
    os.environ.setdefault("AGENT_BACKEND", "openai")
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("MLFLOW_TRACKING_URI", "file:///tmp/mlruns-test")
    os.environ.setdefault("MLFLOW_REGISTRY_URI", "file:///tmp/mlruns-test")
    os.environ.setdefault("MLFLOW_EXPERIMENT_ID", "0")


def _load_app():
    _prepare_env()
    start_server = importlib.import_module("agent_server.start_server")
    start_server = importlib.reload(start_server)
    return start_server.app


def test_health_endpoint_returns_ok():
    app = _load_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    # MLflow's built-in health endpoint can return {"status": "healthy"}
    # depending on route registration order.
    assert payload["status"] in {"ok", "healthy"}


def test_invocations_non_stream_success_with_mock(monkeypatch):
    app = _load_app()
    client = TestClient(app)

    agent_module = importlib.import_module("agent_server.agent")

    class FakeItem:
        def to_input_item(self):
            return {
                "id": "msg-test-1",
                "type": "message",
                "content": [{"type": "output_text", "text": "hello from test"}],
            }

    class FakeResult:
        new_items = [FakeItem()]

    async def fake_run_with_retries(messages, mcp_server=None):  # noqa: ARG001
        return FakeResult()

    async def fake_persist_memory(messages, output_items):  # noqa: ARG001
        return None

    monkeypatch.setattr(agent_module, "_run_with_retries", fake_run_with_retries)
    monkeypatch.setattr(agent_module, "_persist_memory", fake_persist_memory)

    response = client.post(
        "/invocations",
        json={"input": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "output" in payload
    assert isinstance(payload["output"], list)
    assert payload["output"][0]["type"] == "message"


def test_invocations_returns_guidance_when_openai_key_missing(monkeypatch):
    app = _load_app()
    client = TestClient(app)

    agent_module = importlib.import_module("agent_server.agent")

    async def fake_run_with_retries(messages, mcp_server=None):  # noqa: ARG001
        raise RuntimeError(
            "OpenAI backend is not configured. Set OPENAI_API_KEY (or OPENAI_ADMIN_KEY) and restart the server."
        )

    monkeypatch.setattr(agent_module, "_run_with_retries", fake_run_with_retries)

    response = client.post(
        "/invocations",
        json={"input": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "output" in payload
    assert payload["output"]
    assert "OpenAI backend is not configured" in payload["output"][0]["content"][0]["text"]
