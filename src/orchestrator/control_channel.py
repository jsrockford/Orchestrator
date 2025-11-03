"""
Control channel interface for human-in-the-loop commands.

This module owns the named pipe (FIFO) that external processes can write to in
order to influence an active orchestration run. The ControlChannel is designed
to be polled from the main event loop without blocking normal agent handling.
"""

from __future__ import annotations

import errno
import os
import select
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from ..utils.logger import get_logger


_DEFAULT_PIPE_PATH = "/tmp/orchestrator_control"
_READ_CHUNK_SIZE = 4096


@dataclass(frozen=True)
class ControlCommand:
    """
    Represents a parsed control command emitted by a human operator.

    Attributes:
        name: Uppercase command verb (e.g. ``PAUSE``).
        args: Positional segments following the command verb.
        raw: Original line read from the pipe (without trailing newlines).
    """

    name: str
    args: List[str]
    raw: str


class ControlChannel:
    """
    Manage a named pipe that external writers can use to issue control commands.

    The channel is intentionally lightweight: callers should periodically invoke
    :meth:`check_for_commands` to pull any waiting requests. Commands are parsed
    into ``ControlCommand`` instances, leaving higher-level coordination to the
    orchestrator.
    """

    def __init__(self, pipe_path: str | os.PathLike[str] | None = None) -> None:
        self.logger = get_logger("orchestrator.control_channel")
        configured = pipe_path or os.environ.get("ORCHESTRATOR_CONTROL_PIPE")
        self.pipe_path = Path(configured or _DEFAULT_PIPE_PATH)
        self._fd: Optional[int] = None
        self._buffer: str = ""

    # --------------------------------------------------------------------- #
    # Lifecycle helpers
    # --------------------------------------------------------------------- #
    def setup_pipe(self) -> None:
        """
        Ensure the FIFO exists and is open for non-blocking reads.

        If the pipe already exists it will be replaced. Any stale file that is
        not a FIFO is treated as an error to avoid quietly deleting unrelated
        data.
        """

        self.cleanup()
        self.pipe_path.parent.mkdir(parents=True, exist_ok=True)

        if self.pipe_path.exists():
            if not stat.S_ISFIFO(self.pipe_path.stat().st_mode):
                raise RuntimeError(
                    f"Control channel target {self.pipe_path} exists and is not a FIFO"
                )
            try:
                self.pipe_path.unlink()
            except OSError as exc:  # noqa: BLE001
                raise RuntimeError(f"Failed to remove stale control pipe {self.pipe_path}: {exc}") from exc

        try:
            os.mkfifo(self.pipe_path)
        except OSError as exc:  # noqa: BLE001
            raise RuntimeError(f"Unable to create control pipe at {self.pipe_path}: {exc}") from exc

        try:
            # Opening read/write keeps the FIFO from blocking if no external writer is attached.
            self._fd = os.open(self.pipe_path, os.O_RDWR | os.O_NONBLOCK)
        except OSError as exc:  # noqa: BLE001
            self._fd = None
            raise RuntimeError(f"Unable to open control pipe {self.pipe_path}: {exc}") from exc

        self.logger.debug("Control pipe ready at %s", self.pipe_path)

    def cleanup(self, *, close_fd: bool = True) -> None:
        """
        Close the FIFO descriptor and remove the pipe from disk.

        Args:
            close_fd: When False, only remove the pipe without touching the file descriptor.
        """

        if close_fd and self._fd is not None:
            try:
                os.close(self._fd)
            except OSError as exc:  # noqa: BLE001
                self.logger.debug("Error closing control pipe FD: %s", exc)
            finally:
                self._fd = None

        if self.pipe_path.exists():
            try:
                self.pipe_path.unlink()
            except OSError as exc:  # noqa: BLE001
                self.logger.debug("Unable to remove control pipe %s: %s", self.pipe_path, exc)

        self._buffer = ""

    # --------------------------------------------------------------------- #
    # Command polling
    # --------------------------------------------------------------------- #
    def check_for_commands(self) -> List[ControlCommand]:
        """
        Poll the pipe for any waiting commands.

        Returns:
            A list of parsed commands (may be empty). Invalid lines are logged
            and discarded.
        """

        if self._fd is None:
            self.logger.debug("Control pipe not set up; attempting recreation")
            try:
                self.setup_pipe()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Unable to recreate control pipe: %s", exc)
                return []

        try:
            ready, _, _ = select.select([self._fd], [], [], 0)
        except OSError as exc:  # noqa: BLE001
            if exc.errno in (errno.EBADF, errno.ENODEV):
                self.logger.warning("Control pipe descriptor became invalid; recreating: %s", exc)
                self.setup_pipe()
            else:
                self.logger.error("Control pipe select() failed: %s", exc)
            return []

        if not ready:
            return []

        commands: List[ControlCommand] = []
        try:
            chunk = os.read(self._fd, _READ_CHUNK_SIZE)
        except OSError as exc:  # noqa: BLE001
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return []
            self.logger.error("Control pipe read failed: %s", exc)
            return []

        if not chunk:
            # Writer closed; keep reader open but reset buffer.
            self._buffer = ""
            return []

        try:
            decoded = chunk.decode("utf-8")
        except UnicodeDecodeError:
            decoded = chunk.decode("utf-8", errors="ignore")
            self.logger.warning("Stripped invalid UTF-8 bytes from control command chunk")

        self._buffer += decoded
        lines, self._buffer = self._split_buffer(self._buffer)

        for line in lines:
            if not line.strip():
                continue
            try:
                command = self._parse_command(line)
            except ValueError as exc:
                self.logger.warning("Ignoring invalid control command '%s': %s", line.strip(), exc)
                continue
            commands.append(command)

        return commands

    @staticmethod
    def _split_buffer(buffer: str) -> tuple[List[str], str]:
        """
        Split the buffer into complete lines and return the remaining fragment.
        """

        if "\n" not in buffer:
            return [], buffer

        parts = buffer.splitlines(keepends=True)
        complete: List[str] = []
        remainder: List[str] = []

        for part in parts:
            if part.endswith("\n"):
                complete.append(part.rstrip("\r\n"))
            else:
                remainder.append(part)

        return complete, "".join(remainder)

    # --------------------------------------------------------------------- #
    # Parsing helpers
    # --------------------------------------------------------------------- #
    def _parse_command(self, line: str) -> ControlCommand:
        """
        Convert a raw command line into a structured ``ControlCommand``.

        Expected format is ``COMMAND_NAME optional arguments``. Command names
        are normalized to uppercase; arguments preserve original spacing except
        for the leading/trailing whitespace that is trimmed. Arguments are
        provided both as a list (space-delimited) and in the raw attribute.
        """

        stripped = line.strip()
        if not stripped:
            raise ValueError("empty command")

        parts = stripped.split()
        if not parts:
            raise ValueError("missing command verb")

        name = parts[0].upper()
        args: Iterable[str] = parts[1:]
        return ControlCommand(name=name, args=list(args), raw=stripped)
