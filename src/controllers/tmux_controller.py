"""
Tmux Controller for AI CLI Interaction

This module provides programmatic control over AI CLI tools
(Claude Code, Gemini CLI, etc.) running in tmux sessions.
"""

import subprocess
import time
import shutil
from typing import Optional, List, Dict, Any

from ..utils.exceptions import (
    SessionAlreadyExists,
    SessionDead,
    SessionUnresponsive,
    SessionStartupTimeout,
    CommandTimeout,
    ExecutableNotFound,
    TmuxNotFound,
    TmuxError
)
from ..utils.logger import get_logger
from ..utils.retry import retry_with_backoff, STANDARD_RETRY
from ..utils.health_check import HealthChecker


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

        # Set up logging
        self.logger = get_logger(f"{__name__}.{session_name}")
        self.logger.info(f"Initializing TmuxController for {executable} in session {session_name}")

        # AI-specific configuration with defaults
        self.config = ai_config or {}
        self.startup_timeout = self.config.get('startup_timeout', 10)
        self.response_timeout = self.config.get('response_timeout', 30)
        self.ready_check_interval = self.config.get('ready_check_interval', 0.5)
        self.ready_stable_checks = self.config.get('ready_stable_checks', 3)
        self.ready_indicators = self.config.get('ready_indicators', [])

        # Verify environment on initialization
        self._verify_environment()

        # Initialize health checker
        self.health_checker = HealthChecker(
            check_interval=self.config.get('health_check_interval', 30.0),
            response_timeout=self.config.get('health_check_timeout', 5.0),
            max_failed_checks=self.config.get('max_failed_health_checks', 3)
        )

    def _verify_environment(self):
        """
        Verify that required executables are available.

        Raises:
            TmuxNotFound: If tmux is not installed
            ExecutableNotFound: If AI executable is not in PATH
        """
        # Check tmux
        if not shutil.which('tmux'):
            self.logger.error("tmux not found in PATH")
            raise TmuxNotFound("tmux is not installed or not in PATH")

        # Check AI executable
        if not shutil.which(self.executable):
            self.logger.error(f"Executable '{self.executable}' not found in PATH")
            raise ExecutableNotFound(self.executable)

        self.logger.debug("Environment verification passed")

    @retry_with_backoff(max_attempts=2, initial_delay=0.5, exceptions=(TmuxError,))
    def _run_tmux_command(self, args: List[str]) -> subprocess.CompletedProcess:
        """
        Run a tmux command with error handling and automatic retry.

        Args:
            args: Command arguments to pass to tmux

        Returns:
            CompletedProcess result

        Raises:
            TmuxError: If tmux command fails unexpectedly after retries
        """
        cmd = ["tmux"] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Log tmux errors (but don't raise for expected failures like has-session)
            if result.returncode != 0 and result.stderr:
                self.logger.debug(f"tmux command returned {result.returncode}: {' '.join(args)}")
                self.logger.debug(f"stderr: {result.stderr.strip()}")

            return result
        except Exception as e:
            self.logger.error(f"Failed to run tmux command: {' '.join(args)}")
            self.logger.error(f"Error: {e}")
            raise TmuxError(f"Failed to execute tmux command: {e}", command=cmd)

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
            True if session started successfully

        Raises:
            SessionAlreadyExists: If session with this name already exists
            SessionStartupTimeout: If session fails to become ready in time
        """
        self.logger.info(f"Starting session '{self.session_name}'")

        if self.session_exists():
            self.logger.error(f"Session '{self.session_name}' already exists")
            raise SessionAlreadyExists(f"Session '{self.session_name}' already exists")

        # Create detached tmux session with AI executable
        self.logger.debug(f"Creating tmux session with executable: {self.executable}")
        result = self._run_tmux_command([
            "new-session",
            "-d",  # Detached
            "-s", self.session_name,  # Session name
            "-c", self.working_dir,  # Working directory
            self.executable  # Command to run (claude, gemini, etc.)
        ])

        if result.returncode != 0:
            self.logger.error(f"Failed to create tmux session: {result.stderr}")
            raise TmuxError(
                f"Failed to start session: {result.stderr}",
                command=["new-session"],
                return_code=result.returncode
            )

        # Wait for AI to start (use configured timeout)
        init_wait = self.config.get('init_wait', 3)
        self.logger.debug(f"Waiting {init_wait}s for AI to initialize")
        time.sleep(init_wait)

        # Auto-confirm trust prompt if requested
        if auto_confirm_trust:
            self.logger.debug("Auto-confirming trust prompt")
            # Press Enter to confirm "Yes, proceed" (works for Claude/Gemini)
            self._run_tmux_command([
                "send-keys", "-t", self.session_name, "Enter"
            ])
            # Wait for AI to fully initialize
            time.sleep(init_wait)

        # Verify session is actually ready
        if not self.session_exists():
            self.logger.error("Session creation appeared to succeed but session doesn't exist")
            raise SessionStartupTimeout("Session failed to start properly")

        self.logger.info(f"Session '{self.session_name}' started successfully")
        return True

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, exceptions=(TmuxError,))
    def send_command(self, command: str, submit: bool = True) -> bool:
        """
        Send a command to AI CLI with automatic retry on transient failures.

        CRITICAL: Text and Enter must be sent separately to avoid multi-line input.

        Args:
            command: The text command to send
            submit: If True, send Enter to submit the command

        Returns:
            True if command sent successfully

        Raises:
            SessionDead: If session no longer exists (not retried)
            TmuxError: If command fails after retries
        """
        self.logger.info(f"Sending command: {command[:50]}{'...' if len(command) > 50 else ''}")

        if not self.session_exists():
            self.logger.error(f"Cannot send command - session '{self.session_name}' does not exist")
            raise SessionDead(f"Session '{self.session_name}' does not exist")

        # Send the command text
        result = self._run_tmux_command([
            "send-keys", "-t", self.session_name, command
        ])

        if result.returncode != 0:
            self.logger.error(f"Failed to send command text: {result.stderr}")
            raise TmuxError(
                f"Failed to send command: {result.stderr}",
                command=["send-keys"],
                return_code=result.returncode
            )

        # Send Enter separately to submit (not as part of send-keys command)
        if submit:
            time.sleep(0.1)  # Brief pause between text and Enter
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, "Enter"
            ])

            if result.returncode != 0:
                self.logger.error(f"Failed to submit command: {result.stderr}")
                raise TmuxError(
                    f"Failed to submit command: {result.stderr}",
                    command=["send-keys", "Enter"],
                    return_code=result.returncode
                )

        self.logger.debug("Command sent successfully")
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

    def perform_health_check(self, check_type: str = "session_exists") -> dict:
        """
        Perform health check on the session.

        Args:
            check_type: Type of health check to perform:
                - "session_exists": Basic liveness check
                - "output_responsive": Check if session produces output
                - "command_echo": Full responsiveness test with test command

        Returns:
            Dictionary with health check results

        Raises:
            ValueError: If check_type is invalid
        """
        if check_type == "session_exists":
            result = self.health_checker.check_session_exists(self.session_exists)
        elif check_type == "output_responsive":
            result = self.health_checker.check_output_responsive(
                lambda: self.capture_output(lines=50),
                min_output_length=10
            )
        elif check_type == "command_echo":
            result = self.health_checker.check_command_echo(
                send_command_func=lambda cmd: self.send_command(cmd, submit=True),
                wait_func=self.wait_for_ready,
                capture_func=self.capture_output,
                test_command="# health_check"
            )
        else:
            raise ValueError(f"Invalid check_type: {check_type}")

        return {
            "healthy": result.healthy,
            "timestamp": result.timestamp.isoformat(),
            "check_type": result.check_type,
            "details": result.details,
            "error_message": result.error_message,
            "consecutive_failures": self.health_checker.consecutive_failures,
            "is_healthy": self.health_checker.is_healthy()
        }

    def get_health_stats(self) -> dict:
        """
        Get health check statistics.

        Returns:
            Dictionary with health metrics
        """
        return self.health_checker.get_stats()

    def is_healthy(self) -> bool:
        """
        Check if session is currently considered healthy.

        Returns:
            True if session is healthy, False otherwise
        """
        return self.health_checker.is_healthy()

    def get_status(self) -> dict:
        """
        Get session status information including health.

        Returns:
            Dictionary with session status
        """
        return {
            "session_name": self.session_name,
            "working_dir": self.working_dir,
            "exists": self.session_exists(),
            "health": self.get_health_stats()
        }
