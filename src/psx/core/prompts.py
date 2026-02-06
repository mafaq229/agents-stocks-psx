"""Prompt loading and versioning.

Loads agent prompts from versioned YAML files under config/prompts/.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Default config directory (project root / config)
_DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"


class PromptRegistry:
    """Loads and manages versioned prompts from YAML files.

    Prompts are stored in config/prompts/{version}/{agent_name}.yaml
    and loaded on demand with caching.
    """

    def __init__(self, config_dir: Optional[Path] = None, version: str = "v1"):
        self.config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self.version = version

    def set_version(self, version: str):
        """Set active prompt version and clear cache."""
        self.version = version
        self.load_prompt.cache_clear()

    @lru_cache(maxsize=32)
    def load_prompt(self, agent_name: str, version: Optional[str] = None) -> dict:
        """Load full prompt configuration for an agent.

        Args:
            agent_name: Name of the agent (e.g. "supervisor", "data_agent")
            version: Prompt version to load (defaults to self.version)

        Returns:
            Dict with keys: system_prompt, settings, version, etc.
        """
        version = version or self.version
        path = self.config_dir / "prompts" / version / f"{agent_name}.yaml"

        if not path.exists():
            raise FileNotFoundError(
                f"Prompt config not found: {path}. "
                f"Available versions: {self.list_versions()}"
            )

        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        logger.debug(f"Loaded prompt: {agent_name} (version={version})")
        return config

    def get_system_prompt(self, agent_name: str, version: Optional[str] = None) -> str:
        """Get just the system prompt string for an agent.

        Args:
            agent_name: Name of the agent
            version: Prompt version (defaults to self.version)

        Returns:
            System prompt string
        """
        config = self.load_prompt(agent_name, version)
        return config["system_prompt"]

    def get_settings(self, agent_name: str, version: Optional[str] = None) -> dict:
        """Get model settings for an agent.

        Args:
            agent_name: Name of the agent
            version: Prompt version (defaults to self.version)

        Returns:
            Dict with settings (temperature, max_tokens, etc.)
        """
        config = self.load_prompt(agent_name, version)
        return config.get("settings", {})

    def list_versions(self) -> list[str]:
        """List available prompt versions."""
        prompts_dir = self.config_dir / "prompts"
        if not prompts_dir.exists():
            return []
        return sorted(d.name for d in prompts_dir.iterdir() if d.is_dir())

    def list_agents(self, version: Optional[str] = None) -> list[str]:
        """List available agent prompts for a version."""
        version = version or self.version
        version_dir = self.config_dir / "prompts" / version
        if not version_dir.exists():
            return []
        return sorted(p.stem for p in version_dir.glob("*.yaml"))


# Global registry instance
_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    """Get or create the global prompt registry."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


def reset_prompt_registry(config_dir: Optional[Path] = None, version: str = "v1") -> PromptRegistry:
    """Reset the global prompt registry (useful for testing)."""
    global _registry
    _registry = PromptRegistry(config_dir=config_dir, version=version)
    return _registry
