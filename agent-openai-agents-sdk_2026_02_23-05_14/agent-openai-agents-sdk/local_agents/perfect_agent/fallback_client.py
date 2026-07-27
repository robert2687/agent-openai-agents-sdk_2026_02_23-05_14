"""Enhanced fallback client with connection caching and improved error handling.

This module provides:
- Connection caching for OpenAI clients
- Model fallback with configurable priorities
- Better error handling and retry logic
- Token counting and usage tracking
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from openai import OpenAI

from agent_server.monitoring import logger, record_fallback


# ============================================================================
# Configuration
# ============================================================================

# Model priorities (higher number = higher priority)
MODEL_PRIORITIES = {
    "nvidia/nemotron-3-super-120b-a12b:free": 100,
    "qwen/qwen-2.5-72b-instruct": 90,
    "gpt-4.1": 80,
    "gpt-4.1-mini": 70,
    "gpt-4": 60,
    "gpt-3.5-turbo": 50,
}

# Default model sequence
DEFAULT_MODELS = [
    ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
    ("openrouter", "qwen/qwen-2.5-72b-instruct"),
    ("openai", "gpt-4.1"),
]


# ============================================================================
# Connection Cache
# ============================================================================

class ConnectionCache:
    """Thread-safe cache for OpenAI client connections."""

    def __init__(self):
        self._clients: dict[str, OpenAI] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get_client(self, provider: str, api_key: str | None = None, base_url: str | None = None) -> OpenAI:
        """Get or create OpenAI client for provider."""
        cache_key = self._make_cache_key(provider, api_key, base_url)

        with self._lock:
            if cache_key in self._clients:
                self._hits += 1
                return self._clients[cache_key]

            self._misses += 1
            client = self._create_client(provider, api_key, base_url)
            self._clients[cache_key] = client
            return client

    def _make_cache_key(self, provider: str, api_key: str | None, base_url: str | None) -> str:
        """Create cache key from provider and configuration."""
        key_parts = [provider]
        if api_key:
            key_parts.append("has_key")
        if base_url:
            key_parts.append(base_url)
        return ":".join(key_parts)

    def _create_client(self, provider: str, api_key: str | None, base_url: str | None) -> OpenAI:
        """Create OpenAI client for provider."""
        if provider == "openrouter":
            return OpenAI(
                api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": os.environ.get("APP_URL", "https://github.com/robert2687"),
                    "X-Title": os.environ.get("APP_NAME", "PERFECT-AGENT"),
                },
            )
        elif provider == "openai":
            return OpenAI(
                api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._clients),
                "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0.0,
            }

    def clear(self) -> None:
        """Clear all cached clients."""
        with self._lock:
            self._clients.clear()
            self._hits = 0
            self._misses = 0


# Global connection cache
connection_cache = ConnectionCache()


# ============================================================================
# Model Registry
# ============================================================================

class ModelRegistry:
    """Registry for managing model priorities and fallback sequences."""

    def __init__(self):
        self._models: list[tuple[str, str]] = []  # (provider, model)
        self._priorities: dict[str, int] = {}
        self._lock = threading.RLock()

    def add_model(self, provider: str, model: str, priority: int | None = None) -> None:
        """Add a model to the registry."""
        with self._lock:
            if priority is None:
                priority = MODEL_PRIORITIES.get(model, 0)
            self._priorities[model] = priority
            self._models.append((provider, model))
            # Sort by priority (descending)
            self._models.sort(key=lambda x: self._priorities.get(x[1], 0), reverse=True)

    def remove_model(self, model: str) -> bool:
        """Remove a model from the registry."""
        with self._lock:
            removed = False
            self._models = [(p, m) for p, m in self._models if m != model]
            if model in self._priorities:
                del self._priorities[model]
                removed = True
            return removed

    def get_models(self) -> list[tuple[str, str]]:
        """Get list of models sorted by priority."""
        with self._lock:
            return self._models.copy()

    def get_priority(self, model: str) -> int:
        """Get priority of a model."""
        with self._lock:
            return self._priorities.get(model, 0)

    def set_priority(self, model: str, priority: int) -> None:
        """Set priority of a model and re-sort."""
        with self._lock:
            self._priorities[model] = priority
            self._models.sort(key=lambda x: self._priorities.get(x[1], 0), reverse=True)


# Global model registry
model_registry = ModelRegistry()

# Initialize with default models
for provider, model in DEFAULT_MODELS:
    model_registry.add_model(provider, model)


# ============================================================================
# Error Classes
# ============================================================================

class ModelError(Exception):
    """Base class for model-related errors."""

    def __init__(self, message: str, model: str | None = None, provider: str | None = None):
        super().__init__(message)
        self.model = model
        self.provider = provider


class ModelUnavailableError(ModelError):
    """Raised when a model is unavailable."""

    pass


class RateLimitError(ModelError):
    """Raised when rate limit is exceeded."""

    pass


class AuthenticationError(ModelError):
    """Raised when authentication fails."""

    pass


# ============================================================================
# Model Client
# ============================================================================

class ModelClient:
    """Client for interacting with a specific model."""

    def __init__(self, provider: str, model: str, client: OpenAI):
        self.provider = provider
        self.model = model
        self.client = client
        self._call_count = 0
        self._success_count = 0
        self._failure_count = 0

    def call(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict:
        """Call the model with given parameters."""
        self._call_count += 1

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self._success_count += 1
            return response
        except Exception as e:
            self._failure_count += 1
            self._handle_error(e)
            raise

    def _handle_error(self, error: Exception) -> None:
        """Handle and log model errors."""
        error_type = type(error).__name__
        logger.warning(
            "Model error",
            provider=self.provider,
            model=self.model,
            error_type=error_type,
            error_message=str(error),
            call_count=self._call_count,
            success_count=self._success_count,
            failure_count=self._failure_count,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics."""
        return {
            "provider": self.provider,
            "model": self.model,
            "call_count": self._call_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": self._success_count / self._call_count if self._call_count > 0 else 0.0,
        }


