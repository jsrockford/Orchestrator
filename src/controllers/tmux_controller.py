"""
Tmux Controller for AI CLI Interaction

This module provides programmatic control over AI CLI tools
(Claude Code, Gemini CLI, etc.) running in tmux sessions.
"""

import subprocess
import time
from typing import Optional, List, Dict, Any


class TmuxController:
    """
    Controls AI CLI tools running in tmux sessions.

    AI-agnostic controller that works with any interactive CLI tool.
    AI-specific behaviors are configured via parameters.
    """

    def __init__(
        self,
        session_name: str,
        executable: str,
        working_dir: Optional[str] = None,
        ai_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize TmuxController.

        Args:
            session_name: Name of the tmux session
            executable: Command to run (e.g., "claude", "gemini")
            working_dir: Working directory (defaults to current dir)
            ai_config: AI-specific configuration dictionary with:
                - startup_timeout: Seconds to wait for startup
                - response_timeout: Max seconds for responses
                - ready_check_interval: Seconds between ready checks
                - ready_stable_checks: Consecutive stable checks needed
                - ready_indicators: List of patterns indicating ready state
        """
        self.session_name = session_name
        self.executable = executable
        self.working_dir = working_dir or subprocess.check_output(
            ["pwd"], text=True
        ).strip()

        # AI-specific configuration with defaults
        self.config = ai_config or {}
        self.startup_timeout = self.config.get('startup_timeout', 10)
        self.response_timeout = self.config.get('response_timeout', 30)
        self.ready_check_interval = self.config.get('ready_check_interval', 0.5)
        self.ready_stable_checks = self.config.get('ready_stable_checks', 3)
        self.ready_indicators = self.config.get('ready_indicators', [])

    def _run_tmux_command(self, args: List[str]) -> subprocess.CompletedProcess:
        """
        Run a tmux command.

        Args:
            args: Command arguments to pass to tmux

        Returns:
            CompletedProcess result
        """
        cmd = ["tmux"] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    def session_exists(self) -> bool:
        """
        Check if the tmux session exists.

        Returns:
            True if session exists, False otherwise
        """
        result = self._run_tmux_command(["has-session", "-t", self.session_name])
        return result.returncode == 0

    def start_session(self, auto_confirm_trust: bool = True) -> bool:
        """
        Start AI CLI in a new tmux session.

        Args:
            auto_confirm_trust: Automatically confirm trust prompt (for Claude/Gemini)

        Returns:
            True if session started successfully, False otherwise
        """
        if self.session_exists():
            print(f"Session '{self.session_name}' already exists")
            return False

        # Create detached tmux session with AI executable
        result = self._run_tmux_command([
            "new-session",
            "-d",  # Detached
            "-s", self.session_name,  # Session name
            "-c", self.working_dir,  # Working directory
            self.executable  # Command to run (claude, gemini, etc.)
        ])

        if result.returncode != 0:
            print(f"Failed to start session: {result.stderr}")
            return False

        # Wait for AI to start (use configured timeout)
        init_wait = self.config.get('init_wait', 3)
        time.sleep(init_wait)

        # Auto-confirm trust prompt if requested
        if auto_confirm_trust:
            # Press Enter to confirm "Yes, proceed" (works for Claude/Gemini)
            self._run_tmux_command([
                "send-keys", "-t", self.session_name, "Enter"
            ])
            # Wait for AI to fully initialize
            time.sleep(init_wait)

        return True

    def send_command(self, command: str, submit: bool = True) -> bool:
        """
        Send a command to Claude Code.

        CRITICAL: Text and Enter must be sent separately to avoid multi-line input.

        Args:
            command: The text command to send
            submit: If True, send Enter to submit the command

        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.session_exists():
            print(f"Session '{self.session_name}' does not exist")
            return False

        # Send the command text
        result = self._run_tmux_command([
            "send-keys", "-t", self.session_name, command
        ])

        if result.returncode != 0:
            print(f"Failed to send command: {result.stderr}")
            return False

        # Send Enter separately to submit (not as part of send-keys command)
        if submit:
            time.sleep(0.1)  # Brief pause between text and Enter
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, "Enter"
            ])

            if result.returncode != 0:
                print(f"Failed to submit command: {result.stderr}")
                return False

        return True

    def capture_output(self, lines: int = 100, start_line: Optional[int] = None) -> str:
        """
        Capture output from the tmux pane.

        Args:
            lines: Number of lines to capture (default: 100)
            start_line: Starting line for capture (None = current visible pane)

        Returns:
            Captured output as string
        """
        if not self.session_exists():
            return ""

        args = ["capture-pane", "-t", self.session_name, "-p"]

        if start_line is not None:
            args.extend(["-S", str(start_line)])

        result = self._run_tmux_command(args)
        return result.stdout

    def capture_scrollback(self) -> str:
        """
        Capture entire scrollback buffer.

        Returns:
            Full scrollback buffer as string
        """
        if not self.session_exists():
            return ""

        result = self._run_tmux_command([
            "capture-pane", "-t", self.session_name, "-p", "-S", "-"
        ])
        return result.stdout

    def wait_for_ready(self, timeout: Optional[int] = None, check_interval: Optional[float] = None) -> bool:
        """
        Wait until AI is ready for next input.

        Strategy: Capture output repeatedly and wait until it stabilizes
        (no changes between captures), indicating AI has finished responding.

        Args:
            timeout: Maximum seconds to wait (uses config if not specified)
            check_interval: Seconds between checks (uses config if not specified)

        Returns:
            True if ready detected, False if timeout
        """
        if not self.session_exists():
            return False

        # Use configured values if not overridden
        timeout = timeout or self.response_timeout
        check_interval = check_interval or self.ready_check_interval
        required_stable_checks = self.ready_stable_checks

        start_time = time.time()
        previous_output = ""
        stable_count = 0

        while (time.time() - start_time) < timeout:
            current_output = self.capture_output()

            # Check if output has stabilized (no changes)
            if current_output == previous_output:
                stable_count += 1
                if stable_count >= required_stable_checks:
                    # Check for AI-specific ready indicators
                    if self.ready_indicators:
                        # Check if any ready indicator is present
                        if any(indicator in current_output for indicator in self.ready_indicators):
                            return True
                    else:
                        # No specific indicators configured, just use stabilization
                        return True
            else:
                stable_count = 0  # Reset if output changed

            previous_output = current_output
            time.sleep(check_interval)

        return False  # Timeout

    def kill_session(self) -> bool:
        """
        Terminate the tmux session.

        Returns:
            True if session killed successfully, False otherwise
        """
        if not self.session_exists():
            print(f"Session '{self.session_name}' does not exist")
            return False

        result = self._run_tmux_command([
            "kill-session", "-t", self.session_name
        ])

        return result.returncode == 0

    def attach_for_manual(self, read_only: bool = False) -> None:
        """
        Attach to the session for manual interaction.

        Note: This method will block until the user detaches.
        Use read_only=True to prevent accidental input.

        Args:
            read_only: If True, attach in read-only mode
        """
        if not self.session_exists():
            print(f"Session '{self.session_name}' does not exist")
            return

        args = ["attach-session", "-t", self.session_name]
        if read_only:
            args.append("-r")

        # This will block and take over the terminal
        subprocess.run(["tmux"] + args)

    def send_ctrl_c(self) -> bool:
        """
        Send Ctrl+C to cancel current operation.

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.session_exists():
            return False

        result = self._run_tmux_command([
            "send-keys", "-t", self.session_name, "C-c"
        ])

        return result.returncode == 0

    def get_status(self) -> dict:
        """
        Get session status information.

        Returns:
            Dictionary with session status
        """
        return {
            "session_name": self.session_name,
            "working_dir": self.working_dir,
            "exists": self.session_exists(),
        }
