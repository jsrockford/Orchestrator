# AI Development Team Orchestration System

## Project Overview

This project is a proof-of-concept (POC) to develop and test methods for programmatically orchestrating multiple AI CLI tools (including Claude Code, Gemini CLI, Codex, and Qwen) running in a native Ubuntu 24.04 server environment. The primary goal is to create a system that can send automated commands to the AI CLIs, capture and parse their responses, and enable collaborative, multi-agent workflows.

### Gemini's Role

Gemini's role in this development team is advisory, planning, and troubleshooting. Gemini is not permitted to change code files unless specifically asked to by 'Don'

The project will be developed in Python and will explore three potential implementation strategies for controlling the CLI session:
1.  **Tmux-Based Control:** Using `tmux` to manage the session and send commands.
2.  **Expect-Based Control:** Using an `expect` script or the `pexpect` library to automate interaction.
3.  **Direct PTY Control:** Using Python's `pty` module to create a pseudo-terminal.

The success of this POC will be determined by the ability to reliably send commands, receive output, and switch between automated and manual control of the Claude Code CLI.

## Operating Instructions

*   **Project Directories**:
    *   The project folder and primary code repository is `/home/dgray/Projects/Orchestrator`. All code changes must be made within this directory.
    *   The worktree for testing is `/home/dgray/Projects/TestOrch`. The user, Don, is responsible for copying files and running tests in this directory.
*   **Virtual Environment**:
    *   This project uses a Python virtual environment located at `venv/`.
    *   Remember to activate it (`source venv/bin/activate`) before running any Python scripts. Always ask for confirmation before executing project code.
*   **Appending to Files**:
    *   To append content to a file (like `MessageBoard.md`), you MUST follow this three-step process to avoid overwriting data:
    *   1.  **Read:** Use `read_file` to load the full, existing content of the file.
    *   2.  **Concatenate:** Add your new content to the existing content in memory.
    *   3.  **Write:** Use `write_file` to save the *entire combined content* back to the file.

    NEVER insert a comment in 'MessageBoard.md' ALWAYS append!

## Building and Running

## Development Conventions

*   **Code Style:** The project is expected to follow standard Python coding conventions (PEP 8).
*   **Project Structure:** The `spec.md` outlines a clear project structure, separating controllers, utilities, and tests into their own directories. This structure should be adhered to.
*   **Testing:** The project plan includes unit and integration tests. New features should be accompanied by corresponding tests.
*   **Logging:** Comprehensive logging is required for debugging and monitoring the interaction with the CLI.
*   **Configuration:** A `config.yaml` file will be used to manage settings for the application, such as timeouts and session names.
