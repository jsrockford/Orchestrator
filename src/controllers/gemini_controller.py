"""
Gemini CLI Controller

Wrapper around TmuxController configured specifically for Gemini CLI.
"""

from typing import Optional
from .tmux_controller import TmuxController
from ..utils.config_loader import get_config


class GeminiController(TmuxController):
    """Controller specifically configured for Gemini CLI."""

    def __init__(
        self,
        session_name: Optional[str] = None,
        working_dir: Optional[str] = None
    ):
        """
        Initialize GeminiController with Gemini-specific configuration.

        Args:
            session_name: Name of tmux session (uses config default if not specified)
            working_dir: Working directory (defaults to current dir)
        """
        # Load Gemini configuration
        config = get_config()
        gemini_config = config.get_section('gemini')
        tmux_config = config.get_section('tmux')

        # Use configured session name if not specified
        if session_name is None:
            session_name = tmux_config.get('gemini_session', 'gemini')

        # Get executable from config
        executable = gemini_config.get('executable', 'gemini')

        # Initialize parent with Gemini configuration
        executable_args = gemini_config.get('executable_args', [])

        super().__init__(
            session_name=session_name,
            executable=executable,
            working_dir=working_dir,
            ai_config=gemini_config,
            executable_args=executable_args
        )

        # Store Gemini-specific markers
        self.response_marker = gemini_config.get('response_marker', '✦')
        self.supports_tools = gemini_config.get('supports_tools', True)
        self.tool_marker = gemini_config.get('tool_marker', '✓')
