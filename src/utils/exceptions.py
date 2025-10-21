"""
Custom Exceptions for AI Controller Operations

Defines exception hierarchy for clear error handling and recovery strategies.
"""


class AIControllerError(Exception):
    """Base exception for all AI controller errors."""
    pass


# Session-level errors
class SessionError(AIControllerError):
    """Base class for session-related errors."""
    pass


class SessionAlreadyExists(SessionError):
    """Raised when trying to create a session that already exists."""
    pass


class SessionDead(SessionError):
    """Raised when session no longer exists or has died unexpectedly."""
    pass


class SessionUnresponsive(SessionError):
    """Raised when session exists but is not responding to commands."""
    pass


class SessionStartupTimeout(SessionError):
    """Raised when AI session fails to start within expected time."""
    pass


# Command execution errors
class CommandError(AIControllerError):
    """Base class for command execution errors."""
    pass


class CommandTimeout(CommandError):
    """Raised when command execution exceeds timeout."""
    def __init__(self, message, partial_output=None):
        super().__init__(message)
        self.partial_output = partial_output


class CommandMalformed(CommandError):
    """Raised when command contains invalid characters or format."""
    pass


class AutomationPaused(CommandError):
    """Raised when automation is paused (manual takeover, explicit pause, etc.)."""
    pass


# Environment/setup errors
class EnvironmentError(AIControllerError):
    """Base class for environment setup errors."""
    pass


class ExecutableNotFound(EnvironmentError):
    """Raised when AI executable (claude/gemini) is not found in PATH."""
    def __init__(self, executable_name):
        self.executable_name = executable_name
        super().__init__(f"Executable '{executable_name}' not found in PATH")


class TmuxNotFound(EnvironmentError):
    """Raised when tmux is not installed or not in PATH."""
    pass


class TmuxError(EnvironmentError):
    """Raised when tmux command fails."""
    def __init__(self, message, command=None, return_code=None):
        super().__init__(message)
        self.command = command
        self.return_code = return_code


# Output/parsing errors
class OutputError(AIControllerError):
    """Base class for output capture/parsing errors."""
    pass


class OutputEmpty(OutputError):
    """Raised when output capture returns empty result unexpectedly."""
    pass


class OutputMalformed(OutputError):
    """Raised when output cannot be parsed correctly."""
    pass
