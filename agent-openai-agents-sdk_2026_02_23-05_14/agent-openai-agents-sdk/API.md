# API Documentation

This server follows the MLflow ResponsesAgent interface and is intended to be usable in local/OpenAI mode without Databricks. Databricks mode remains optional for Databricks-authenticated tools and deployment.

## Base URL

When running locally with `uv run start-server` or Docker Compose, the default base URL is:

```text
http://localhost:8000
```

For Databricks Apps deployments, the base URL is the Databricks App URL provided by your workspace.

## Authentication

Local/OpenAI mode relies on `.env` values such as `AGENT_BACKEND=openai` and `OPENAI_API_KEY`. Databricks authentication is only required when using `AGENT_BACKEND=databricks`.

## Content Type

All requests use JSON.

```text
Content-Type: application/json
```

## Endpoint: Invoke Agent

`POST /invocations`

Invokes the agent and returns a complete response.

### Request Body

```json
{
  "input": [
    {
      "role": "user",
      "content": "Hello!"
    }
  ]
}
```

#### Request fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `input` | array | Yes | Array of message objects using Responses API format (`role`, `content`). |
| `stream` | boolean | No | If `true`, the server streams events instead of returning a single response (see Streaming endpoint behavior below). |

### Response

```json
{
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "Hi! How can I help you today?"
        }
      ]
    }
  ]
}
```

## Endpoint: Health

`GET /health`

Example response:

```json
{
  "status": "ok",
  "backend": "openai",
  "databricks_tools_enabled": false,
  "model": "gpt-4.1-mini",
  "fallback_model": "gpt-4.1",
  "max_retries": 2,
  "retry_base_seconds": 1.0
}
```

## Streaming Responses

To stream responses, set `"stream": true` in the request body and send the request to the same endpoint:

`POST /invocations`

### Example (curl)

```bash
curl -N -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Stream a response"}],
    "stream": true
  }'
```

The server returns a stream of `ResponsesAgentStreamEvent` payloads, compatible with the OpenAI Responses API streaming format. Each event represents an incremental update to the response items.

## Example (Non-Streaming)

```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello"}]
  }'
```

## Tooling & Capabilities

In local/OpenAI mode, the agent runs without Databricks MCP tooling. In Databricks mode, the agent can use the Databricks MCP server for the built-in code interpreter tool (`system.ai.python_exec`). Tool calls are surfaced in Responses API output items. The agent implementation lives in:

- `agent_server/agent.py`
- `agent_server/start_server.py`

## Error Handling

Errors are returned as standard HTTP error responses with JSON bodies. Common issues include:

- **400 Bad Request**: Invalid input format.
- **401/403 Unauthorized**: Missing or invalid upstream credentials for the configured backend.
- **500 Internal Server Error**: Unhandled agent or tool error.

## Related Documentation

- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [MLflow Responses Agent](https://mlflow.org/docs/latest/genai/flavors/responses-agent-intro/)
- [Databricks Agent Framework](https://docs.databricks.com/aws/en/generative-ai/agent-framework/)
