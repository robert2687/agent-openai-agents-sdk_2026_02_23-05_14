# perfect-agent

A production-ready, deterministic, tool-using assistant with a **Nemotron → Qwen → GPT-4.1** fallback chain.

Works on **Windows**, **macOS**, and **Linux**.

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
│       └── shell.py       # run_shell (cross-platform)
├── examples/
│   ├── analyze_repo.md
│   └── generate_docs.md
├── tests/
│   └── test_tools.py
├── .env.example
├── pyproject.toml
├── requirements.txt
├── run.ps1               # Windows PowerShell launcher
├── run.sh                # macOS / Linux bash launcher
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

Copy the template and edit in at least one API key:

```bash
cp .env.example .env
# Edit .env and fill in at least one of OPENROUTER_API_KEY or OPENAI_API_KEY
```

| Variable | Purpose | Required |
|---|---|---|
| `OPENROUTER_API_KEY` | Enables Nemotron & Qwen (primary models) | Recommended |
| `OPENAI_API_KEY` | Fallback to GPT-4.1 | Recommended |

### 3. Run

#### Windows (PowerShell)

```powershell
.\run.ps1                    # interactive REPL
.\run.ps1 -m "question"      # single message
.\run.ps1 -v -m "question"   # verbose
```

The `run.ps1` script will:
- Find Python 3 (checks `.venv\Scripts\python.exe`, then system `python`)
- Create `.env` from `.env.example` if missing
- Prompt to add API keys if none are configured
- Launch the agent

#### macOS / Linux (bash / zsh)

```bash
./run.sh                      # interactive REPL
./run.sh -m "question"        # single message
./run.sh -v -m "question"     # verbose
```

The `run.sh` script will:
- Find Python 3 (checks `.venv/bin/python`, then `python3`, then `python`)
- Create `.env` from `.env.example` if missing
- Prompt to add API keys if none are configured
- Launch the agent

#### Direct Python (any platform)

```bash
# Interactive REPL:
python agent/runner.py
# or (after pip install -e .):
perfect-agent

# Single-message scripting:
python agent/runner.py --message "List the files in the current directory"
perfect-agent -m "Summarize the README at https://example.com/README.md"

# Verbose debug output:
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
| `run_shell(cmd, ...)` | Execute a shell command (cross-platform) |

## Configuration

All settings can be overridden via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `PA_MAX_RETRIES` | `3` | Retries per model before fallback |
| `PA_RETRY_BASE_SECONDS` | `1.5` | Base delay for exponential back-off |
| `PA_MAX_TOOL_ROUNDS` | `10` | Max tool-calling rounds per request |
| `PA_SHELL_TIMEOUT` | `60` | Shell command timeout (seconds) |
| `PA_HTTP_TIMEOUT` | `20` | HTTP request timeout (seconds) |

## Platform Notes

### Windows
- Use **PowerShell** (5.1+ or PowerShell 7+) to run `run.ps1`
- Install Python from [python.org](https://python.org), the Microsoft Store, or via `winget install Python.Python.3.12`
- The shell tool (`run_shell`) uses `cmd.exe` under the hood, so batch files (`.bat`, `.cmd`) and Windows CLI syntax work natively
- File paths use backslashes (`\`) — the `run_shell` tool handles this automatically when you pass commands as strings

### macOS
- Use **Terminal** (bash or zsh) to run `./run.sh`
- Install Python from [python.org](https://python.org) or via Homebrew: `brew install python@3.12`
- The shell tool uses your default shell (`/bin/zsh` on macOS 10.15+)
- The `run.sh` launcher uses `sed -i ''` (BSD sed) for in-place `.env` editing

### Linux
- Use any terminal (bash, zsh, dash) to run `./run.sh`
- Install Python via your package manager: `sudo apt install python3 python3-pip` (Debian/Ubuntu), `sudo dnf install python3` (Fedora), or `sudo pacman -S python` (Arch)
- The shell tool uses your default shell (`/bin/sh`), so all standard POSIX commands work
- The `run.sh` launcher uses GNU `sed -i` for in-place `.env` editing

## Running Tests

```bash
pip install pytest
pytest tests/
```

## Examples

See [`examples/`](examples/) for ready-made prompts:
- [`analyze_repo.md`](examples/analyze_repo.md) — architecture analysis
- [`generate_docs.md`](examples/generate_docs.md) — documentation generation
