"""
Tmux Controller for Claude Code Interaction

This module provides programmatic control over a Claude Code instance
running in a tmux session.
"""

import subprocess
import time
from typing import Optional, List


class TmuxController:
    """Controls Claude Code running in a tmux session."""

    def __init__(self, session_name: str = "claude-poc", working_dir: Optional[str] = None):
        """
        Initialize TmuxController.

        Args:
            session_name: Name of the tmux session
            working_dir: Working directory for Claude Code (defaults to current dir)
        """
        self.session_name = session_name
        self.working_dir = working_dir or subprocess.check_output(
            ["pwd"], text=True
        ).strip()

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
        Start Claude Code in a new tmux session.

        Args:
            auto_confirm_trust: Automatically confirm trust prompt

        Returns:
            True if session started successfully, False otherwise
        """
        if self.session_exists():
            print(f"Session '{self.session_name}' already exists")
            return False

        # Create detached tmux session with Claude Code
        result = self._run_tmux_command([
            "new-session",
            "-d",  # Detached
            "-s", self.session_name,  # Session name
            "-c", self.working_dir,  # Working directory
            "claude"  # Command to run
        ])

        if result.returncode != 0:
            print(f"Failed to start session: {result.stderr}")
            return False

        # Wait for Claude Code to start
        time.sleep(3)

        # Auto-confirm trust prompt if requested
        if auto_confirm_trust:
            # Press Enter to confirm "Yes, proceed" (already selected by default)
            self._run_tmux_command([
                "send-keys", "-t", self.session_name, "Enter"
            ])
            # Wait for Claude to fully initialize
            time.sleep(3)

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

    def wait_for_ready(self, timeout: int = 30, check_interval: float = 0.5) -> bool:
        """
        Wait until Claude Code is ready for next input.

        Strategy: Capture output repeatedly and wait until it stabilizes
        (no changes between captures), indicating Claude has finished responding.

        Args:
            timeout: Maximum seconds to wait
            check_interval: Seconds between checks

        Returns:
            True if ready detected, False if timeout
        """
        if not self.session_exists():
            return False

        start_time = time.time()
        previous_output = ""
        stable_count = 0
        required_stable_checks = 3  # Need 3 consecutive stable checks

        while (time.time() - start_time) < timeout:
            current_output = self.capture_output()

            # Check if output has stabilized (no changes)
            if current_output == previous_output:
                stable_count += 1
                if stable_count >= required_stable_checks:
                    # Also check that we're showing the prompt (ready state)
                    if "────────" in current_output or "? for shortcuts" in current_output:
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
