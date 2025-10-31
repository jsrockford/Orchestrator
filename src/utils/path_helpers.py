"""
Path resolution helpers for orchestrator utilities and tests.

These helpers centralize how we locate the primary project directory and the
separate tmux/testing worktree so that individual scripts avoid hard-coded
absolute paths. Environment variables take precedence, falling back to values
defined in config.yaml, and ultimately to sensible defaults relative to the
repository root.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .config_loader import get_config

ENV_PROJECT_ROOT = "ORCHESTRATOR_PROJECT_ROOT"
ENV_TMUX_WORKTREE = "ORCHESTRATOR_TEST_DIR"


def _resolve_path(value: Optional[str]) -> Optional[Path]:
    """Expand environment variables and ~ in a configured path."""
    if not value:
        return None
    return Path(os.path.expanduser(os.path.expandvars(str(value)))).resolve()


def get_repo_root() -> Path:
    """
    Return the repository root path.

    Resolution order:
      1. Environment variable ORCHESTRATOR_PROJECT_ROOT
      2. config.yaml worktree.main_path
      3. Two levels up from this file (default repository layout)
    """
    env_value = os.getenv(ENV_PROJECT_ROOT)
    if env_value:
        resolved = _resolve_path(env_value)
        if resolved:
            return resolved

    config = get_config().get_section("worktree")
    configured = _resolve_path(config.get("main_path") if isinstance(config, dict) else None)
    if configured:
        return configured

    return Path(__file__).resolve().parents[2]


def get_tmux_worktree_path() -> Path:
    """
    Return the tmux/testing worktree path.

    Resolution order mirrors get_repo_root but uses ORCHESTRATOR_TEST_DIR
    and worktree.tmux_path. Defaults to the repository root when no override
    is provided.
    """
    env_value = os.getenv(ENV_TMUX_WORKTREE)
    if env_value:
        resolved = _resolve_path(env_value)
        if resolved:
            return resolved

    config = get_config().get_section("worktree")
    configured = _resolve_path(config.get("tmux_path") if isinstance(config, dict) else None)
    if configured:
        return configured

    return get_repo_root()


def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, returning the path.

    This is primarily a convenience for tests that need a writable location.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path

