# Quick Start Guide

## Choose your backend

This project supports two setup paths:

- Local/OpenAI mode: recommended for local development and the fastest non-Databricks setup.
- Databricks mode: optional if you need Databricks authentication, MCP tools, or Databricks deployment.

## Local/OpenAI mode

### 1. Install dependencies

```bash
uv sync
```

If you do not use `uv`, install the package in editable mode with pip.

### 2. Configure `.env`

```bash
cp .env.example .env
```

Windows PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

Set these values:

```bash
AGENT_BACKEND=openai
OPENAI_API_KEY=<your-key>
AGENT_MODEL=gpt-4.1-mini
AGENT_FALLBACK_MODEL=gpt-4.1
```

### 3. Verify setup

```bash
uv run verify-setup
```

In OpenAI mode, this should pass without Databricks CLI installed.

### 4. Start the server

```bash
uv run start-server --reload
```

Endpoints:

- API: `http://localhost:8000/invocations`
- Health: `http://localhost:8000/health`
- Docs: `http://localhost:8000/docs`

### 5. Optional local UI

Use Docker Compose for a simple local API + UI stack:

```bash
docker compose up --build
```

This starts:

- API on `http://localhost:8000`
- Gradio UI on `http://localhost:7860`

## Browser extension (Chrome + Edge)

After your backend is running, you can use the included browser extension.

1. Open Chrome extensions page: `chrome://extensions` (or Edge extensions page: `edge://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked** and choose `browser-extension/`.
4. Open extension settings (⚙) and confirm the backend URL (default `http://localhost:8000`).

To package a zip for distribution:

```bash
uv run package-browser-extension
```

## Databricks mode

Use this mode only if you need Databricks-backed tools or Databricks deployment.

```bash
uv run quickstart --backend databricks
```

That flow checks Databricks prerequisites, sets up auth, and configures MLflow tracking in Databricks.

## Test the server

### Health check

```bash
curl http://localhost:8000/health
```

Expected fields include:

- `backend`
- `databricks_tools_enabled`
- `model`
- `fallback_model`

### Non-streaming request

```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello"}]
  }'
```

### Streaming request

```bash
curl -N -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Stream a response"}],
    "stream": true
  }'
```

## Troubleshooting

### Missing Databricks packages in OpenAI mode

OpenAI mode no longer requires `databricks-sdk` or `databricks-openai`. If you still see a Databricks import error, make sure `.env` sets `AGENT_BACKEND=openai`.

### Missing Python dependencies

```bash
uv sync
```

### Port already in use

```bash
uv run start-server --port 8001
```

## Recommended development loop

1. Run `uv run start-server --reload`
2. Hit `GET /health`
3. Test `POST /invocations`
4. Edit `agent_server/agent.py`
5. Re-run `uv run verify-setup` after environment changes
