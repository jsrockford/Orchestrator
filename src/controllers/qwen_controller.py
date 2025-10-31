"""
Qwen CLI Controller

Provides Qwen-specific defaults for the shared TmuxController. Qwen's CLI uses
an `(esc to cancel` loading indicator, so we rely on loading indicator clears
plus a configurable stabilization delay before submitting new input.
"""

from typing import Optional

from .tmux_controller import TmuxController
from ..utils.config_loader import get_config


class QwenController(TmuxController):
    """Controller configured for the Qwen CLI."""

    def __init__(
        self,
        session_name: Optional[str] = None,
        working_dir: Optional[str] = None,
    ):
        """
        Initialize QwenController with Qwen-specific configuration.

        Args:
            session_name: Optional tmux session name (defaults to config value).
            working_dir: Working directory for the Qwen process.
        """
        config = get_config()
        qwen_config = dict(config.get_section("qwen") or {})
        tmux_config = config.get_section("tmux")

        # Override for tmux reliability: Use C-m for consistent command submission
        # This enables the double-submit pattern (C-m + fallback Enter) which is
        # essential for complex/normalized multiline commands in orchestrated scenarios
        qwen_config["submit_key"] = "C-m"
        qwen_config["submit_fallback_keys"] = ["M-Enter", "C-m", "Enter", "C-j"]
        qwen_config["submit_retry_delay"] = 0.2
        qwen_config["text_enter_delay"] = 0.6
        qwen_config["post_text_delay"] = 0.0

        if session_name is None:
            session_name = tmux_config.get("qwen_session", "qwen")

        executable = qwen_config.get("executable", "qwen")
        executable_args = qwen_config.get("executable_args", [])

        super().__init__(
            session_name=session_name,
            executable=executable,
            working_dir=working_dir,
            ai_config=qwen_config,
            executable_args=executable_args,
        )

        self.response_marker = qwen_config.get("response_marker", "▸")
