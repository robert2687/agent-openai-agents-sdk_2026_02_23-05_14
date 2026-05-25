# Command Reference

## Local/OpenAI setup

```bash
cp .env.example .env
uv sync
uv run verify-setup
uv run start-server --reload
```

Windows PowerShell for env file copy:

```powershell
Copy-Item .env.example .env
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

## Browser extension (Chrome + Edge)

```bash
# Package browser extension zip
uv run package-browser-extension
```

Load unpacked extension folder:

- Chrome: `chrome://extensions`
- Edge: `edge://extensions`
- Select `browser-extension/`

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

## Alias helpers

```bash
# Source aliases in your shell profile
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
