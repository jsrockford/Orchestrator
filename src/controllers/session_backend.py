"""
Session backend abstraction for interactive AI CLI tools.

This interface allows the orchestration layer to target different process
transport mechanisms (tmux, expect, PTY, etc.) while presenting the same
surface area to higher-level controllers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence


@dataclass(frozen=True)
class SessionSpec:
    """
    Declarative session configuration passed to backends when creating a new
    interactive CLI instance.

    Attributes:
        name: Logical identifier for the session.
        executable: CLI executable to launch (e.g., "claude", "gemini").
        working_dir: Filesystem path to use as the process working directory.
        env: Optional environment overrides to apply when spawning the process.
        args: Optional extra arguments to append after the executable.
    """

    name: str
    executable: str
    working_dir: str
    env: Optional[Mapping[str, str]] = None
    args: Sequence[str] = field(default_factory=tuple)


class SessionBackendError(RuntimeError):
    """Base exception for backend failures."""


class SessionNotFoundError(SessionBackendError):
    """Raised when an operation targets a session that does not exist."""


class SessionBackend(ABC):
    """
    Transport interface for automating interactive AI CLI tools.

    Concrete implementations (e.g., tmux, expect, PTY) encapsulate the process
    management mechanics while higher-level controllers focus on orchestration
    logic such as readiness heuristics, command scheduling, and health checks.
    """

    def __init__(self, spec: SessionSpec) -> None:
        self.spec = spec

    # --- Lifecycle ----------------------------------------------------- #

    @abstractmethod
    def start(self) -> None:
        """
        Launch the CLI process according to the stored session specification.

        Raises:
            SessionBackendError: If the session fails to start.
        """

    @abstractmethod
    def session_exists(self) -> bool:
        """
        Return True if the session currently exists and is reachable.
        """

    @abstractmethod
    def kill(self) -> None:
        """
        Terminate the underlying session.

        Raises:
            SessionNotFoundError: If no session exists to terminate.
        """

    # --- Input --------------------------------------------------------- #

    @abstractmethod
    def send_text(self, text: str) -> None:
        """
        Inject literal text into the session input buffer without submitting.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot deliver the text.
        """

    @abstractmethod
    def send_enter(self) -> None:
        """
        Submit the current line (typically by sending the Enter key).

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot deliver the keystroke.
        """

    @abstractmethod
    def send_ctrl_c(self) -> None:
        """
        Interrupt the current operation (Ctrl+C equivalent).

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot deliver the signal.
        """

    # --- Output -------------------------------------------------------- #

    @abstractmethod
    def capture_output(
        self,
        *,
        start_line: Optional[int] = None,
        lines: Optional[int] = None,
    ) -> str:
        """
        Capture text from the session's visible buffer.

        Args:
            start_line: Starting line offset. Backend-specific semantics:
                - Tmux: 0 = top of buffer, negative = relative to top
                - Other backends may define differently
                If omitted, captures the visible pane.
            lines: Number of lines to include. If omitted, implementations
                should default to the backend's standard capture window.

        Returns:
            Captured output as a single string.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot capture output.
        """

    @abstractmethod
    def capture_scrollback(self) -> str:
        """
        Capture the full scrollback buffer for post-mortem analysis.

        Returns:
            The complete scrollback as a single string.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot capture output.
        """

    # --- Observability ------------------------------------------------- #

    @abstractmethod
    def list_clients(self) -> Sequence[str]:
        """
        Enumerate active client connections (for manual takeover detection).

        Returns:
            A sequence of client identifiers.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If the backend cannot list clients.
        """

    @abstractmethod
    def attach(self, read_only: bool = False) -> None:
        """
        Attach the current terminal to the session for manual observation.

        Args:
            read_only: If True, attach in read-only mode when supported.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionBackendError: If attachment fails.
        """

    # --- Diagnostics --------------------------------------------------- #

    def get_status(self) -> Mapping[str, object]:
        """
        Return backend-specific status information for debugging.

        Implementations may override to add richer fields.
        """
        return {
            "session": self.spec.name,
            "exists": self.session_exists(),
        }
