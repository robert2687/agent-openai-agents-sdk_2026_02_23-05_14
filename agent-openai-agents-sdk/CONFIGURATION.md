# Configuration Guide

This document provides comprehensive configuration options for the Agent OpenAI Agents SDK.

## Overview

The Agent OpenAI Agents SDK can be configured through:

1. **Environment variables** (recommended for production)
2. **`.env` file** (recommended for development)
3. **Command-line arguments** (limited options)

## Environment Variables

### Core Settings

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `AGENT_BACKEND` | `openai` | Backend to use: `openai` or `databricks` | No |
| `AGENT_MODEL` | `gpt-4.1-mini` | Primary model to use | No |
| `AGENT_FALLBACK_MODEL` | `gpt-4.1` | Fallback model when primary fails | No |
| `AGENT_MAX_RETRIES` | `3` | Maximum number of retry attempts | No |
| `AGENT_RETRY_BASE_SECONDS` | `1.5` | Base delay for exponential backoff (seconds) | No |
| `AGENT_MAX_TOKENS` | `4096` | Maximum tokens per response | No |

### Authentication Settings

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `AGENT_REQUIRE_AUTH` | `0` | Require authentication: `1` for yes, `0` for no | No |
| `AGENT_API_TOKEN` | `""` | API token for Bearer authentication | No |

### Rate Limiting

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `AGENT_RATE_LIMIT_PER_MINUTE` | `120` | Requests per minute per user | No |
| `REDIS_URL` | `None` | Redis URL for distributed rate limiting | No |

### Memory Store Settings

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `MEMORY_BACKEND` | `inmemory` | Memory backend: `inmemory` or `cosmos` | No |
| `AGENT_MEMORY_TENANT` | `default-tenant` | Default tenant ID for memory | No |
| `AGENT_MEMORY_USER` | `default-user` | Default user ID for memory | No |

### Cosmos DB Settings (for `MEMORY_BACKEND=cosmos`)

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `COSMOS_ENDPOINT` | `None` | Cosmos DB endpoint URL | Yes (if using Cosmos) |
| `COSMOS_KEY` | `None` | Cosmos DB access key | Yes (if using Cosmos) |
| `COSMOS_DATABASE` | `None` | Cosmos DB database name | Yes (if using Cosmos) |
| `COSMOS_CONTAINER` | `None` | Cosmos DB container name | Yes (if using Cosmos) |

### OpenAI Settings

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `OPENAI_API_KEY` | `None` | OpenAI API key | Yes (if using OpenAI) |
| `OPENAI_ADMIN_KEY` | `None` | OpenAI admin key (alternative) | No |
| `OPENAI_BASE_URL` | `None` | Custom OpenAI API base URL | No |
| `OPENROUTER_API_KEY` | `None` | OpenRouter API key | No |

### Databricks Settings (for `AGENT_BACKEND=databricks`)

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `DATABRICKS_HOST` | `None` | Databricks workspace host | Yes (if using Databricks) |
| `DATABRICKS_TOKEN` | `None` | Databricks personal access token | Yes (if using Databricks) |
| `DATABRICKS_CONFIG_PROFILE` | `None` | Databricks CLI profile name | No |

### MLflow Settings

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `MLFLOW_TRACKING_URI` | `sqlite:///mlflow.db` | MLflow tracking URI | No |
| `MLFLOW_REGISTRY_URI` | `None` | MLflow registry URI | No |
| `MLFLOW_EXPERIMENT_ID` | `None` | MLflow experiment ID | No |
| `AGENT_ENABLE_MLFLOW_AUTOLOG` | `0` | Enable MLflow autologging: `1` for yes, `0` for no | No |

### App Identity

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `APP_NAME` | `PERFECT-AGENT` | Application name | No |
| `APP_URL` | `https://github.com/robert2687` | Application URL | No |

### Networking

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `API_PORT` | `8000` | API server port | No |
| `UI_PORT` | `7860` | UI server port | No |

### Monitoring

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `AGENT_ENABLE_PROMETHEUS` | `0` | Enable Prometheus metrics: `1` for yes, `0` for no | No |

## .env File Example

```bash
# Copy the example file to create your configuration
cp .env.example .env

# Edit .env with your settings
nano .env
```

### Example .env File

