# Project: Claude Code WSL Interaction POC

## Project Overview

This project is a proof-of-concept (POC) to develop and test methods for programmatically interacting with the Claude Code CLI running in a Windows Subsystem for Linux (WSL) environment. The primary goal is to create a system that can send automated commands to the Claude Code CLI, capture and parse its responses, while still allowing a user to interact with the CLI manually.

The project will be developed in Python and will explore three potential implementation strategies for controlling the CLI session:
1.  **Tmux-Based Control:** Using `tmux` to manage the session and send commands.
2.  **Expect-Based Control:** Using an `expect` script or the `pexpect` library to automate interaction.
3.  **Direct PTY Control:** Using Python's `pty` module to create a pseudo-terminal.

The success of this POC will be determined by the ability to reliably send commands, receive output, and switch between automated and manual control of the Claude Code CLI.

## Building and Running

As this is a Python-based project, it is expected to have a `requirements.txt` file for managing dependencies.

**To set up the environment:**

```bash
# It is recommended to use a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**To run the main application:**

```bash
python src/main.py
```

**To run tests:**

```bash
# Details on the testing framework are not yet specified, but a common command is:
pytest
```

*TODO: The exact commands for running the application and tests need to be finalized based on the project's structure and chosen libraries.*

## Development Conventions

*   **Code Style:** The project is expected to follow standard Python coding conventions (PEP 8).
*   **Project Structure:** The `spec.md` outlines a clear project structure, separating controllers, utilities, and tests into their own directories. This structure should be adhered to.
*   **Testing:** The project plan includes unit and integration tests. New features should be accompanied by corresponding tests.
*   **Logging:** Comprehensive logging is required for debugging and monitoring the interaction with the CLI.
*   **Configuration:** A `config.yaml` file will be used to manage settings for the application, such as timeouts and session names.
