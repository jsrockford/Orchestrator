"""
Tmux Controller for AI CLI Interaction

This module provides programmatic control over AI CLI tools
(Claude Code, Gemini CLI, etc.) running in tmux sessions.
"""

import subprocess
import time
import shutil
import re
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
from ..utils.config_loader import get_config
from ..utils.retry import retry_with_backoff, STANDARD_RETRY
from ..utils.health_check import HealthChecker
from ..utils.auto_restart import AutoRestarter, RestartPolicy


ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


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
        ai_config: Optional[Dict[str, Any]] = None,
        executable_args: Optional[Sequence[str]] = None,
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
        exec_args = tuple(executable_args or ())

        spec = SessionSpec(
            name=session_name,
            executable=executable,
            working_dir=resolved_working_dir,
            args=exec_args
        )
        super().__init__(spec)

        # Maintain backward compatibility with direct attribute access
        self.session_name = spec.name
        self.executable = spec.executable
        self.working_dir = spec.working_dir
        self.executable_args: Tuple[str, ...] = exec_args

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
        self.loading_indicators = self.config.get('loading_indicators', [])
        self.loading_indicator_settle_time = float(self.config.get('loading_indicator_settle_time', 1.0))
        self.response_complete_markers = self.config.get('response_complete_markers', [])
        self.submit_key = self.config.get('submit_key', 'Enter')
        self.text_enter_delay = float(self.config.get('text_enter_delay', 0.1))
        self.post_text_delay = float(self.config.get('post_text_delay', 0.0))
        fallback_keys = self.config.get('submit_fallback_keys', ())
        if isinstance(fallback_keys, str):
            fallback_keys = [fallback_keys]
        self.submit_fallback_keys = tuple(str(key).strip() for key in fallback_keys if key)
        self.submit_retry_delay = float(self.config.get('submit_retry_delay', 0.0))
        ready_delay_config = self.config.get('ready_stabilization_delay')
        if ready_delay_config is None:
            self.ready_stabilization_delay = 2.0 if self.executable == "gemini" else 1.0
            ready_delay_explicit = False
        else:
            self.ready_stabilization_delay = float(ready_delay_config)
            ready_delay_explicit = True
        self._strip_ansi_for_markers = bool(self.config.get('strip_ansi_for_indicators', True))
        self.debug_wait_logging = bool(self.config.get('debug_wait_logging', False))
        if self.post_text_delay > 0:
            self.logger.info(
                "Configured post_text_delay=%.3fs (text_enter_delay=%.3fs)",
                self.post_text_delay,
                self.text_enter_delay,
            )
        if ready_delay_explicit and self.ready_stabilization_delay >= 0:
            self.logger.info(
                "Configured ready_stabilization_delay=%.3fs for executable '%s'",
                self.ready_stabilization_delay,
                self.executable,
            )
        if self._strip_ansi_for_markers:
            self.logger.debug("ANSI stripping enabled for indicator detection")
        self._pause_on_manual_clients = bool(self.config.get('pause_on_manual_clients', True))

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
        self._last_output_lines: List[str] = []

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

    def _send_literal_text(self, text: str) -> None:
        """
        Send text to tmux character-by-character in manageable chunks.

        Using tmux's literal mode ensures punctuation (e.g., apostrophes) is preserved.
        """
        if not text:
            return

        chunk_size = 100
        for idx in range(0, len(text), chunk_size):
            chunk = text[idx : idx + chunk_size]
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, "-l", "--", chunk
            ])
            if result.returncode != 0:
                raise TmuxError(
                    f"Failed to send literal chunk: {result.stderr}",
                    command=["send-keys", "-l"],
                    return_code=result.returncode,
                )
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

        if not self._pause_on_manual_clients:
            return

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

        self._snapshot_output_state()

        text_to_send = command.replace("\r\n", "\n")
        if "\n" in text_to_send:
            # Avoid premature submission in CLIs that treat literal newlines as Enter
            self.logger.debug("Normalizing multiline command for tmux send-keys")
        text_to_send = " ".join(filter(None, text_to_send.splitlines()))

        self._send_literal_text(text_to_send)

        if self.post_text_delay > 0:
            self.logger.info(
                "Sleeping %.3fs between literal send and submit",
                self.post_text_delay,
            )
            time.sleep(self.post_text_delay)

        if submit:
            if self.text_enter_delay > 0:
                self.logger.info(
                    "Sleeping %.3fs before sending submit key '%s'",
                    self.text_enter_delay,
                    self.submit_key,
                )
                time.sleep(self.text_enter_delay)
            else:
                self.logger.info("Sending submit key '%s' immediately", self.submit_key)

            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, self.submit_key
            ])
            stderr = result.stderr.strip() if result.stderr else ""
            log_suffix = f" (stderr: {stderr})" if stderr else ""
            self.logger.info(
                "Submit key '%s' send-keys returned %s%s",
                self.submit_key,
                result.returncode,
                log_suffix,
            )

            if result.returncode != 0:
                self.logger.error(f"Failed to submit command: {result.stderr}")
                raise TmuxError(
                    f"Failed to submit command: {result.stderr}",
                    command=["send-keys", "Enter"],
                    return_code=result.returncode
                )

            if self.submit_key and self.submit_key != "Enter":
                fallback = self._run_tmux_command([
                    "send-keys", "-t", self.session_name, "Enter"
                ])
                fallback_stderr = fallback.stderr.strip() if fallback.stderr else ""
                fallback_suffix = (
                    f" (stderr: {fallback_stderr})" if fallback_stderr else ""
                )
                self.logger.info(
                    "Fallback Enter send-keys returned %s%s",
                    fallback.returncode,
                    fallback_suffix,
                )
                if fallback.returncode != 0:
                    self.logger.warning(
                        "Fallback Enter send failed: %s",
                        fallback.stderr.strip() if fallback.stderr else "unknown",
                    )

            if self.submit_fallback_keys:
                self._trigger_fallback_submit_if_needed()

        self.logger.debug("Command sent successfully")
        return True

    def _snapshot_output_state(self) -> None:
        """
        Cache the current pane contents so subsequent output deltas only include new text.
        """
        try:
            raw_output = self.capture_output()
        except SessionBackendError:
            self._last_output_lines = []
            return

        self._last_output_lines = raw_output.splitlines()

    def _submission_in_progress(self) -> bool:
        """
        Detect whether the CLI has started processing the previously submitted command.

        We treat the presence of any configured loading indicator as evidence that the
        command was accepted and is currently running.
        """
        if not self.loading_indicators:
            return False
        if not self.session_exists():
            return False

        try:
            output = self.capture_output()
        except SessionBackendError:
            return False

        tail_text = "\n".join(self._tail_lines(output, limit=20))
        sanitized_tail = self._indicator_text(tail_text)
        return any(
            indicator and indicator in sanitized_tail
            for indicator in self.loading_indicators
        )

    def _trigger_fallback_submit_if_needed(self) -> None:
        """
        Send additional submit keys when the primary submit sequence appears to stall.
        """
        if not self.submit_fallback_keys:
            return

        delay = max(0.0, self.submit_retry_delay)
        if delay:
            time.sleep(delay)

        if self._submission_in_progress():
            self.logger.debug("Submission in progress; fallback submit keys not required")
            return

        for key in self.submit_fallback_keys:
            self.logger.warning(
                "Primary submit key did not trigger processing; sending fallback key '%s'",
                key,
            )
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, key
            ])
            stderr = result.stderr.strip() if result.stderr else ""
            suffix = f" (stderr: {stderr})" if stderr else ""
            self.logger.info(
                "Fallback submit key '%s' send-keys returned %s%s",
                key,
                result.returncode,
                suffix,
            )

            if result.returncode != 0:
                continue

            post_delay = delay if delay > 0 else 0.1
            if post_delay > 0:
                time.sleep(post_delay)

            if self._submission_in_progress():
                break

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
            normalized = text.replace("\r\n", "\n")
            normalized = " ".join(filter(None, normalized.splitlines()))
            self._send_literal_text(normalized)
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
            time.sleep(self.text_enter_delay)  # Brief pause before Enter
            result = self._run_tmux_command([
                "send-keys", "-t", self.session_name, self.submit_key
            ])
            if result.returncode != 0:
                raise SessionBackendError(f"Failed to send Enter: {result.stderr}")
            if self.submit_key and self.submit_key != "Enter":
                fallback = self._run_tmux_command([
                    "send-keys", "-t", self.session_name, "Enter"
                ])
                if fallback.returncode != 0:
                    self.logger.debug(
                        "Fallback Enter send failed in send_enter: %s",
                        fallback.stderr.strip() if fallback.stderr else "unknown",
                    )
            if self.submit_fallback_keys:
                self._trigger_fallback_submit_if_needed()
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
            if self._pause_on_manual_clients:
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

        tmux_defaults = {}
        try:
            tmux_defaults = get_config().get_section("tmux") or {}
        except Exception:  # pragma: no cover - config loader errors bubble later
            tmux_defaults = {}

        pane_width = self.config.get('pane_width')
        if pane_width is None:
            pane_width = tmux_defaults.get('default_pane_width')
        pane_height = self.config.get('pane_height')
        if pane_height is None:
            pane_height = tmux_defaults.get('default_pane_height')

        def _normalize_dimension(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                return None
            return numeric if numeric > 0 else None

        pane_width_int = _normalize_dimension(pane_width) or 200
        pane_height_int = _normalize_dimension(pane_height) or 50

        # Create detached tmux session with AI executable
        self.logger.debug(
            "Creating tmux session with executable: %s (pane %dx%d)",
            self.executable,
            pane_width_int,
            pane_height_int,
        )
        command = [
            "new-session",
            "-d",  # Detached
            "-s", self.session_name,  # Session name
            "-c", self.working_dir,  # Working directory
            "-x", str(pane_width_int),
            "-y", str(pane_height_int),
            self.executable,  # Command to run (claude, gemini, etc.)
            *self.executable_args,
        ]
        result = self._run_tmux_command(command)

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
        stabilization_delay = max(0.0, float(self.ready_stabilization_delay))
        if stabilization_delay > 0:
            self.logger.debug(
                "Ready indicator found, allowing input buffer to stabilize (%.3fs)...",
                stabilization_delay,
            )
            time.sleep(stabilization_delay)
        else:
            self.logger.debug("Ready indicator found; no additional stabilization delay configured")

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

        self.logger.debug(f"Waiting for startup ready indicators: {self.ready_indicators}")
        if self.loading_indicators:
            self.logger.debug(f"Will check for absence of loading indicators: {self.loading_indicators}")

        while (time.time() - start_time) < timeout:
            output = self.capture_output()
            search_output = self._indicator_text(output)

            # Check for AI-specific ready indicators
            if self.ready_indicators:
                self.logger.debug(f"Checking for indicators in {len(output)} chars of output")

                # First check if ready indicator is present
                ready_indicator_found = False
                for indicator in self.ready_indicators:
                    if indicator and indicator in search_output:
                        ready_indicator_found = True
                        self.logger.debug(f"Startup ready indicator found: '{indicator}'")
                        break

                if ready_indicator_found:
                    # Now check that no loading indicators are present
                    if self.loading_indicators:
                        has_loading = any(
                            loading_ind and loading_ind in search_output
                            for loading_ind in self.loading_indicators
                        )
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

    def get_last_output(self, *, tail_lines: int = 50) -> str:
        """
        Return newly captured output since the previous snapshot.

        Args:
            tail_lines: Maximum number of trailing lines to return if no delta
                can be computed (fallback for buffer resets).
        """
        if not self.session_exists():
            return ""

        try:
            raw_output = self.capture_output()
        except SessionBackendError:
            return ""

        if not raw_output:
            return ""

        current_lines = raw_output.splitlines()
        delta: List[str]

        if self._last_output_lines and len(current_lines) >= len(self._last_output_lines):
            prefix_length = self._common_prefix_length(self._last_output_lines, current_lines)
            delta = current_lines[prefix_length:]
        else:
            delta = current_lines[-tail_lines:]

        self._last_output_lines = current_lines
        return "\n".join(delta).strip()

    def reset_output_cache(self) -> None:
        """Forget cached output so the next capture returns the latest pane contents."""
        self._last_output_lines = []

    @staticmethod
    def _tail_lines(output: str, limit: int = 26) -> List[str]:
        if not output:
            return []
        lines = [line.rstrip() for line in output.splitlines() if line.strip()]
        return lines[-limit:]

    @staticmethod
    def _contains_any(haystack: str, needles: Sequence[str]) -> bool:
        return any(needle and needle in haystack for needle in needles)

    def _indicator_text(self, text: str) -> str:
        if not text:
            return ""
        if self._strip_ansi_for_markers:
            return ANSI_ESCAPE_RE.sub('', text)
        return text

    def _log_wait_debug(self, message: str, *args) -> None:
        if self.debug_wait_logging:
            self.logger.debug(message, *args)

    def _is_response_ready(self, tail_lines: Sequence[str]) -> bool:
        if not tail_lines:
            return False

        sanitized = [self._indicator_text(line) for line in tail_lines]
        relevant = list(sanitized[-5:]) if len(sanitized) > 5 else list(sanitized)
        tail_text = "\n".join(relevant)

        markers_found = [marker for marker in self.response_complete_markers if marker and marker in tail_text]
        indicators_found = [indicator for indicator in self.ready_indicators if indicator and indicator in tail_text]

        ready = True
        if self.response_complete_markers and not markers_found:
            ready = False
        if self.ready_indicators and not indicators_found:
            ready = False

        if self.debug_wait_logging:
            preview = tail_text[-400:] if len(tail_text) > 400 else tail_text
            self._log_wait_debug(
                "Ready check tail preview=%r markers_found=%s indicators_found=%s -> %s",
                preview,
                markers_found,
                indicators_found,
                ready,
            )

        return ready

    @staticmethod
    def _common_prefix_length(first: Sequence[str], second: Sequence[str]) -> int:
        limit = min(len(first), len(second))
        for idx in range(limit):
            if first[idx] != second[idx]:
                return idx
        return limit

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
        half_timeout_warning_emitted = False
        saw_loading_indicator = False
        loading_cleared_time: Optional[float] = None
        ready_gate_released = True

        self._log_wait_debug(
            "wait_for_ready start timeout=%ss interval=%.3fs stable_checks=%d",
            timeout,
            check_interval,
            required_stable_checks,
        )

        while (time.time() - start_time) < timeout:
            elapsed = time.time() - start_time
            if (
                not half_timeout_warning_emitted
                and timeout
                and elapsed >= (timeout / 2)
            ):
                self.logger.warning(
                    "wait_for_ready has been waiting %.2fs (>=50%% of timeout %ss) for session '%s'",
                    elapsed,
                    timeout,
                    self.session_name,
                )
                half_timeout_warning_emitted = True

            current_output = self.capture_output()
            tail_lines = self._tail_lines(current_output)
            sanitized_tail_lines = [self._indicator_text(line) for line in tail_lines]

            if sanitized_tail_lines and self.loading_indicators:
                tail_window = sanitized_tail_lines[-6:] if len(sanitized_tail_lines) > 6 else sanitized_tail_lines
                tail_text = "\n".join(tail_window)
                loading_present = self._contains_any(tail_text, self.loading_indicators)
                if loading_present:
                    if loading_cleared_time is not None:
                        self._log_wait_debug(
                            "Loading indicator reappeared after %.2fs; resetting settle timer",
                            time.time() - loading_cleared_time,
                        )
                    if not saw_loading_indicator:
                        self.logger.info("wait_for_ready detected processing start for session '%s'", self.session_name)
                    saw_loading_indicator = True
                    loading_cleared_time = None
                    ready_gate_released = False
                    self._log_wait_debug("Loading indicator detected; waiting for completion")
                    stable_count = 0
                    previous_output = current_output
                    time.sleep(check_interval)
                    continue
                if saw_loading_indicator and not loading_present:
                    if loading_cleared_time is None:
                        loading_cleared_time = time.time()
                        self.logger.info(
                            "wait_for_ready detected loading indicator cleared for session '%s'",
                            self.session_name,
                        )
                    cleared_elapsed = time.time() - loading_cleared_time
                    # Allow brief settling period after indicator clears
                    settle_required = max(check_interval, self.loading_indicator_settle_time)
                    if cleared_elapsed < settle_required:
                        self._log_wait_debug(
                            "Loading indicator just cleared (%.2fs); waiting one more interval for output to settle",
                            cleared_elapsed,
                        )
                        previous_output = current_output
                        time.sleep(check_interval)
                        continue
                    ready_gate_released = True
                    self._log_wait_debug(
                        "Loading indicator cleared and settle requirement satisfied (%.2fs >= %.2fs)",
                        cleared_elapsed,
                        settle_required,
                    )

            # Check if output has stabilized (no changes)
            if current_output == previous_output:
                stable_count += 1
                elapsed = time.time() - start_time
                self._log_wait_debug(
                    "Output stable (%d/%d) after %.2fs",
                    stable_count,
                    required_stable_checks,
                    elapsed,
                )
                if (
                    stable_count >= required_stable_checks
                    and ready_gate_released
                    and self._is_response_ready(sanitized_tail_lines)
                ):
                    self._log_wait_debug("Ready confirmed after %.2fs", elapsed)
                    if saw_loading_indicator:
                        self.logger.info(
                            "wait_for_ready processed completion via stability fallback for session '%s'",
                            self.session_name,
                        )
                    return True
            else:
                if stable_count:
                    elapsed = time.time() - start_time
                    self._log_wait_debug(
                        "Output changed after %.2fs; reset stable_count (was %d)",
                        elapsed,
                        stable_count,
                    )
                stable_count = 0  # Reset if output changed

            previous_output = current_output
            time.sleep(check_interval)

        elapsed_total = time.time() - start_time
        self._log_wait_debug("wait_for_ready timed out after %.2fs", elapsed_total)
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