```ini
# ============================================================================
# Core Settings
# ============================================================================
AGENT_BACKEND=openai
AGENT_MODEL=gpt-4.1-mini
AGENT_FALLBACK_MODEL=gpt-4.1
AGENT_MAX_RETRIES=3
AGENT_RETRY_BASE_SECONDS=1.5
AGENT_MAX_TOKENS=4096

# ============================================================================
# Authentication
# ============================================================================
AGENT_REQUIRE_AUTH=1
AGENT_API_TOKEN=your-secure-api-token-here

# ============================================================================
# Rate Limiting
# ============================================================================
AGENT_RATE_LIMIT_PER_MINUTE=120
REDIS_URL=redis://localhost:6379/0

# ============================================================================
# Memory Store
# ============================================================================
MEMORY_BACKEND=inmemory
AGENT_MEMORY_TENANT=default-tenant
AGENT_MEMORY_USER=default-user

# For Cosmos DB (uncomment to use)
# MEMORY_BACKEND=cosmos
# COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
# COSMOS_KEY=your-cosmos-primary-key
# COSMOS_DATABASE=agent-db
# COSMOS_CONTAINER=messages

# ============================================================================
# OpenAI Settings
# ============================================================================
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=
OPENROUTER_API_KEY=your-openrouter-api-key

# ============================================================================
# Databricks Settings (for AGENT_BACKEND=databricks)
# ============================================================================
# DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
# DATABRICKS_TOKEN=your-personal-access-token
# DATABRICKS_CONFIG_PROFILE=DEFAULT

# ============================================================================
# MLflow Settings
# ============================================================================
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MLFLOW_REGISTRY_URI=
MLFLOW_EXPERIMENT_ID=
AGENT_ENABLE_MLFLOW_AUTOLOG=0

# ============================================================================
# App Identity
# ============================================================================
APP_NAME=PERFECT-AGENT
APP_URL=https://github.com/robert2687

# ============================================================================
# Networking
# ============================================================================
API_PORT=8000
UI_PORT=7860

# ============================================================================
# Monitoring
# ============================================================================
AGENT_ENABLE_PROMETHEUS=1
```

## Configuration Profiles

### Development Profile

```ini
AGENT_BACKEND=openai
AGENT_MODEL=gpt-4.1-mini
AGENT_REQUIRE_AUTH=0
AGENT_ENABLE_PROMETHEUS=1
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
```

### Production Profile

```ini
AGENT_BACKEND=openai
AGENT_MODEL=gpt-4.1
AGENT_FALLBACK_MODEL=gpt-4.1
AGENT_MAX_RETRIES=5
AGENT_RETRY_BASE_SECONDS=2.0
AGENT_REQUIRE_AUTH=1
AGENT_API_TOKEN=secure-random-token
AGENT_RATE_LIMIT_PER_MINUTE=60
REDIS_URL=redis://your-redis-server:6379/0
MEMORY_BACKEND=cosmos
COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
COSMOS_KEY=your-cosmos-key
COSMOS_DATABASE=agent-db
COSMOS_CONTAINER=messages
AGENT_ENABLE_PROMETHEUS=1
MLFLOW_TRACKING_URI=postgresql://user:pass@localhost:5432/mlflow
```

### Databricks Profile

```ini
AGENT_BACKEND=databricks
AGENT_MODEL=databricks-gpt-5-2
AGENT_FALLBACK_MODEL=databricks-gpt-5-2
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your-personal-access-token
AGENT_REQUIRE_AUTH=1
AGENT_API_TOKEN=your-api-token
```

## Configuration Management

### Reloading Configuration

Configuration can be reloaded without restarting the server:

```bash
# Send POST request to reload endpoint
curl -X POST http://localhost:8000/config/reload

# Or use the reload command
uv run config-reload
```

### Environment Variable Priority

The configuration system uses the following priority order:

1. **Explicit environment variables** (highest priority)
2. **`.env` file** in the current directory
3. **`.env` file** in the project root
4. **Default values** (lowest priority)

### Using Multiple .env Files

You can use multiple `.env` files for different environments:

```bash
# Development
cp .env.development .env

# Production
cp .env.production .env

# Test
cp .env.test .env
```

## Security Best Practices

### API Token Management

1. **Never commit API tokens** to version control
2. **Use environment variables** for sensitive data
3. **Rotate tokens regularly**
4. **Use different tokens** for different environments
5. **Limit token permissions** to only what's needed

### Example: Using secrets in GitHub Actions

```yaml
# .github/workflows/ci.yml
jobs:
  deploy:
    steps:
      - name: Deploy
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          AGENT_API_TOKEN: ${{ secrets.AGENT_API_TOKEN }}
        run: |
          echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> .env
          echo "AGENT_API_TOKEN=${AGENT_API_TOKEN}" >> .env
          uv run start-server
```

## Performance Tuning

### Rate Limiting

```ini
# For high-traffic applications
AGENT_RATE_LIMIT_PER_MINUTE=1000
REDIS_URL=redis://your-redis-cluster:6379/0
```

### Retry Configuration

```ini
# For unreliable networks
AGENT_MAX_RETRIES=5
AGENT_RETRY_BASE_SECONDS=2.0
```

### Token Limits

```ini
# For long conversations
AGENT_MAX_TOKENS=8192
```

## Monitoring Configuration

### Prometheus Metrics

```ini
# Enable Prometheus metrics
AGENT_ENABLE_PROMETHEUS=1
```

