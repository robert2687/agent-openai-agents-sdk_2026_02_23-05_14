# Responses API Agent

This project now supports a real local-first workflow.

- Local/OpenAI mode is the default path and does not require Databricks.
- Databricks mode remains available for Databricks-authenticated tools and deployment.

The backend exposes an MLflow ResponsesAgent-compatible API, a health endpoint, retry and fallback model controls, and an optional local UI stack via Docker Compose.

## Local/OpenAI quick start

### Works on Windows, macOS, and Linux

Use the same runtime commands on every OS:

- `uv sync`
- `uv run verify-setup`
- `uv run start-server --reload`

Environment file copy examples:

- macOS/Linux: `cp .env.example .env`
- Windows PowerShell: `Copy-Item .env.example .env`

```bash
cp .env.example .env
# set OPENAI_API_KEY in .env
uv sync
uv run verify-setup
uv run start-server --reload
```

Check the service:

```bash
curl http://localhost:8000/health
```

Optional local UI stack:

```bash
docker compose up --build
```

## Browser extension (Chrome + Edge)

This repository now includes a Chromium WebExtension in [`browser-extension/`](./browser-extension/).

Load unpacked in:

- Chrome: `chrome://extensions`
- Edge: `edge://extensions`

Package a distributable zip:

```bash
uv run package-browser-extension
```

See full instructions in [`browser-extension/README.md`](./browser-extension/README.md).

## Databricks quick start

Use this only if you want Databricks features:

```bash
uv run quickstart --backend databricks
```

## Runtime behavior

- `AGENT_BACKEND=openai` uses `OPENAI_API_KEY` and skips Databricks imports and auth.
- `AGENT_BACKEND=databricks` enables Databricks MCP integration when the optional dependencies are installed.
- `GET /health` reports backend, Databricks tool availability, active model, fallback model, and retry settings.

## Main entrypoints

- `uv run start-server --reload`: recommended local backend
- `docker compose up --build`: local API + Gradio UI
- `uv run quickstart --backend databricks`: optional Databricks setup

## Docs

