"""Fallback LLM client: Nemotron (OpenRouter) → Qwen (OpenRouter) → GPT-4.1 (OpenAI).

Each provider is tried in order; the first successful response is returned.
All errors are logged and suppressed until all options are exhausted.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

from openai import OpenAI

from agent import config

LOGGER = logging.getLogger(__name__)

# Ordered fallback chain: (provider_name, model_id)
_FALLBACK_CHAIN: list[tuple[str, str]] = [
    ("openrouter", config.NEMOTRON_MODEL),
    ("openrouter", config.QWEN_MODEL),
    ("openai", config.OPENAI_MODEL),
]


def check_api_keys() -> None:
    """Raise a friendly RuntimeError if no API keys are configured."""
    has_openrouter = bool(config.OPENROUTER_API_KEY)
    has_openai = bool(config.OPENAI_API_KEY)
    if has_openrouter or has_openai:
        return

    msg = (
        "\n"
        "╔══════════════════════════════════════════════════════════╗\n"
        "║          PERFECT-AGENT — API KEY REQUIRED                ║\n"
        "╠══════════════════════════════════════════════════════════╣\n"
        "║  No API key found. Add at least ONE key to your .env:    ║\n"
        "║                                                          ║\n"
        "║  Option A – OpenRouter (free, recommended):              ║\n"
        "║    OPENROUTER_API_KEY=sk-or-...                          ║\n"
        "║    → Get a free key at https://openrouter.ai/keys        ║\n"
        "║                                                          ║\n"
        "║  Option B – OpenAI:                                      ║\n"
        "║    OPENAI_API_KEY=sk-...                                  ║\n"
        "║    → Get a key at https://platform.openai.com/api-keys   ║\n"
        "║                                                          ║\n"
        "║  Then edit perfect-agent/.env and restart.               ║\n"
        "╚══════════════════════════════════════════════════════════╝\n"
    )
    print(msg, file=sys.stderr)
    raise RuntimeError("No API key configured. See message above.")


def _make_clients() -> dict[str, OpenAI]:
    clients: dict[str, OpenAI] = {}

    if config.OPENROUTER_API_KEY:
        clients["openrouter"] = OpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": config.APP_URL,
                "X-Title": config.APP_NAME,
            },
        )

    if config.OPENAI_API_KEY:
        kwargs: dict[str, Any] = {"api_key": config.OPENAI_API_KEY}
        if config.OPENAI_BASE_URL:
            kwargs["base_url"] = config.OPENAI_BASE_URL
        clients["openai"] = OpenAI(**kwargs)

    return clients


def fallback_chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    *,
    temperature: float = 0.2,
):
    """Send *messages* to the first available model in the fallback chain.

    Parameters
    ----------
    messages:    OpenAI-format message list.
    tools:       Optional tool definitions (function-calling schema).
    temperature: Sampling temperature (default 0.2 for determinism).

    Returns
    -------
    openai.types.chat.ChatCompletion

    Raises
    ------
    RuntimeError if every provider in the chain fails.
    """
    clients = _make_clients()

    if not clients:
        check_api_keys()  # raises with a friendly message

    last_error: Exception | None = None

    for provider, model in _FALLBACK_CHAIN:
        client = clients.get(provider)
        if client is None:
            LOGGER.debug("Skipping %s/%s — no API key configured.", provider, model)
            continue

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = client.chat.completions.create(**kwargs)
                if attempt > 1 or provider != _FALLBACK_CHAIN[0][0]:
                    LOGGER.info("Succeeded with %s/%s (attempt %d)", provider, model, attempt)
                return response

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < config.MAX_RETRIES:
                    delay = config.RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    LOGGER.warning(
                        "Model %s/%s failed (attempt %d/%d). Retrying in %.1fs. Error: %s",
                        provider,
                        model,
                        attempt,
                        config.MAX_RETRIES,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                else:
                    LOGGER.warning(
                        "Model %s/%s exhausted all %d attempts. Error: %s",
                        provider,
                        model,
                        config.MAX_RETRIES,
                        exc,
                    )

    raise RuntimeError(
        f"All models in fallback chain failed. Last error: {last_error}"
    )
    clients: dict[str, OpenAI] = {}

    if config.OPENROUTER_API_KEY:
        clients["openrouter"] = OpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": config.APP_URL,
                "X-Title": config.APP_NAME,
            },
        )

    if config.OPENAI_API_KEY:
        kwargs: dict[str, Any] = {"api_key": config.OPENAI_API_KEY}
        if config.OPENAI_BASE_URL:
            kwargs["base_url"] = config.OPENAI_BASE_URL
        clients["openai"] = OpenAI(**kwargs)

    return clients


def fallback_chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    *,
    temperature: float = 0.2,
):
    """Send *messages* to the first available model in the fallback chain.

    Parameters
    ----------
    messages:    OpenAI-format message list.
    tools:       Optional tool definitions (function-calling schema).
    temperature: Sampling temperature (default 0.2 for determinism).

    Returns
    -------
    openai.types.chat.ChatCompletion

    Raises
    ------
    RuntimeError if every provider in the chain fails.
    """
    clients = _make_clients()
    last_error: Exception | None = None

    for provider, model in _FALLBACK_CHAIN:
        client = clients.get(provider)
        if client is None:
            LOGGER.debug("Skipping %s/%s — no API key configured.", provider, model)
            continue

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = client.chat.completions.create(**kwargs)
                if attempt > 1 or provider != _FALLBACK_CHAIN[0][0]:
                    LOGGER.info("Succeeded with %s/%s (attempt %d)", provider, model, attempt)
                return response

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < config.MAX_RETRIES:
                    delay = config.RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    LOGGER.warning(
                        "Model %s/%s failed (attempt %d/%d). Retrying in %.1fs. Error: %s",
                        provider,
                        model,
                        attempt,
                        config.MAX_RETRIES,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                else:
                    LOGGER.warning(
                        "Model %s/%s exhausted all %d attempts. Error: %s",
                        provider,
                        model,
                        config.MAX_RETRIES,
                        exc,
                    )

    raise RuntimeError(
        f"All models in fallback chain failed. Last error: {last_error}"
    )
