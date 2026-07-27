"""Centralized configuration management using Pydantic Settings.

This module provides type-safe configuration with environment variable support,
validation, and easy access throughout the application.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Agent server configuration."""

    # Backend settings
    backend: str = Field(default="openai", env="AGENT_BACKEND")
    model: str = Field(default="gpt-4.1-mini", env="AGENT_MODEL")
    fallback_model: str = Field(default="gpt-4.1", env="AGENT_FALLBACK_MODEL")

    # Retry settings
    max_retries: int = Field(default=3, ge=1, le=10, env="AGENT_MAX_RETRIES")
    retry_base_seconds: float = Field(default=1.5, ge=0.1, le=60, env="AGENT_RETRY_BASE_SECONDS")

    # Token settings
    max_tokens: int = Field(default=4096, ge=1, le=32768, env="AGENT_MAX_TOKENS")

    # Authentication settings
    require_auth: bool = Field(default=False, env="AGENT_REQUIRE_AUTH")
    api_token: str = Field(default="", env="AGENT_API_TOKEN")

    # Rate limiting
    rate_limit_per_minute: int = Field(default=120, ge=1, le=10000, env="AGENT_RATE_LIMIT_PER_MINUTE")

    # Memory settings
    memory_backend: str = Field(default="inmemory", env="MEMORY_BACKEND")
    memory_tenant: str = Field(default="default-tenant", env="AGENT_MEMORY_TENANT")
    memory_user: str = Field(default="default-user", env="AGENT_MEMORY_USER")

    # MLflow settings
    mlflow_tracking_uri: str = Field(default="sqlite:///mlflow.db", env="MLFLOW_TRACKING_URI")
    mlflow_registry_uri: str | None = Field(default=None, env="MLFLOW_REGISTRY_URI")
    mlflow_experiment_id: str | None = Field(default=None, env="MLFLOW_EXPERIMENT_ID")
    mlflow_enable_autolog: bool = Field(default=False, env="AGENT_ENABLE_MLFLOW_AUTOLOG")

    # OpenAI settings
    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")
    openai_admin_key: str | None = Field(default=None, env="OPENAI_ADMIN_KEY")
    openai_base_url: str | None = Field(default=None, env="OPENAI_BASE_URL")
    openrouter_api_key: str | None = Field(default=None, env="OPENROUTER_API_KEY")

    # App identity
    app_name: str = Field(default="PERFECT-AGENT", env="APP_NAME")
    app_url: str = Field(default="https://github.com/robert2687", env="APP_URL")

    # Networking
    api_port: int = Field(default=8000, ge=1, le=65535, env="API_PORT")
    ui_port: int = Field(default=7860, ge=1, le=65535, env="UI_PORT")

    # Databricks settings
    databricks_host: str | None = Field(default=None, env="DATABRICKS_HOST")
    databricks_token: str | None = Field(default=None, env="DATABRICKS_TOKEN")
    databricks_config_profile: str | None = Field(default=None, env="DATABRICKS_CONFIG_PROFILE")

    # Cosmos DB settings
    cosmos_endpoint: str | None = Field(default=None, env="COSMOS_ENDPOINT")
    cosmos_key: str | None = Field(default=None, env="COSMOS_KEY")
    cosmos_database: str | None = Field(default=None, env="COSMOS_DATABASE")
    cosmos_container: str | None = Field(default=None, env="COSMOS_CONTAINER")

    # Monitoring
    enable_prometheus: bool = Field(default=False, env="AGENT_ENABLE_PROMETHEUS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        valid_backends = {"openai", "databricks"}
        if v.lower() not in valid_backends:
            raise ValueError(f"backend must be one of {valid_backends}, got {v}")
        return v.lower()

    @property
    def use_databricks(self) -> bool:
        """Check if Databricks backend is enabled."""
        return self.backend == "databricks"

    @property
    def openai_credentials_configured(self) -> bool:
        """Check if OpenAI credentials are available."""
        return bool(self.openai_api_key or self.openai_admin_key)

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return os.getenv("ENVIRONMENT", "development") == "production"


@lru_cache()
def get_config() -> AgentConfig:
    """Get cached configuration instance."""
    return AgentConfig()


def reset_config() -> None:
    """Reset configuration cache (useful for testing)."""
    get_config.cache_clear()


# Convenience access
config = get_config()