- [QUICKSTART.md](./QUICKSTART.md)
- [CHECKLIST.md](./CHECKLIST.md)
- [COMMANDS.md](./COMMANDS.md)
- [API.md](./API.md)
   ```

   - Example streaming request:

     ```bash
     curl -X POST http://localhost:8000/invocations \
     -H "Content-Type: application/json" \
     -d '{ "input": [{ "role": "user", "content": "hi" }], "stream": true }'
     ```

   - Example non-streaming request:

     ```bash
     curl -X POST http://localhost:8000/invocations  \
     -H "Content-Type: application/json" \
     -d '{ "input": [{ "role": "user", "content": "hi" }] }'
     ```

## Modifying your agent

See the [OpenAI Agents SDK documentation](https://platform.openai.com/docs/guides/agents-sdk) for more information on how to edit your own agent.

Required files for hosting with MLflow `AgentServer`:

- `agent.py`: Contains your agent logic. Modify this file to create your custom agent. For example, you can [add agent tools](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-tool) to give your agent additional capabilities
- `start_server.py`: Initializes and runs the MLflow `AgentServer` with agent_type="ResponsesAgent". You don't have to modify this file for most common use cases, but can add additional server routes (e.g. a `/metrics` endpoint) here

**Common customization questions:**

**Q: Can I add additional files or folders to my agent?**
Yes. Add additional files or folders as needed. Ensure the script within `pyproject.toml` runs the correct script that starts the server and sets up MLflow tracing.

**Q: How do I add dependencies to my agent?**
Run `uv add <package_name>` (e.g., `uv add "mlflow-skinny[databricks]"`). See the [python pyproject.toml guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#dependencies-and-requirements).

**Q: Can I add custom tracing beyond the built-in tracing?**
Yes. This template uses MLflow's agent server, which comes with automatic tracing for agent logic decorated with `@invoke()` and `@stream()`. It also uses [MLflow autologging APIs](https://mlflow.org/docs/latest/genai/tracing/#one-line-auto-tracing-integrations) to capture traces from LLM invocations. However, you can add additional instrumentation to capture more granular trace information when your agent runs. See the [MLflow tracing documentation](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/app-instrumentation/).

**Q: How can I extend this example with additional tools and capabilities?**
This template can be extended by integrating additional MCP servers, Vector Search Indexes, UC Functions, and other Databricks tools. See the ["Agent Framework Tools Documentation"](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-tool).

## Evaluating your agent

Evaluate your agent by calling the invoke function you defined for the agent locally.

- Update your `evaluate_agent.py` file with the preferred evaluation dataset and scorers.

Run the evaluation using the evaluation script:

```bash
uv run agent-evaluate
```

After it completes, open the MLflow UI link for your experiment to inspect results.

## Deploying to Databricks Apps

0. **Create a Databricks App**:
   Ensure you have the [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/tutorial) installed and configured.

   ```bash
   databricks apps create agent-openai-agents-sdk
   ```

1. **Set up authentication to Databricks resources**

   For this example, you need to add an MLflow Experiment as a resource to your app. Grant the App's Service Principal (SP) permission to edit the experiment by clicking `edit` on your app home page. See the [Databricks Apps MLflow experiment documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/mlflow) for more information.

   To grant access to other resources like serving endpoints, genie spaces, UC Functions, and Vector Search Indexes, click `edit` on your app home page to grant the App's SP permission. See the [Databricks Apps resources documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/resources).

   For resources that are not supported yet, see the [Agent Framework authentication documentation](https://docs.databricks.com/aws/en/generative-ai/agent-framework/deploy-agent#automatic-authentication-passthrough) for the correct permission level to grant to your app SP.

   **On-behalf-of (OBO) User Authentication**: Use `get_user_workspace_client()` from `agent_server.utils` to authenticate as the requesting user instead of the app service principal. See the [OBO authentication documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth?language=Streamlit#retrieve-user-authorization-credentials).

2. **Sync local files to your workspace**

   See the [Databricks Apps deploy documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy?language=Databricks+CLI#deploy-the-app).

   ```bash
   DATABRICKS_USERNAME=$(databricks current-user me | jq -r .userName)
   databricks sync . "/Users/$DATABRICKS_USERNAME/agent-openai-agents-sdk"
   ```

3. **Deploy your Databricks App**

   See the [Databricks Apps deploy documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy?language=Databricks+CLI#deploy-the-app).

   ```bash
   databricks apps deploy agent-openai-agents-sdk --source-code-path /Workspace/Users/$DATABRICKS_USERNAME/agent-openai-agents-sdk
   ```

4. **Query your agent hosted on Databricks Apps**

   Databricks Apps are _only_ queryable via OAuth token. You cannot use a PAT to query your agent. Generate an [OAuth token with your credentials using the Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/authentication#u2m-auth):

   ```bash
   databricks auth login --host <https://host.databricks.com>
   databricks auth token
   ```

   Send a request to the `/invocations` endpoint:

   - Example streaming request:

     ```bash
     curl -X POST <app-url.databricksapps.com>/invocations \
        -H "Authorization: Bearer <oauth token>" \
        -H "Content-Type: application/json" \
        -d '{ "input": [{ "role": "user", "content": "hi" }], "stream": true }'
     ```

   - Example non-streaming request:

     ```bash
     curl -X POST <app-url.databricksapps.com>/invocations \
        -H "Authorization: Bearer <oauth token>" \
        -H "Content-Type: application/json" \
        -d '{ "input": [{ "role": "user", "content": "hi" }] }'
     ```

For future updates to the agent, sync and redeploy your agent.

### FAQ

- For a streaming response, I see a 200 OK in the logs, but an error in the actual stream. What's going on?
  - This is expected behavior. The initial 200 OK confirms stream setup; streaming errors don't affect this status.
- When querying my agent, I get a 302 error. What's going on?
  - Use an OAuth token. PATs are not supported for querying agents.
