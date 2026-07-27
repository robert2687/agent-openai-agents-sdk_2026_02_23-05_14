# API Documentation

This document provides comprehensive API documentation for the Agent OpenAI Agents SDK.

## Base URL

```
http://localhost:8000
```

## Authentication

### Bearer Token Authentication

All endpoints (except health checks) require authentication via Bearer token.

**Header:** `Authorization: Bearer <token>`

**Configuration:**
- Set `AGENT_API_TOKEN` environment variable with your API token
- Set `AGENT_REQUIRE_AUTH=1` to enable authentication

**Example:**
```bash
curl -H "Authorization: Bearer your-api-token" http://localhost:8000/health
```

### Rate Limiting

- **Default:** 120 requests per minute per user
- **Configurable:** Set `AGENT_RATE_LIMIT_PER_MINUTE` environment variable
- **Headers:**
  - `429 Too Many Requests` when limit exceeded
  - `Retry-After: 60` header indicates seconds until next request allowed

## Endpoints

### Health and Status

#### GET /health

Returns the health status of the service.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "backend": "openai",
  "openai_credentials_configured": true,
  "databricks_tools_enabled": false,
  "model": "gpt-4.1-mini",
  "fallback_model": "gpt-4.1",
  "max_retries": 3,
  "retry_base_seconds": 1.5,
  "max_tokens": 4096,
  "rate_limit_per_minute": 120,
  "require_auth": false,
  "memory_backend": "inmemory"
}
```

#### GET /

Returns basic service information.

**Request:**
```bash
curl http://localhost:8000/
```

**Response:**
```json
{
  "service": "agent-openai-agents-sdk",
  "status": "ok",
  "version": "0.2.0",
  "docs": "/docs",
  "health": "/health",
  "invocations": "/invocations",
  "metrics": "/metrics"
}
```

#### GET /client-capabilities

Returns client capabilities and runtime information.

**Request:**
```bash
curl http://localhost:8000/client-capabilities
```

**Response:**
```json
{
  "capabilities": {
    "supportsStreaming": true,
    "supportsTools": true,
    "supportsMemory": true
  },
  "runtime": {
    "backend": "openai",
    "model": "gpt-4.1-mini",
    "fallback_model": "gpt-4.1",
    "max_retries": 3,
    "max_tokens": 4096,
    "rate_limit_per_minute": 120
  }
}
```

### Agent Invocations

#### POST /invocations

Send a request to the agent for processing.

**Request:**
```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-token" \
  -d '{
    "input": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "stream": false,
    "max_tokens": 1000
  }'
```

**Request Body:**
```json
{
  "input": [
    {
      "role": "system" | "user" | "assistant" | "tool",
      "content": "string" | [{"type": "text", "text": "string"}]
    }
  ],
  "stream": false,
  "max_tokens": 1000
}
```

**Response (non-streaming):**
```json
{
  "output": [
    {
      "id": "msg-123",
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "I'm doing well, thank you for asking!"
        }
      ]
    }
  ]
}
```

**Response (streaming):**
```
HTTP/1.1 200 OK
Content-Type: text/event-stream

event: message
data: {"id": "msg-123", "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Hello"}]}

event: message
data: {"id": "msg-123", "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "!"}]}

event: done
data: {}
```

**Validation Rules:**
- `input` must be a non-empty array
- Each message must have `role` and `content` fields
- Valid roles: `system`, `user`, `assistant`, `tool`
- Maximum 100 messages per request
- Maximum 100,000 characters per message content

**Error Responses:**
```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": [{"loc": ["body", "input", 0, "role"], "msg": "field required"}],
  "request_id": "req-123"
}
```

### Configuration

#### GET /config

Get current configuration (non-sensitive values only).

**Request:**
```bash
curl http://localhost:8000/config
```

**Response:**
```json
{
  "backend": "openai",
  "model": "gpt-4.1-mini",
  "fallback_model": "gpt-4.1",
  "max_retries": 3,
  "retry_base_seconds": 1.5,
  "max_tokens": 4096,
  "require_auth": false,
  "rate_limit_per_minute": 120,
  "memory_backend": "inmemory",
  "enable_prometheus": true,
  "app_name": "PERFECT-AGENT"
}
```

#### POST /config/reload

Reload configuration from environment variables.

**Request:**
```bash
curl -X POST http://localhost:8000/config/reload
```

**Response:**
```json
{
  "status": "ok",
  "message": "Configuration reloaded"
}
```

### Token Management (Admin)

#### POST /tokens

Create a new API token.

**Request:**
```bash
curl -X POST http://localhost:8000/tokens \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "expiry_hours": 24,
    "metadata": {"role": "admin", "user": "admin@example.com"}
  }'
