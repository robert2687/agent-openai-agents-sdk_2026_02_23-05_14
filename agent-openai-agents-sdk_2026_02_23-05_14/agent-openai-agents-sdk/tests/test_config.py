"""Tests for configuration module."""

import os

import pytest

from agent_server.config import AgentConfig, get_config, reset_config


class TestAgentConfig:
    """Tests for AgentConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AgentConfig()

        assert config.backend == "openai"
        assert config.model == "gpt-4.1-mini"
        assert config.fallback_model == "gpt-4.1"
        assert config.max_retries == 3
        assert config.retry_base_seconds == 1.5
        assert config.max_tokens == 4096
        assert config.require_auth is False
        assert config.api_token == ""
        assert config.rate_limit_per_minute == 120
        assert config.memory_backend == "inmemory"

    def test_env_variable_loading(self):
        """Test loading from environment variables."""
        os.environ["AGENT_BACKEND"] = "databricks"
        os.environ["AGENT_MODEL"] = "custom-model"
        os.environ["AGENT_MAX_RETRIES"] = "5"

        reset_config()
        config = get_config()

        assert config.backend == "databricks"
        assert config.model == "custom-model"
        assert config.max_retries == 5

        # Clean up
        del os.environ["AGENT_BACKEND"]
        del os.environ["AGENT_MODEL"]
        del os.environ["AGENT_MAX_RETRIES"]
        reset_config()

    def test_validation_backend(self):
        """Test backend validation."""
        config = AgentConfig(backend="openai")
        assert config.backend == "openai"

        config = AgentConfig(backend="databricks")
        assert config.backend == "databricks"

        with pytest.raises(ValueError):
            AgentConfig(backend="invalid")

    def test_validation_max_retries(self):
        """Test max_retries validation."""
        config = AgentConfig(max_retries=1)
        assert config.max_retries == 1

        config = AgentConfig(max_retries=10)
        assert config.max_retries == 10

        with pytest.raises(ValueError):
            AgentConfig(max_retries=0)

        with pytest.raises(ValueError):
            AgentConfig(max_retries=11)

    def test_validation_retry_base_seconds(self):
        """Test retry_base_seconds validation."""
        config = AgentConfig(retry_base_seconds=0.1)
        assert config.retry_base_seconds == 0.1

        config = AgentConfig(retry_base_seconds=60)
        assert config.retry_base_seconds == 60

        with pytest.raises(ValueError):
            AgentConfig(retry_base_seconds=0)

        with pytest.raises(ValueError):
            AgentConfig(retry_base_seconds=61)

    def test_validation_max_tokens(self):
        """Test max_tokens validation."""
        config = AgentConfig(max_tokens=1)
        assert config.max_tokens == 1

        config = AgentConfig(max_tokens=32768)
        assert config.max_tokens == 32768

        with pytest.raises(ValueError):
            AgentConfig(max_tokens=0)

        with pytest.raises(ValueError):
            AgentConfig(max_tokens=32769)

    def test_validation_rate_limit(self):
        """Test rate_limit_per_minute validation."""
        config = AgentConfig(rate_limit_per_minute=1)
        assert config.rate_limit_per_minute == 1

        config = AgentConfig(rate_limit_per_minute=10000)
        assert config.rate_limit_per_minute == 10000

        with pytest.raises(ValueError):
            AgentConfig(rate_limit_per_minute=0)

        with pytest.raises(ValueError):
            AgentConfig(rate_limit_per_minute=10001)

    def test_properties(self):
        """Test computed properties."""
        config = AgentConfig(backend="openai")
        assert config.use_databricks is False
        assert config.is_production is False

        config = AgentConfig(backend="databricks")
        assert config.use_databricks is True

    def test_openai_credentials_configured(self):
        """Test OpenAI credentials detection."""
        os.environ["OPENAI_API_KEY"] = "test-key"
        reset_config()
        config = get_config()
        assert config.openai_credentials_configured is True

        del os.environ["OPENAI_API_KEY"]
        os.environ["OPENAI_ADMIN_KEY"] = "admin-key"
        reset_config()
        config = get_config()
        assert config.openai_credentials_configured is True

        del os.environ["OPENAI_ADMIN_KEY"]
        reset_config()
        config = get_config()
        assert config.openai_credentials_configured is False

    def test_caching(self):
        """Test configuration caching."""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

        reset_config()
        config3 = get_config()

        assert config3 is not config1
