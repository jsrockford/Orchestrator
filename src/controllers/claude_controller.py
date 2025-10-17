"""
Claude Code Controller

Wrapper around TmuxController configured specifically for Claude Code.
"""

from typing import Optional
from .tmux_controller import TmuxController
from ..utils.config_loader import get_config


class ClaudeController(TmuxController):
    """Controller specifically configured for Claude Code."""

    def __init__(
        self,
        session_name: Optional[str] = None,
        working_dir: Optional[str] = None
    ):
        """
        Initialize ClaudeController with Claude-specific configuration.

        Args:
            session_name: Name of tmux session (uses config default if not specified)
            working_dir: Working directory (defaults to current dir)
        """
        # Load Claude configuration
        config = get_config()
        claude_config = config.get_section('claude')
        tmux_config = config.get_section('tmux')

        # Use configured session name if not specified
        if session_name is None:
            session_name = tmux_config.get('claude_session', 'claude')

        # Get executable from config
        executable = claude_config.get('executable', 'claude')

        # Initialize parent with Claude configuration
        executable_args = claude_config.get('executable_args', [])

        super().__init__(
            session_name=session_name,
            executable=executable,
            working_dir=working_dir,
            ai_config=claude_config,
            executable_args=executable_args
        )

        # Store Claude-specific markers
        self.response_marker = claude_config.get('response_marker', '●')