```

**Response:**
```json
{
  "status": "ok",
  "token": "generated-token-string",
  "expires_in": 86400
}
```

#### DELETE /tokens/{token}

Revoke an API token.

**Request:**
```bash
curl -X DELETE http://localhost:8000/tokens/token-to-revoke \
  -H "Authorization: Bearer admin-token"
```

**Response:**
```json
{
  "status": "ok",
  "message": "Token revoked"
}
```

### Monitoring

#### GET /metrics

Get Prometheus metrics.

**Request:**
```bash
curl http://localhost:8000/metrics
```

**Response:**
```
# HELP agent_requests_total Total number of requests
# TYPE agent_requests_total counter
agent_requests_total{endpoint="/health",method="GET",status_code="200",backend="openai"} 1
...
```

**Note:** Requires `AGENT_ENABLE_PROMETHEUS=true`

## Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| 400 | Bad Request | Check request format and parameters |
| 401 | Unauthorized | Provide valid Authorization header |
| 403 | Forbidden | Check permissions |
| 422 | Validation Error | Fix request validation errors |
| 429 | Rate Limited | Wait and retry |
| 500 | Internal Error | Check server logs |
| 502 | Bad Gateway | Check upstream services |
| 503 | Service Unavailable | Server is overloaded |

## Request Headers

| Header | Description | Required |
|--------|-------------|----------|
| `Authorization` | Bearer token for authentication | Yes (if auth enabled) |
| `Content-Type` | Request content type | Yes (for POST) |
| `X-User-ID` | User identifier for rate limiting | No |
| `X-Tenant-ID` | Tenant identifier for multi-tenancy | No |
| `X-Request-ID` | Request identifier for tracing | No |
| `X-Write-Confirm` | Confirmation for write operations | No |

## Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique request identifier |
| `Retry-After` | Seconds to wait before retry (429 only) |

## Rate Limiting

- **Algorithm:** Sliding window
- **Scope:** Per user (based on `X-User-ID` header or IP)
- **Default:** 120 requests per minute
- **Response:** 429 Too Many Requests with `Retry-After` header

## WebSocket Support

For streaming responses, the server supports WebSocket connections.

**Endpoint:** `ws://localhost:8000/ws`

**Protocol:** Standard WebSocket with JSON messages

## Examples

### Python Client Example

```python
import requests
import json

BASE_URL = "http://localhost:8000"
API_TOKEN = "your-api-token"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Health check
def health_check():
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    return response.json()

# Non-streaming invocation
def invoke_agent(messages):
    data = {
        "input": messages,
        "stream": False
    }
    response = requests.post(f"{BASE_URL}/invocations", headers=headers, json=data)
    return response.json()

# Streaming invocation
def invoke_agent_streaming(messages):
    data = {
        "input": messages,
        "stream": True
    }
    response = requests.post(f"{BASE_URL}/invocations", headers=headers, json=data, stream=True)
    
    for line in response.iter_lines():
        if line:
            yield json.loads(line.decode('utf-8'))

# Usage
messages = [
    {"role": "user", "content": "Hello, how are you?"}
]

# Non-streaming
result = invoke_agent(messages)
print(result)

# Streaming
for chunk in invoke_agent_streaming(messages):
    print(chunk)
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Non-streaming invocation
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-token" \
  -d '{"input": [{"role": "user", "content": "Hello"}], "stream": false}'

# Streaming invocation
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-token" \
  -d '{"input": [{"role": "user", "content": "Hello"}], "stream": true}' \
  --no-buffer
```

## WebSocket Example

```javascript
// JavaScript WebSocket client
const socket = new WebSocket('ws://localhost:8000/ws');

socket.onopen = () => {
  socket.send(JSON.stringify({
    input: [{role: 'user', content: 'Hello'}],
    stream: true
  }));
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

socket.onclose = () => {
  console.log('Connection closed');
};
```