# ============================================================================
# Fallback Client
# ============================================================================

class FallbackClient:
    """Main fallback client with connection caching and intelligent fallback."""

    def __init__(self):
        self._clients: dict[str, ModelClient] = {}
        self._lock = threading.RLock()
        self._fallback_count = 0

    def get_client(self, provider: str, model: str) -> ModelClient:
        """Get or create model client."""
        cache_key = f"{provider}:{model}"

        with self._lock:
            if cache_key in self._clients:
                return self._clients[cache_key]

            openai_client = connection_cache.get_client(provider)
            client = ModelClient(provider, model, openai_client)
            self._clients[cache_key] = client
            return client

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict:
        """Send chat completion request with fallback.

        Tries models in priority order until one succeeds.
        """
        models = model_registry.get_models()
        errors = []

        for provider, model in models:
            try:
                client = self.get_client(provider, model)
                response = client.call(messages, tools, temperature, max_tokens)

                # Record fallback if we tried multiple models
                if len(errors) > 0:
                    previous_model = models[0][1] if len(errors) == 1 else models[len(errors) - 1][1]
                    record_fallback(previous_model, model)
                    self._fallback_count += 1

                return response

            except Exception as e:
                errors.append((provider, model, e))
                logger.warning(
                    "Model failed, trying next",
                    provider=provider,
                    model=model,
                    error=str(e),
                    attempt=len(errors),
                    total_models=len(models),
                )

        # All models failed
        error_messages = [f"{p}/{m}: {str(e)}" for p, m, e in errors]
        raise ModelUnavailableError(
            f"All models failed. Errors: {'; '.join(error_messages)}"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get overall statistics."""
        with self._lock:
            return {
                "fallback_count": self._fallback_count,
                "clients": {key: client.get_stats() for key, client in self._clients.items()},
                "connection_cache": connection_cache.get_stats(),
            }

    def clear_cache(self) -> None:
        """Clear all caches."""
        with self._lock:
            self._clients.clear()
        connection_cache.clear()


# Global fallback client instance
fallback_client = FallbackClient()


# ============================================================================
# Legacy Functions (for backward compatibility)
# ============================================================================

NEMOTRON = "nvidia/nemotron-3-super-120b-a12b:free"
QWEN = "qwen/qwen-2.5-72b-instruct"
GPT4 = "gpt-4.1"


def get_clients():
    """Get OpenAI clients (legacy function)."""
    return {
        "openrouter": connection_cache.get_client("openrouter"),
        "openai": connection_cache.get_client("openai"),
    }


def try_model(client: OpenAI, model: str, messages: list[dict], tools: list[dict] | None = None):
    """Try a single model (legacy function)."""
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
        )
    except Exception:
        return None


def fallback_chat(messages: list[dict], tools: list[dict] | None = None):
    """Fallback chat with legacy interface."""
    return fallback_client.chat(messages, tools)


# ============================================================================
# Configuration Functions
# ============================================================================

def add_model(provider: str, model: str, priority: int | None = None) -> None:
    """Add a model to the fallback sequence."""
    model_registry.add_model(provider, model, priority)


def remove_model(model: str) -> bool:
    """Remove a model from the fallback sequence."""
    return model_registry.remove_model(model)


def set_model_priority(model: str, priority: int) -> None:
    """Set priority for a model."""
    model_registry.set_priority(model, priority)


def get_fallback_stats() -> dict[str, Any]:
    """Get fallback client statistics."""
    return fallback_client.get_stats()


def clear_fallback_cache() -> None:
    """Clear all fallback client caches."""
    fallback_client.clear_cache()
