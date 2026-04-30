# Command Reference

## Local/OpenAI setup

```bash
cp .env.example .env
uv sync
uv run verify-setup
uv run start-server --reload
```

## Databricks setup

```bash
uv run quickstart --backend databricks
databricks auth profiles
```

## Local run commands

```bash
# Backend only
uv run start-server --reload

# Backend on a different port
uv run start-server --port 8001

# Optional local UI stack
docker compose up --build
```

## Health and API checks

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": "Hello"}]}'

curl -N -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": "Hello"}], "stream": true}'
```

## Dependency commands

```bash
uv sync
uv sync --upgrade
uv pip list
uv add <package-name>
```

## Test commands

```bash
uv run pytest tests/test_smoke_endpoints.py
uv run pytest
```

## Optional Databricks commands

```bash
databricks current-user me
databricks auth profiles
databricks experiments list
databricks apps logs <app-name>
```

## Important files

```text
.env
pyproject.toml
agent_server/agent.py
agent_server/start_server.py
verify_setup.py
docker-compose.yml
```

# Source the aliases
source ~/.bashrc

# Now use:
agent-start      # Start the agent
agent-dev        # Start in dev mode
agent-verify     # Verify setup
```

## 📚 Getting Help

```bash
# Command help
uv --help
databricks --help
databricks apps --help

# View documentation
cat README.md
cat QUICKSTART.md
cat ARCHITECTURE.md

# Check version
uv --version
databricks --version
python --version
node --version
```
