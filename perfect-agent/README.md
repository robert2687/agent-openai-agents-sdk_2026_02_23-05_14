# perfect-agent

A production-ready, deterministic, tool-using assistant with a **Nemotron → Qwen → GPT-4.1** fallback chain.

## Structure

```text
perfect-agent/
├── agent/
│   ├── __init__.py
│   ├── config.py          # env-based configuration
│   ├── fallback_client.py # model fallback chain with retry
│   ├── runner.py          # CLI entry point & tool-calling loop
│   ├── system_prompt.txt
│   └── tools/
│       ├── file.py        # read, write, append, delete, list_dir
│       ├── http.py        # http_get, http_post
│       └── shell.py       # run_shell (with working_dir support)
├── examples/
│   ├── analyze_repo.md
│   └── generate_docs.md
├── tests/
│   └── test_tools.py
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install dependencies

```bash
cd perfect-agent
pip install -r requirements.txt
# or install as a package with the CLI entry point:
pip install -e .
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in at least one of OPENROUTER_API_KEY or OPENAI_API_KEY
```

| Variable | Purpose | Required |
|---|---|---|
| `OPENROUTER_API_KEY` | Enables Nemotron & Qwen (primary models) | Recommended |
| `OPENAI_API_KEY` | Fallback to GPT-4.1 | Recommended |

### 3. Run

**Interactive REPL:**
```bash
python agent/runner.py
# or (after pip install -e .):
perfect-agent
```

**Single-message scripting:**
```bash
python agent/runner.py --message "List the files in the current directory"
perfect-agent -m "Summarize the README at https://example.com/README.md"
```

**Verbose debug output:**
```bash
perfect-agent --verbose --message "Run: echo hello"
```

## Model Fallback Chain

```
OpenRouter → nvidia/nemotron-3-super-120b-a12b:free   (free, fastest)
         ↓ (on failure)
OpenRouter → qwen/qwen-2.5-72b-instruct               (high quality)
         ↓ (on failure)
OpenAI   → gpt-4.1                                    (reliable fallback)
```

Each model is retried up to `PA_MAX_RETRIES` times (default 3) with exponential back-off before moving to the next.

## Available Tools

| Tool | Description |
|---|---|
| `read_file(path)` | Read a file's content |
| `write_file(path, content)` | Write/overwrite a file |
| `append_file(path, content)` | Append to a file |
| `delete_file(path)` | Delete a file |
| `list_dir(path)` | List directory contents |
| `http_get(url, ...)` | HTTP GET request |
| `http_post(url, json_body, ...)` | HTTP POST request |
| `run_shell(cmd, ...)` | Execute a shell command |

## Configuration

All settings can be overridden via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `PA_MAX_RETRIES` | `3` | Retries per model before fallback |
| `PA_RETRY_BASE_SECONDS` | `1.5` | Base delay for exponential back-off |
| `PA_MAX_TOOL_ROUNDS` | `10` | Max tool-calling rounds per request |
| `PA_SHELL_TIMEOUT` | `60` | Shell command timeout (seconds) |
| `PA_HTTP_TIMEOUT` | `20` | HTTP request timeout (seconds) |

## Running Tests

```bash
pip install pytest
pytest tests/
```

## Examples

See [`examples/`](examples/) for ready-made prompts:
- [`analyze_repo.md`](examples/analyze_repo.md) — architecture analysis
- [`generate_docs.md`](examples/generate_docs.md) — documentation generation

