#!/usr/bin/env bash
# run.sh — Launch PERFECT-AGENT on macOS / Linux
#
# Usage (from the perfect-agent directory):
#   ./run.sh                      # interactive REPL
#   ./run.sh -m "question"        # single message
#   ./run.sh -v -m "question"     # verbose

set -euo pipefail

# ── Argument parsing ──────────────────────────────────────────────────────────
MESSAGE=""
VERBOSE=false

while getopts ":m:v" opt; do
  case "$opt" in
    m) MESSAGE="$OPTARG" ;;
    v) VERBOSE=true ;;
    \?) echo "Usage: $0 [-m message] [-v]" >&2; exit 1 ;;
  esac
done

# ── Find Python ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer the project's own virtual environment if it exists.
VENV_PY="$SCRIPT_DIR/.venv/bin/python"

PY=""
for candidate in "$VENV_PY" "python3" "python"; do
  if command -v "$candidate" &>/dev/null; then
    v="$("$candidate" --version 2>&1 || true)"
    if echo "$v" | grep -q "Python 3"; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "ERROR: Python 3 not found." >&2
  echo "Venv checked: $VENV_PY" >&2
  exit 1
fi

echo "Python: $PY"

# ── Check / create .env ──────────────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo ".env created from .env.example"
fi

# Read current key values
OR_KEY=""
OA_KEY=""
if [ -f "$ENV_FILE" ]; then
  OR_KEY="$(grep -E '^OPENROUTER_API_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  OA_KEY="$(grep -E '^OPENAI_API_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
fi

if [ -z "$OR_KEY" ] && [ -z "$OA_KEY" ]; then
  echo ""
  echo "No API key found in .env!"
  echo ""
  echo "Option A (free) - OpenRouter: https://openrouter.ai/keys"
  echo "Option B        - OpenAI:     https://platform.openai.com/api-keys"
  echo ""
  printf "[O]penRouter / [A]I / [S]kip: "
  read -r choice

  case "$choice" in
    [Oo]*)
      printf "Paste OpenRouter key (sk-or-...): "
      read -r key
      if [ -n "$key" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
          sed -i '' "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$key|" "$ENV_FILE"
        else
          sed -i "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$key|" "$ENV_FILE"
        fi
        echo "Saved."
      fi
      ;;
    [Aa]*)
      printf "Paste OpenAI key (sk-...): "
      read -r key
      if [ -n "$key" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
          sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$key|" "$ENV_FILE"
        else
          sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$key|" "$ENV_FILE"
        fi
        echo "Saved."
      fi
      ;;
    *)
      echo "Edit '$ENV_FILE' then re-run ./run.sh"
      exit 0
      ;;
  esac
fi

# ── Build argument list and launch ───────────────────────────────────────────
SCRIPT="$SCRIPT_DIR/agent/runner.py"
ARGS=()

if [ "$VERBOSE" = true ]; then
  ARGS+=("--verbose")
fi

if [ -n "$MESSAGE" ]; then
  ARGS+=("--message" "$MESSAGE")
fi

echo ""
exec "$PY" "$SCRIPT" "${ARGS[@]}"
