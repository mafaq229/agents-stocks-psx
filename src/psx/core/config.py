"""Configuration management for PSX Stock Analysis Platform.

Loads settings from environment variables and provides typed access.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal
from dotenv import load_dotenv

load_dotenv()

LLMProvider = Literal["openai", "anthropic"]


# Default models per provider
DEFAULT_MODELS = {
    "openai": {
        "smart": "gpt-5.1",       # For complex analysis (AnalystAgent, Synthesis)
        "fast": "gpt-5-nano",   # For routing/summarization (Data, Supervisor, PDF summarizer)
    },
    "anthropic": {
        "smart": "claude-sonnet-4-5-20250929",
        "fast": "claude-haiku-4-5-20251001",
    },
}


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: LLMProvider = "openai"
    model: str = "gpt-5.1"  # Default smart model
    fast_model: str = "gpt-5-nano"  # Cheap model for summarization/routing
    temperature: float = 0.0
    max_tokens: int = 10000
    timeout: float = 120.0


@dataclass
class AgentModels:
    """Per-agent model configuration."""

    # Agents that need smarter models (complex reasoning)
    analyst: Optional[str] = None      # Financial analysis - use smart
    synthesis: Optional[str] = None    # Final report generation - use smart

    # Agents that can use cheaper models (tool calling, routing)
    supervisor: Optional[str] = None   # Routing decisions - use fast
    data: Optional[str] = None         # Tool calls only - use fast
    research: Optional[str] = None     # Tool calls + some reasoning - use fast
    pdf_summarizer: Optional[str] = None  # PDF extraction - use fast


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None

    # LLM Settings
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Per-agent model overrides
    agent_models: AgentModels = field(default_factory=AgentModels)

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
        else:
            default_provider = "openai"

        # Override from env if specified
        provider = os.getenv("PSX_LLM_PROVIDER", default_provider)
        if provider not in ("openai", "anthropic"):
            provider = default_provider

        # Get default models for this provider
        provider_models = DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openai"])
        default_smart = provider_models["smart"]
        default_fast = provider_models["fast"]

        # Allow env override for main model
        model = os.getenv("PSX_LLM_MODEL", default_smart)
        fast_model = os.getenv("PSX_LLM_FAST_MODEL", default_fast)

        llm_config = LLMConfig(
            provider=provider,  # type: ignore
            model=model,
            fast_model=fast_model,
            temperature=float(os.getenv("PSX_LLM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("PSX_LLM_MAX_TOKENS", "4096")),
            timeout=float(os.getenv("PSX_LLM_TIMEOUT", "120.0")),
        )

        # Per-agent model overrides (optional)
        agent_models = AgentModels(
            analyst=os.getenv("PSX_MODEL_ANALYST"),
            synthesis=os.getenv("PSX_MODEL_SYNTHESIS"),
            supervisor=os.getenv("PSX_MODEL_SUPERVISOR"),
            data=os.getenv("PSX_MODEL_DATA"),
            research=os.getenv("PSX_MODEL_RESEARCH"),
            pdf_summarizer=os.getenv("PSX_MODEL_PDF_SUMMARIZER"),
        )

        return cls(
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            llm=llm_config,
            agent_models=agent_models,
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

    def get_model_for_agent(self, agent_type: str) -> str:
        """Get the model to use for a specific agent type.

        Args:
            agent_type: One of 'analyst', 'synthesis', 'supervisor', 'data',
                       'research', 'pdf_summarizer'

        Returns:
            Model name to use
        """
        # Check for explicit override first
        override = getattr(self.agent_models, agent_type, None)
        if override:
            return override

        # Use smart model for complex reasoning tasks
        smart_agents = {"analyst", "synthesis"}
        if agent_type in smart_agents:
            return self.llm.model  # Smart model

        # Use fast model for routing/tool-calling tasks
        return self.llm.fast_model

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
