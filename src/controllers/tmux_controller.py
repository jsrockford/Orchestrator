"""
Tmux Controller for AI CLI Interaction

This module provides programmatic control over AI CLI tools
(Claude Code, Gemini CLI, etc.) running in tmux sessions.
"""

import subprocess
import time
import shutil
from collections import deque
from typing import Optional, List, Dict, Any, Mapping, Sequence, Deque, Tuple

from .session_backend import (
    SessionBackend,
    SessionSpec,
    SessionBackendError,
    SessionNotFoundError
)
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
from ..utils.auto_restart import AutoRestarter, RestartPolicy


class TmuxController(SessionBackend):
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
        # Resolve working directory
        resolved_working_dir = working_dir or subprocess.check_output(
            ["pwd"], text=True
        ).strip()

        # Create SessionSpec and initialize parent
        spec = SessionSpec(
            name=session_name,
            executable=executable,
            working_dir=resolved_working_dir
        )
        super().__init__(spec)

        # Maintain backward compatibility with direct attribute access
        self.session_name = spec.name
        self.executable = spec.executable
        self.working_dir = spec.working_dir

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

        # Initialize auto-restarter
        restart_policy_str = self.config.get('restart_policy', 'on_failure')
        try:
            restart_policy = RestartPolicy(restart_policy_str)
        except ValueError:
            self.logger.warning(f"Invalid restart_policy '{restart_policy_str}', using ON_FAILURE")
            restart_policy = RestartPolicy.ON_FAILURE

        self.auto_restarter = AutoRestarter(
            policy=restart_policy,
            max_restart_attempts=self.config.get('max_restart_attempts', 3),
            restart_window=self.config.get('restart_window', 300.0),
            initial_backoff=self.config.get('restart_initial_backoff', 5.0),
            max_backoff=self.config.get('restart_max_backoff', 60.0)
        )

        # Automation/manual takeover state
        self._automation_paused: bool = False
        self._automation_pause_reason: Optional[str] = None
        self._manual_clients: Sequence[str] = []
        self._pending_commands: Deque[Tuple[str, bool]] = deque()

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

    # ========================================================================
    # Automation / Manual Takeover Helpers
    # ========================================================================

    @property
    def automation_paused(self) -> bool:
        """Return True when automation is currently paused."""
        return self._automation_paused

    @property
    def automation_pause_reason(self) -> Optional[str]:
        """Reason describing why automation is paused (if any)."""
        return self._automation_pause_reason

    @property
    def manual_clients(self) -> Sequence[str]:
        """Return the most recently observed manual clients."""
        return self._manual_clients

    @property
    def pending_command_count(self) -> int:
        """Return the number of queued commands awaiting automation resume."""
        return len(self._pending_commands)

    def get_pending_commands(self) -> List[Tuple[str, bool]]:
        """Return a snapshot of queued commands."""
        return list(self._pending_commands)

    def pause_automation(self, reason: str = "manual") -> None:
        """Pause automation explicitly (commands will be queued)."""
        self._set_automation_paused(True, reason=reason, flush_pending=False)

    def resume_automation(self, flush_pending: bool = True) -> None:
        """
        Resume automation (optionally flushing any queued commands).

        Args:
            flush_pending: If True, execute queued commands after resuming.
        """
        self._set_automation_paused(False, flush_pending=flush_pending)

    def _set_automation_paused(
        self,
        paused: bool,
        *,
        reason: Optional[str] = None,
        flush_pending: bool = True
    ) -> None:
        """
        Internal helper for toggling automation state.
        """
        if paused:
            if not self._automation_paused:
                self.logger.info(f"Pausing automation (reason: {reason})")
            self._automation_paused = True
            self._automation_pause_reason = reason
        else:
            if self._automation_paused:
                self.logger.info("Resuming automation")
            self._automation_paused = False
            self._automation_pause_reason = None
            if flush_pending:
                self._drain_pending_commands()

    def _update_manual_control_state(self) -> None:
        """
        Inspect tmux clients and pause/resume automation as appropriate.
        """
        try:
            clients = self.list_clients()
        except SessionNotFoundError:
            self._manual_clients = []
            return
        except SessionBackendError as exc:
            self.logger.debug(f"Failed to list clients for manual control state: {exc}")
            return

        previous_clients = list(self._manual_clients)
        self._manual_clients = clients
        if clients:
            self._set_automation_paused(True, reason="manual-attach", flush_pending=False)
        elif (
            previous_clients
            and self._automation_paused
            and self._automation_pause_reason == "manual-attach"
        ):
            self._set_automation_paused(False, flush_pending=True)

    def _enqueue_command(self, command: str, submit: bool) -> None:
        """Queue a command to be replayed once automation resumes."""
        self._pending_commands.append((command, submit))
        self.logger.info(
            "Queued command due to automation pause "
            f"(pending={len(self._pending_commands)})"
        )

    def _drain_pending_commands(self) -> None:
        """
        Dispatch queued commands now that automation has resumed.
        """
        if not self._pending_commands:
            return

        self.logger.info(f"Draining {len(self._pending_commands)} queued command(s)")
        while self._pending_commands and not self._automation_paused:
            command, submit = self._pending_commands.popleft()
            try:
                self._send_command_internal(command, submit)
            except Exception as exc:  # noqa: BLE001 - log and requeue
                self.logger.error(
                    "Failed to flush queued command; leaving in queue",
                    exc_info=exc
                )
                self._pending_commands.appendleft((command, submit))
                break

    def _send_command_internal(self, command: str, submit: bool) -> bool:
        """
        Core implementation shared by send_command() and the queue flusher.

        Returns:
            True if the command was dispatched successfully.
        """
        if not self.session_exists():
            self.logger.error(f"Cannot send command - session '{self.session_name}' does not exist")
            raise SessionDead(f"Session '{self.session_name}' does not exist")

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

    # ========================================================================
    # SessionBackend Interface Implementation
    # ========================================================================

    def start(self) -> None:
        """
        Launch the CLI process according to the session specification.

        This is the SessionBackend interface method. Calls start_session() internally.

        Raises:
            SessionBackendError: If the session fails to start.
        """
        try:
            self.start_session(auto_confirm_trust=True)
        except (SessionAlreadyExists, SessionStartupTimeout, TmuxError) as e:
            raise SessionBackendError(f"Failed to start session: {e}") from e

    def send_text(self, text: str) -> None:
        """
        Inject literal text into the session input buffer without submitting.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot deliver the text.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, text
            ])
            if result.returncode != 0:
                raise SessionBackendError(f"Failed to send text: {result.stderr}")
        except TmuxError as e:
            raise SessionBackendError(f"Failed to send text: {e}") from e

    def send_enter(self) -> None:
        """
        Submit the current line (send Enter key).

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot deliver the keystroke.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            time.sleep(0.1)  # Brief pause before Enter
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, "Enter"
            ])
            if result.returncode != 0:
                raise SessionBackendError(f"Failed to send Enter: {result.stderr}")
        except TmuxError as e:
            raise SessionBackendError(f"Failed to send Enter: {e}") from e

    def send_ctrl_c(self) -> None:
        """
        Interrupt the current operation (Ctrl+C equivalent).

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot deliver the signal.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, "C-c"
            ])
            if result.returncode != 0:
                raise SessionBackendError(f"Failed to send Ctrl+C: {result.stderr}")
        except TmuxError as e:
            raise SessionBackendError(f"Failed to send Ctrl+C: {e}") from e

    def capture_output(
        self,
        *,
        start_line: Optional[int] = None,
        lines: Optional[int] = None,
    ) -> str:
        """
        Capture text from the session's visible buffer.

        Args:
            start_line: Starting line offset (tmux semantics: 0 = top of buffer,
                negative values = offset from top). If omitted, captures visible pane.
            lines: Number of lines to include (not used in tmux implementation,
                controlled by tmux's default capture window).

        Returns:
            Captured output as a single string.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot capture output.

        Note:
            Tmux's -S flag uses top-relative indexing where 0 is the first line
            in the scrollback. Use negative values to offset from the top.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            args = ["capture-pane", "-t", self.session_name, "-p"]
            if start_line is not None:
                args.extend(["-S", str(start_line)])
            result = self._run_tmux_command(args)
            return result.stdout
        except TmuxError as e:
            raise SessionBackendError(f"Failed to capture output: {e}") from e

    def capture_scrollback(self) -> str:
        """
        Capture the full scrollback buffer for post-mortem analysis.

        Returns:
            The complete scrollback as a single string.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot capture output.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            result = self._run_tmux_command([
                "capture-pane", "-t", self.session_name, "-p", "-S", "-"
            ])
            return result.stdout
        except TmuxError as e:
            raise SessionBackendError(f"Failed to capture scrollback: {e}") from e

    def list_clients(self) -> Sequence[str]:
        """
        Enumerate active client connections (for manual takeover detection).

        Returns:
            A sequence of client identifiers.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot list clients.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            result = self._run_tmux_command([
                "list-clients", "-t", self.session_name
            ])
            if result.returncode == 0 and result.stdout.strip():
                return [line.strip() for line in result.stdout.strip().split('\n')]
            return []
        except TmuxError as e:
            raise SessionBackendError(f"Failed to list clients: {e}") from e

    def attach(self, read_only: bool = False) -> None:
        """
        Attach the current terminal to the session for manual observation.

        Args:
            read_only: If True, attach in read-only mode.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If attachment fails.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            args = ["attach-session", "-t", self.session_name]
            if read_only:
                args.append("-r")
            # Preemptively pause automation before handing control to a human
            self.pause_automation(reason="manual-attach")
            # This will block and take over the terminal
            subprocess.run(["tmux"] + args, check=True)
        except subprocess.CalledProcessError as e:
            raise SessionBackendError(f"Failed to attach: {e}") from e
        finally:
            # Re-evaluate client list on detach to resume automation as needed
            self._update_manual_control_state()

    def kill(self) -> None:
        """
        Terminate the underlying session.

        Raises:
            SessionNotFoundError: If no session exists to terminate.
        """
        if not self.session_exists():
            raise SessionNotFoundError(f"Session '{self.session_name}' does not exist")

        try:
            result = self._run_tmux_command([
                "kill-session", "-t", self.session_name
            ])
            if result.returncode != 0:
                raise SessionBackendError(f"Failed to kill session: {result.stderr}")
        except TmuxError as e:
            raise SessionBackendError(f"Failed to kill session: {e}") from e

    def get_status(self) -> Mapping[str, object]:
        """
        Return backend-specific status information for debugging.

        Overrides base implementation to include health and restart stats.
        """
        return {
            "session": self.spec.name,
            "exists": self.session_exists(),
            "working_dir": self.spec.working_dir,
            "executable": self.spec.executable,
            "automation": {
                "paused": self._automation_paused,
                "reason": self._automation_pause_reason,
                "pending_commands": self.pending_command_count,
                "manual_clients": list(self._manual_clients),
            },
            "health": self.get_health_stats(),
            "restart": self.get_restart_stats()
        }

    # ========================================================================
    # Legacy Methods (maintain backward compatibility)
    # ========================================================================

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

        # Wait for AI to start (brief initial wait for process to spawn)
        init_wait = self.config.get('init_wait', 3)
        self.logger.debug(f"Waiting {init_wait}s for AI process to spawn")
        time.sleep(init_wait)

        # Auto-confirm trust prompt if requested
        if auto_confirm_trust:
            self.logger.debug("Auto-confirming trust prompt")
            # Press Enter to confirm "Yes, proceed" (works for Claude/Gemini)
            self._run_tmux_command([
                "send-keys", "-t", self.session_name, "Enter"
            ])
            # Brief wait for Enter to be processed
            time.sleep(1)

        # Wait for AI to be fully ready (detect ready indicators)
        self.logger.debug("Waiting for AI to be fully ready...")
        if not self.wait_for_startup(timeout=self.startup_timeout):
            self.logger.error("AI failed to show ready indicators within timeout")
            raise SessionStartupTimeout(f"Session failed to be ready within {self.startup_timeout}s")

        # Stabilization delay after detecting ready indicator
        # Ensures input buffer is fully initialized and ready for first command
        # Critical for Gemini which can show prompt before buffer is ready
        stabilization_delay = 2.0 if self.executable == "gemini" else 1.0
        self.logger.debug(f"Ready indicator found, allowing input buffer to stabilize ({stabilization_delay}s)...")
        time.sleep(stabilization_delay)

        # Verify session is actually ready
        if not self.session_exists():
            self.logger.error("Session creation appeared to succeed but session doesn't exist")
            raise SessionStartupTimeout("Session failed to start properly")

        self.logger.info(f"Session '{self.session_name}' started successfully and ready")
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
            True if command sent successfully, False if it was queued due to
            automation being paused.

        Raises:
            SessionDead: If session no longer exists (not retried)
            TmuxError: If command fails after retries
        """
        self.logger.info(f"Sending command: {command[:50]}{'...' if len(command) > 50 else ''}")

        self._update_manual_control_state()
        if self._automation_paused:
            pause_reason = self._automation_pause_reason or "unknown"
            self.logger.warning(
                "Automation currently paused (reason: %s); queueing command",
                pause_reason
            )
            self._enqueue_command(command, submit)
            return False

        try:
            return self._send_command_internal(command, submit)
        except SessionDead:
            raise
        except TmuxError:
            raise

    def wait_for_startup(self, timeout: Optional[int] = None) -> bool:
        """
        Wait until AI has fully started and is ready for first input.

        Looks for startup ready indicators AND ensures no loading indicators present.
        This is different from wait_for_ready() which waits for response completion.

        Args:
            timeout: Maximum seconds to wait (uses startup_timeout from config if not specified)

        Returns:
            True if startup indicators detected and no loading indicators, False if timeout
        """
        if not self.session_exists():
            return False

        timeout = timeout or self.startup_timeout
        check_interval = 0.5
        start_time = time.time()

        # Get loading indicators from config (if available)
        loading_indicators = self.config.get('loading_indicators', [])

        self.logger.debug(f"Waiting for startup ready indicators: {self.ready_indicators}")
        if loading_indicators:
            self.logger.debug(f"Will check for absence of loading indicators: {loading_indicators}")

        while (time.time() - start_time) < timeout:
            output = self.capture_output()

            # Check for AI-specific ready indicators
            if self.ready_indicators:
                self.logger.debug(f"Checking for indicators in {len(output)} chars of output")

                # First check if ready indicator is present
                ready_indicator_found = False
                for indicator in self.ready_indicators:
                    if indicator in output:
                        ready_indicator_found = True
                        self.logger.debug(f"Startup ready indicator found: '{indicator}'")
                        break

                if ready_indicator_found:
                    # Now check that no loading indicators are present
                    if loading_indicators:
                        has_loading = any(loading_ind in output for loading_ind in loading_indicators)
                        if has_loading:
                            self.logger.debug("Ready indicator found but loading indicator still present, waiting...")
                            time.sleep(check_interval)
                            continue

                    # Ready indicator present and no loading indicators
                    self.logger.debug("Startup complete: ready indicator found, no loading indicators")
                    return True
                else:
                    self.logger.debug(f"Indicators not found. Looking for: {self.ready_indicators}")
            else:
                # Fallback: if no indicators configured, just check for any output
                if len(output.strip()) > 50:  # Arbitrary threshold for "has started"
                    return True

            time.sleep(check_interval)

        self.logger.warning(f"Startup timeout after {timeout}s")
        return False

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
        Terminate the tmux session (legacy method for backward compatibility).

        Delegates to kill() interface method.

        Returns:
            True if session killed successfully, False otherwise
        """
        try:
            self.kill()
            return True
        except (SessionNotFoundError, SessionBackendError):
            return False

    def attach_for_manual(self, read_only: bool = False) -> None:
        """
        Attach to the session for manual interaction (legacy method).

        Delegates to attach() interface method.

        Note: This method will block until the user detaches.
        Use read_only=True to prevent accidental input.

        Args:
            read_only: If True, attach in read-only mode
        """
        try:
            self.attach(read_only=read_only)
        except (SessionNotFoundError, SessionBackendError) as e:
            print(f"Failed to attach: {e}")

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

    def restart_session(self, reason: str = "manual", auto_confirm_trust: bool = True) -> bool:
        """
        Restart the session (kill and start fresh).

        Args:
            reason: Reason for restart (for logging)
            auto_confirm_trust: Auto-confirm trust prompt on restart

        Returns:
            True if restart succeeded, False otherwise
        """
        self.logger.info(f"Restarting session (reason: {reason})")

        # Kill existing session if it exists
        if self.session_exists():
            self.logger.debug("Killing existing session")
            self.kill_session()
            time.sleep(1)  # Brief pause to ensure cleanup

        # Start new session
        try:
            self.start_session(auto_confirm_trust=auto_confirm_trust)
            self.logger.info("Session restarted successfully")

            # Reset health checker after successful restart
            self.health_checker.reset()

            return True
        except Exception as e:
            self.logger.error(f"Failed to restart session: {e}")
            return False

    def auto_restart_if_needed(self, reason: str = "unknown") -> bool:
        """
        Automatically restart session if policy allows and conditions are met.

        Args:
            reason: Reason for potential restart

        Returns:
            True if restart was attempted and succeeded, False otherwise
        """
        def restart_func():
            return self.restart_session(reason=reason)

        return self.auto_restarter.attempt_restart(
            restart_func=restart_func,
            reason=reason,
            wait_before_restart=True
        )

    def get_restart_stats(self) -> dict:
        """
        Get auto-restart statistics.

        Returns:
            Dictionary with restart metrics
        """
        return self.auto_restarter.get_stats()
