"""Tests for configuration management."""

import pytest
import os
from unittest.mock import patch

from psx.core.config import (
    LLMConfig,
    AgentModels,
    Config,
    get_config,
    reset_config,
    DEFAULT_MODELS,
)


class TestLLMConfig:
    """Test LLMConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-5.1"
        assert config.fast_model == "gpt-5-nano"
        assert config.temperature == 0.0
        assert config.max_tokens == 10000
        assert config.timeout == 120.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5-20250929",
            fast_model="claude-haiku-4-5-20251001",
            temperature=0.7,
            max_tokens=2000,
            timeout=60.0,
        )
        assert config.provider == "anthropic"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000


class TestAgentModels:
    """Test AgentModels dataclass."""

    def test_default_values(self):
        """Test all values default to None."""
        models = AgentModels()
        assert models.analyst is None
        assert models.synthesis is None
        assert models.supervisor is None
        assert models.data is None
        assert models.research is None
        assert models.pdf_summarizer is None

    def test_custom_overrides(self):
        """Test setting custom model overrides."""
        models = AgentModels(
            analyst="gpt-4o",
            supervisor="gpt-5-mini",
        )
        assert models.analyst == "gpt-4o"
        assert models.supervisor == "gpt-5-mini"
        assert models.data is None  # Not overridden


class TestConfig:
    """Test Config dataclass."""

    def test_default_values(self):
        """Test default configuration."""
        config = Config()
        assert config.openai_api_key is None
        assert config.anthropic_api_key is None
        assert config.data_dir == "data"
        assert config.db_path == "data/db/psx.db"
        assert config.max_agent_iterations == 10

    def test_from_env_openai_default(self):
        """Test from_env defaults to OpenAI when key available."""
        env = {
            "OPENAI_API_KEY": "sk-test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            reset_config()
            config = Config.from_env()

        assert config.llm.provider == "openai"
        assert config.openai_api_key == "sk-test-key"
        assert config.llm.model == DEFAULT_MODELS["openai"]["smart"]

    def test_from_env_anthropic_default(self):
        """Test from_env defaults to Anthropic when only that key available."""
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()

        assert config.llm.provider == "anthropic"
        assert config.anthropic_api_key == "sk-ant-test-key"
        assert config.llm.model == DEFAULT_MODELS["anthropic"]["smart"]

    def test_from_env_provider_override(self):
        """Test PSX_LLM_PROVIDER overrides default."""
        env = {
            "OPENAI_API_KEY": "sk-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "PSX_LLM_PROVIDER": "anthropic",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()

        assert config.llm.provider == "anthropic"

    def test_from_env_model_override(self):
        """Test PSX_LLM_MODEL overrides default model."""
        env = {
            "OPENAI_API_KEY": "sk-test",
            "PSX_LLM_MODEL": "gpt-4o",
            "PSX_LLM_FAST_MODEL": "gpt-4o-mini",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()

        assert config.llm.model == "gpt-4o"
        assert config.llm.fast_model == "gpt-4o-mini"

    def test_from_env_llm_settings(self):
        """Test LLM settings from environment."""
        env = {
            "OPENAI_API_KEY": "sk-test",
            "PSX_LLM_TEMPERATURE": "0.5",
            "PSX_LLM_MAX_TOKENS": "8192",
            "PSX_LLM_TIMEOUT": "180.0",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()

        assert config.llm.temperature == 0.5
        assert config.llm.max_tokens == 8192
        assert config.llm.timeout == 180.0

    def test_from_env_agent_model_overrides(self):
        """Test per-agent model overrides from environment."""
        env = {
            "OPENAI_API_KEY": "sk-test",
            "PSX_MODEL_ANALYST": "gpt-4o",
            "PSX_MODEL_SUPERVISOR": "gpt-5-mini",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()

        assert config.agent_models.analyst == "gpt-4o"
        assert config.agent_models.supervisor == "gpt-5-mini"
        assert config.agent_models.data is None

    def test_from_env_data_paths(self):
        """Test data path configuration from environment."""
        env = {
            "PSX_DATA_DIR": "/custom/data",
            "PSX_DB_PATH": "/custom/db/psx.db",
            "PSX_CACHE_DIR": "/custom/cache",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()

        assert config.data_dir == "/custom/data"
        assert config.db_path == "/custom/db/psx.db"
        assert config.cache_dir == "/custom/cache"

    def test_from_env_agent_settings(self):
        """Test agent settings from environment."""
        env = {
            "PSX_MAX_ITERATIONS": "20",
            "PSX_AGENT_TIMEOUT": "600.0",
        }
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_env()

        assert config.max_agent_iterations == 20
        assert config.agent_timeout == 600.0


class TestConfigGetApiKey:
    """Test Config.get_api_key method."""

    def test_get_openai_key(self):
        """Test getting OpenAI API key."""
        config = Config(openai_api_key="sk-openai-test")
        key = config.get_api_key("openai")
        assert key == "sk-openai-test"

    def test_get_anthropic_key(self):
        """Test getting Anthropic API key."""
        config = Config(anthropic_api_key="sk-ant-test")
        key = config.get_api_key("anthropic")
        assert key == "sk-ant-test"

    def test_get_default_provider_key(self):
        """Test getting key for default provider."""
        config = Config(
            openai_api_key="sk-openai",
            llm=LLMConfig(provider="openai"),
        )
        key = config.get_api_key()  # No provider specified
        assert key == "sk-openai"

    def test_missing_openai_key_raises(self):
        """Test missing OpenAI key raises error."""
        config = Config()
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            config.get_api_key("openai")

    def test_missing_anthropic_key_raises(self):
        """Test missing Anthropic key raises error."""
        config = Config()
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            config.get_api_key("anthropic")

    def test_unknown_provider_raises(self):
        """Test unknown provider raises error."""
        config = Config()
        with pytest.raises(ValueError, match="Unknown provider"):
            config.get_api_key("unknown")  # type: ignore


class TestConfigGetModelForAgent:
    """Test Config.get_model_for_agent method."""

    def test_analyst_uses_smart_model(self):
        """Test analyst agent uses smart model."""
        config = Config(llm=LLMConfig(model="smart-model", fast_model="fast-model"))
        model = config.get_model_for_agent("analyst")
        assert model == "smart-model"

    def test_synthesis_uses_smart_model(self):
        """Test synthesis uses smart model."""
        config = Config(llm=LLMConfig(model="smart-model", fast_model="fast-model"))
        model = config.get_model_for_agent("synthesis")
        assert model == "smart-model"

    def test_supervisor_uses_fast_model(self):
        """Test supervisor uses fast model."""
        config = Config(llm=LLMConfig(model="smart-model", fast_model="fast-model"))
        model = config.get_model_for_agent("supervisor")
        assert model == "fast-model"

    def test_data_uses_fast_model(self):
        """Test data agent uses fast model."""
        config = Config(llm=LLMConfig(model="smart-model", fast_model="fast-model"))
        model = config.get_model_for_agent("data")
        assert model == "fast-model"

    def test_research_uses_fast_model(self):
        """Test research agent uses fast model."""
        config = Config(llm=LLMConfig(model="smart-model", fast_model="fast-model"))
        model = config.get_model_for_agent("research")
        assert model == "fast-model"

    def test_pdf_summarizer_uses_fast_model(self):
        """Test PDF summarizer uses fast model."""
        config = Config(llm=LLMConfig(model="smart-model", fast_model="fast-model"))
        model = config.get_model_for_agent("pdf_summarizer")
        assert model == "fast-model"

    def test_override_takes_precedence(self):
        """Test explicit override takes precedence."""
        config = Config(
            llm=LLMConfig(model="smart-model", fast_model="fast-model"),
            agent_models=AgentModels(analyst="custom-analyst-model"),
        )
        model = config.get_model_for_agent("analyst")
        assert model == "custom-analyst-model"


class TestConfigValidate:
    """Test Config.validate method."""

    def test_validate_openai_missing_key(self):
        """Test validation catches missing OpenAI key."""
        config = Config(llm=LLMConfig(provider="openai"))
        issues = config.validate()
        assert any("OpenAI API key" in issue for issue in issues)

    def test_validate_anthropic_missing_key(self):
        """Test validation catches missing Anthropic key."""
        config = Config(llm=LLMConfig(provider="anthropic"))
        issues = config.validate()
        assert any("Anthropic API key" in issue for issue in issues)

    def test_validate_tavily_warning(self):
        """Test validation warns about missing Tavily key."""
        config = Config(
            openai_api_key="sk-test",
            llm=LLMConfig(provider="openai"),
        )
        issues = config.validate()
        assert any("Tavily" in issue for issue in issues)

    def test_validate_all_keys_present(self):
        """Test validation with all keys present."""
        config = Config(
            openai_api_key="sk-openai",
            tavily_api_key="tvly-test",
            llm=LLMConfig(provider="openai"),
        )
        issues = config.validate()
        # Only Tavily warning should not appear
        assert not any("OpenAI API key" in issue for issue in issues)
        assert not any("Anthropic API key" in issue for issue in issues)


class TestGlobalConfig:
    """Test global config functions."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Reset config after each test."""
        reset_config()

    def test_get_config_creates_instance(self):
        """Test get_config creates singleton instance."""
        env = {"OPENAI_API_KEY": "sk-test"}
        with patch.dict(os.environ, env, clear=True):
            config1 = get_config()
            config2 = get_config()

        assert config1 is config2  # Same instance

    def test_reset_config_clears_instance(self):
        """Test reset_config clears singleton."""
        env = {"OPENAI_API_KEY": "sk-test1"}
        with patch.dict(os.environ, env, clear=True):
            config1 = get_config()

        reset_config()

        env = {"OPENAI_API_KEY": "sk-test2"}
        with patch.dict(os.environ, env, clear=True):
            config2 = get_config()

        assert config1.openai_api_key == "sk-test1"
        assert config2.openai_api_key == "sk-test2"
