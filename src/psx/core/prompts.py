"""Prompt loading and versioning.

Loads agent prompts from versioned YAML files under config/prompts/.
"""

import logging
from pathlib import Path

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Default config directory (project root / config)
_DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"


class PromptRegistry:
    """Loads and manages versioned prompts from YAML files.

    Prompts are stored in config/prompts/{version}/{agent_name}.yaml
    and loaded on demand with caching.
    """

    def __init__(self, config_dir: Path | None = None, version: str = "v1"):
        self.config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self.version = version
        self._cache: dict[tuple[str, str], dict] = {}

    def set_version(self, version: str):
        """Set active prompt version and clear cache."""
        self.version = version
        self._cache.clear()

    def load_prompt(self, agent_name: str, version: str | None = None) -> dict:
        """Load full prompt configuration for an agent.

        Args:
            agent_name: Name of the agent (e.g. "supervisor", "data_agent")
            version: Prompt version to load (defaults to self.version)

        Returns:
            Dict with keys: system_prompt, settings, version, etc.
        """
        version = version or self.version
        cache_key = (agent_name, version)
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.config_dir / "prompts" / version / f"{agent_name}.yaml"

        if not path.exists():
            raise FileNotFoundError(
                f"Prompt config not found: {path}. Available versions: {self.list_versions()}"
            )

        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        logger.debug(f"Loaded prompt: {agent_name} (version={version})")
        self._cache[cache_key] = config
        return config  # type: ignore[no-any-return]

    def get_system_prompt(self, agent_name: str, version: str | None = None) -> str:
        """Get just the system prompt string for an agent.

        Args:
            agent_name: Name of the agent
            version: Prompt version (defaults to self.version)

        Returns:
            System prompt string
        """
        config = self.load_prompt(agent_name, version)
        return config["system_prompt"]  # type: ignore[no-any-return]

    def get_settings(self, agent_name: str, version: str | None = None) -> dict:
        """Get model settings for an agent.

        Args:
            agent_name: Name of the agent
            version: Prompt version (defaults to self.version)

        Returns:
            Dict with settings (temperature, max_tokens, etc.)
        """
        config = self.load_prompt(agent_name, version)
        return config.get("settings", {})  # type: ignore[no-any-return]

    def list_versions(self) -> list[str]:
        """List available prompt versions."""
        prompts_dir = self.config_dir / "prompts"
        if not prompts_dir.exists():
            return []
        return sorted(d.name for d in prompts_dir.iterdir() if d.is_dir())

    def list_agents(self, version: str | None = None) -> list[str]:
        """List available agent prompts for a version."""
        version = version or self.version
        version_dir = self.config_dir / "prompts" / version
        if not version_dir.exists():
            return []
        return sorted(p.stem for p in version_dir.glob("*.yaml"))


# Global registry instance
_registry: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    """Get or create the global prompt registry."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


def reset_prompt_registry(config_dir: Path | None = None, version: str = "v1") -> PromptRegistry:
    """Reset the global prompt registry (useful for testing)."""
    global _registry
    _registry = PromptRegistry(config_dir=config_dir, version=version)
    return _registry
