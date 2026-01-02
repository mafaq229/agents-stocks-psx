"""Configuration management for PSX Stock Analysis Platform.

Loads settings from environment variables and provides typed access.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal
from dotenv import load_dotenv

load_dotenv()

LLMProvider = Literal["openai", "anthropic"]


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: LLMProvider = "openai"
    model: str = "gpt-5.1"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: float = 120.0


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None

    # LLM Settings
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Data paths
    data_dir: str = "data"
    db_path: str = "data/db/psx.db"
    cache_dir: str = "data/cache"

    # Agent settings
    max_agent_iterations: int = 10
    agent_timeout: float = 300.0

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # Determine default LLM provider based on available keys
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if anthropic_key and not openai_key:
            default_provider: LLMProvider = "anthropic"
            default_model = "claude-sonnet-4-5-20250929"
        else:
            default_provider = "openai"
            default_model = "gpt-5.1"

        # Override from env if specified
        provider = os.getenv("PSX_LLM_PROVIDER", default_provider)
        if provider not in ("openai", "anthropic"):
            provider = default_provider

        model = os.getenv("PSX_LLM_MODEL", default_model)

        llm_config = LLMConfig(
            provider=provider,  # type: ignore
            model=model,
            temperature=float(os.getenv("PSX_LLM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("PSX_LLM_MAX_TOKENS", "4096")),
            timeout=float(os.getenv("PSX_LLM_TIMEOUT", "120.0")),
        )

        return cls(
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            llm=llm_config,
            data_dir=os.getenv("PSX_DATA_DIR", "data"),
            db_path=os.getenv("PSX_DB_PATH", "data/db/psx.db"),
            cache_dir=os.getenv("PSX_CACHE_DIR", "data/cache"),
            max_agent_iterations=int(os.getenv("PSX_MAX_ITERATIONS", "10")),
            agent_timeout=float(os.getenv("PSX_AGENT_TIMEOUT", "300.0")),
        )

    def get_api_key(self, provider: Optional[LLMProvider] = None) -> str:
        """Get API key for the specified or default provider."""
        provider = provider or self.llm.provider

        if provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            return self.openai_api_key
        elif provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            return self.anthropic_api_key
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def validate(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []

        # Check LLM API key
        if self.llm.provider == "openai" and not self.openai_api_key:
            issues.append("OpenAI API key not set (OPENAI_API_KEY)")
        if self.llm.provider == "anthropic" and not self.anthropic_api_key:
            issues.append("Anthropic API key not set (ANTHROPIC_API_KEY)")

        # Check Tavily for web search
        if not self.tavily_api_key:
            issues.append("Tavily API key not set (TAVILY_API_KEY) - web search disabled")

        return issues


# Global config instance - lazy loaded
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config() -> None:
    """Reset configuration (useful for testing)."""
    global _config
    _config = None
