"""
Codex CLI Controller

Provides Codex-specific defaults for the shared TmuxController. The Codex CLI
behaves similarly to Claude (Enter submits, standard prompt markers), so we
reuse the same mechanics but keep configuration isolated in case future builds
diverge.
"""

from typing import Optional

from .tmux_controller import TmuxController
from ..utils.config_loader import get_config


class CodexController(TmuxController):
    """Controller configured for the Codex CLI."""

    def __init__(
        self,
        session_name: Optional[str] = None,
        working_dir: Optional[str] = None,
    ):
        """
        Initialize CodexController with Codex-specific configuration.

        Args:
            session_name: Optional tmux session name (uses config default when omitted).
            working_dir: Working directory for the Codex process.
        """
        config = get_config()
        codex_config = config.get_section("codex")
        tmux_config = config.get_section("tmux")

        if session_name is None:
            session_name = tmux_config.get("codex_session", "codex")

        executable = codex_config.get("executable", "codex")
        executable_args = codex_config.get("executable_args", [])

        super().__init__(
            session_name=session_name,
            executable=executable,
            working_dir=working_dir,
            ai_config=codex_config,
            executable_args=executable_args,
        )

        self.response_marker = codex_config.get("response_marker", "▸")
