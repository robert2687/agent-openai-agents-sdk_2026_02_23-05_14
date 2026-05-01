"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# ── Model chain ──────────────────────────────────────────────────────────────
NEMOTRON_MODEL: str = os.getenv(
    "PA_NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"
)
QWEN_MODEL: str = os.getenv("PA_QWEN_MODEL", "qwen/qwen-2.5-72b-instruct")
OPENAI_MODEL: str = os.getenv("PA_OPENAI_MODEL", "gpt-4.1")

# ── API keys / endpoints ──────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL") or None

APP_URL: str = os.getenv("APP_URL", "https://github.com/robert2687")
APP_NAME: str = os.getenv("APP_NAME", "PERFECT-AGENT")

# ── Retry / resilience ────────────────────────────────────────────────────────
MAX_RETRIES: int = max(1, _int("PA_MAX_RETRIES", 3))
RETRY_BASE_SECONDS: float = max(0.1, _float("PA_RETRY_BASE_SECONDS", 1.5))
MAX_TOOL_ROUNDS: int = max(1, _int("PA_MAX_TOOL_ROUNDS", 10))

# ── Shell ─────────────────────────────────────────────────────────────────────
SHELL_TIMEOUT: int = max(5, _int("PA_SHELL_TIMEOUT", 60))

# ── HTTP ──────────────────────────────────────────────────────────────────────
HTTP_TIMEOUT: int = max(5, _int("PA_HTTP_TIMEOUT", 20))
