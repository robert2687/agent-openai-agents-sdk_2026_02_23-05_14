# Getting Started Checklist

## Local/OpenAI mode

- [ ] Install Python dependencies with `uv sync`
- [ ] Copy `.env.example` to `.env`
- [ ] Set `AGENT_BACKEND=openai`
- [ ] Set `OPENAI_API_KEY`
- [ ] Run `uv run verify-setup`
- [ ] Start the backend with `uv run start-server --reload`
- [ ] Check `http://localhost:8000/health`
- [ ] Send a test request to `POST /invocations`

## Optional local UI

- [ ] Run `docker compose up --build`
- [ ] Open the Gradio UI at `http://localhost:7860`

## Databricks mode

- [ ] Install Databricks CLI
- [ ] Install Node.js if you want the Databricks-style web app
- [ ] Run `uv run quickstart --backend databricks`
- [ ] Confirm Databricks auth works
- [ ] Confirm MLflow experiment setup is complete

## Verification

- [ ] `GET /health` returns `status=ok`
- [ ] `backend` matches your configured backend
- [ ] `databricks_tools_enabled=false` in OpenAI mode
- [ ] `POST /invocations` returns a valid response body

## Development loop

- [ ] Edit `agent_server/agent.py`
- [ ] Keep `uv run start-server --reload` running
- [ ] Re-run `uv run verify-setup` after environment changes
- [ ] Use `docker compose up --build` only when you want the optional local UI stack
   - Review OpenAI Agents SDK documentation
   - Contact your Databricks support team

## 🎉 Success

Once all items are checked, you have:

- ✅ A working Databricks OpenAI agent
- ✅ Local development environment
- ✅ Tracing and monitoring set up
- ✅ Ready to customize and deploy

**Happy building!** 🚀
