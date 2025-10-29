"""
Configuration Loader

Loads and provides access to configuration values from config.yaml
"""

import os
import yaml
from typing import Any, Dict, Optional, Sequence


class ConfigLoader:
    """Loads and provides access to configuration settings."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ConfigLoader.

        Args:
            config_path: Path to config.yaml file. If None, searches for it
                        in standard locations.
        """
        self.config_path = config_path or self._find_config()
        self.config = self._load_config()

    def _find_config(self) -> str:
        """
        Find config.yaml in standard locations.

        Returns:
            Path to config.yaml

        Raises:
            FileNotFoundError: If config.yaml not found
        """
        # Search paths (in order of priority)
        search_paths = [
            "config.yaml",                                    # Current directory
            os.path.join(os.getcwd(), "config.yaml"),        # Explicit current
            os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml"),  # Project root
        ]

        for path in search_paths:
            if os.path.exists(path):
                return os.path.abspath(path)

        raise FileNotFoundError(
            f"config.yaml not found in standard locations: {search_paths}"
        )

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
            yaml.YAMLError: If config file is invalid
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"Invalid config file format: {self.config_path}")

        return config

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., "claude.startup_timeout")
            default: Default value if key not found

        Returns:
            Configuration value or default

        Examples:
            config.get("claude.startup_timeout")  # Returns 10
            config.get("tmux.capture_lines")      # Returns 100
            config.get("nonexistent.key", 42)     # Returns 42
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.

        Args:
            section: Section name (e.g., "claude", "tmux")

        Returns:
            Section dictionary or empty dict if not found
        """
        return self.config.get(section, {})

    def get_executable_parts(self, agent: str) -> Sequence[str]:
        """
        Return the executable and argument list for a given agent.

        Args:
            agent: Agent key in the config (e.g., "claude", "gemini").

        Returns:
            Sequence containing the executable and any configured arguments.

        Raises:
            KeyError: If the executable is not defined for the agent.
        """
        section = self.get_section(agent)
        executable = section.get("executable")
        if not executable:
            raise KeyError(f"No executable configured for '{agent}'.")

        raw_args = section.get("executable_args", [])
        if isinstance(raw_args, str):
            raw_args = [raw_args]

        if not isinstance(raw_args, (list, tuple)):
            raise TypeError(
                f"Invalid executable_args for '{agent}': expected list/tuple, got {type(raw_args)!r}"
            )

        return (executable, *map(str, raw_args))

    def get_executable_command(self, agent: str) -> str:
        """
        Build a shell-ready command string for the given agent.

        Args:
            agent: Agent key in the config (e.g., "claude", "gemini").

        Returns:
            Command string (executable + args) joined by spaces.
        """
        parts = self.get_executable_parts(agent)
        return " ".join(parts)

    def reload(self) -> None:
        """Reload configuration from file."""
        self.config = self._load_config()

    def __repr__(self) -> str:
        return f"ConfigLoader('{self.config_path}')"


# Global config instance (lazy loaded)
_config_instance: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """
    Get global configuration instance (singleton pattern).

    Returns:
        ConfigLoader instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader()
    return _config_instance


def reload_config() -> None:
    """Reload global configuration from file."""
    global _config_instance
    if _config_instance is not None:
        _config_instance.reload()