### Grafana Dashboard

Import the provided Grafana dashboard configuration:

```bash
# Copy dashboard to Grafana provisioning directory
cp monitoring/grafana/provisioning/dashboards/agent-dashboard.json \
   /etc/grafana/provisioning/dashboards/

# Restart Grafana
grafana-cli plugins install
systemctl restart grafana-server
```

## Troubleshooting

### Common Issues

1. **Configuration not loading**
   - Check that `.env` file exists in the working directory
   - Verify file permissions
   - Ensure environment variables are properly set

2. **Invalid configuration values**
   - Check for typos in variable names
   - Verify that values meet validation requirements
   - Review error messages for specific issues

3. **Missing required variables**
   - Set all required variables for your backend
   - Check the documentation for required variables

### Debugging Configuration

```python
# Check loaded configuration
from agent_server.config import get_config

config = get_config()
print(f"Backend: {config.backend}")
print(f"Model: {config.model}")
print(f"Auth required: {config.require_auth}")
```

### Validation Errors

If configuration validation fails, you'll see errors like:

```
ValueError: backend must be one of {'openai', 'databricks'}, got 'invalid'
ValueError: max_retries must be >= 1 and <= 10, got 0
```

Fix the invalid values in your configuration.

## Migration Guide

### From v0.1.0 to v0.2.0

The v0.2.0 release introduces several breaking changes:

1. **Configuration system**
   - Old: Individual environment variables
   - New: Centralized configuration with validation

2. **Authentication**
   - Old: Simple token check
   - New: Token manager with rotation and expiry support

3. **Rate limiting**
   - Old: In-memory only
   - New: Redis support for distributed deployments

### Migration Steps

1. **Update environment variables**
   - Review the new configuration options
   - Update your `.env` files

2. **Update authentication**
   - If using API tokens, they will continue to work
   - Consider using the new token management endpoints

3. **Update rate limiting**
   - For distributed deployments, configure `REDIS_URL`
   - The default in-memory rate limiter remains unchanged

## Configuration Reference

### All Available Variables

```ini
# Core
AGENT_BACKEND
AGENT_MODEL
AGENT_FALLBACK_MODEL
AGENT_MAX_RETRIES
AGENT_RETRY_BASE_SECONDS
AGENT_MAX_TOKENS

# Authentication
AGENT_REQUIRE_AUTH
AGENT_API_TOKEN

# Rate Limiting
AGENT_RATE_LIMIT_PER_MINUTE
REDIS_URL

# Memory
MEMORY_BACKEND
AGENT_MEMORY_TENANT
AGENT_MEMORY_USER
COSMOS_ENDPOINT
COSMOS_KEY
COSMOS_DATABASE
COSMOS_CONTAINER

# OpenAI
OPENAI_API_KEY
OPENAI_ADMIN_KEY
OPENAI_BASE_URL
OPENROUTER_API_KEY

# Databricks
DATABRICKS_HOST
DATABRICKS_TOKEN
DATABRICKS_CONFIG_PROFILE

# MLflow
MLFLOW_TRACKING_URI
MLFLOW_REGISTRY_URI
MLFLOW_EXPERIMENT_ID
AGENT_ENABLE_MLFLOW_AUTOLOG

# App
APP_NAME
APP_URL

# Networking
API_PORT
UI_PORT

# Monitoring
AGENT_ENABLE_PROMETHEUS
```

## Support

For configuration issues:

1. **Check the documentation** - This file and the README
2. **Review error messages** - They often contain specific guidance
3. **Validate your configuration** - Use the `/config` endpoint
4. **Check logs** - Server logs often contain configuration warnings
5. **Open an issue** - If you're still stuck, open a GitHub issue

## Examples

### Minimal Configuration (Development)

```ini
AGENT_BACKEND=openai
OPENAI_API_KEY=your-api-key
```

### Full Configuration (Production)

```ini
# Core
AGENT_BACKEND=openai
AGENT_MODEL=gpt-4.1
AGENT_FALLBACK_MODEL=gpt-4.1
AGENT_MAX_RETRIES=5
AGENT_RETRY_BASE_SECONDS=2.0
AGENT_MAX_TOKENS=8192

# Authentication
AGENT_REQUIRE_AUTH=1
AGENT_API_TOKEN=secure-random-token

# Rate Limiting
AGENT_RATE_LIMIT_PER_MINUTE=1000
REDIS_URL=redis://your-redis:6379/0

# Memory
MEMORY_BACKEND=cosmos
COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
COSMOS_KEY=your-cosmos-key
COSMOS_DATABASE=agent-db
COSMOS_CONTAINER=messages

# OpenAI
OPENAI_API_KEY=your-openai-key
OPENROUTER_API_KEY=your-openrouter-key

# Monitoring
AGENT_ENABLE_PROMETHEUS=1

# Networking
API_PORT=8000
UI_PORT=7860
```
