# Orchestrator Code Documentation

This document provides a detailed overview of the project's code structure, designed to help new team members understand the architecture and key components.

## 1. Configuration (`config.yaml`)

The `config.yaml` file is the central point for configuring the entire application. It defines the behavior of AI controllers, logging, and orchestration logic.

-   **AI-Specific Sections (`claude`, `gemini`, `codex`, `qwen`):** Each AI has its own section defining startup timeouts, response characteristics, prompt markers, and the executable command. This allows for fine-tuning the interaction with each specific CLI tool.
-   **`tmux` Section:** Configures default tmux session names and global settings like pane dimensions.
-   **`logging` Section:** Controls the log level, file path, and rotation for the application logs (`logs/tmux.log`).
-   **`response_validation` Section:** Defines patterns for detecting errors or harmless noise in AI responses, enabling automatic retries.
-   **`completion_detection` Section:** Configures the hybrid system for detecting when a conversation is complete. It includes the explicit `[[PROJECT_COMPLETE]]` signal and fallback phrases.
-   **`control_channel` Section:** Enables and configures the named pipe (`/tmp/orchestrator_control`) for human-in-the-loop interaction.
-   **`loop_detection` Section:** Configures the rules for detecting and handling repetitive, looping behavior from agents.
-   **`post_completion_validation` Section:** Defines checks to run after a project is marked complete, such as verifying that test files were created.

## 2. Source Code (`src/**`)

The core application logic resides in the `src` directory.

### `src/controllers/`

This directory contains the components responsible for interacting directly with the AI CLI tools running in tmux.

-   **`session_backend.py`:** Defines the abstract base class `SessionBackend`, which specifies the interface that all controllers must implement (`start`, `kill`, `send_text`, `capture_output`, etc.).
-   **`tmux_controller.py`:** The primary concrete implementation of `SessionBackend`. The `TmuxController` class handles all the low-level `tmux` commands for session management, sending keys, and capturing pane output. It is AI-agnostic.
-   **AI-Specific Controllers (`claude_controller.py`, `gemini_controller.py`, etc.):** These are thin wrappers around `TmuxController`. They inherit from it and simply load their specific configurations from `config.yaml` (e.g., `ClaudeController` loads settings from the `claude:` block).

### `src/orchestrator/`

This is the heart of the system, managing the high-level collaborative workflow.

-   **`orchestrator.py`:** The `DevelopmentTeamOrchestrator` is the top-level class. It holds the registered controllers and provides the main entry point (`start_discussion`) for initiating a collaborative session.
-   **`conversation_manager.py`:** The `ConversationManager` is the engine of a discussion. It manages the turn-taking logic (round-robin by default), calls the orchestrator to dispatch commands, and uses helper modules to detect consensus, conflicts, or loops. **This is where the main orchestration loop lives.**
-   **`control_channel.py`:** Implements the `ControlChannel` class, which creates and listens to the named pipe (FIFO). It polls for commands like `PAUSE`, `RESUME`, `KEY`, and `TEXT` without blocking the main loop.
-   **`context_manager.py`:** Acts as the "memory" for a conversation. It stores the history of turns, decisions, and other significant events.
-   **`message_router.py`:** Facilitates communication between agents by taking the response from one agent and formatting it into the context for the next agent's prompt.
-   **`validation.py`:** Contains the `PostCompletionValidator` class, which runs checks after a project is marked complete to ensure quality (e.g., checking for the existence of test files).

### `src/utils/`

This directory contains shared utilities used across the application.

-   **`config_loader.py`:** Provides a singleton `ConfigLoader` for accessing `config.yaml` settings.
-   **`output_parser.py`:** A critical utility for cleaning the raw text captured from tmux panes, removing UI artifacts, ANSI codes, and separating prompts from responses.
-   **`exceptions.py`:** Defines custom exception classes for specific error conditions (e.g., `SessionDead`, `CommandTimeout`).
-   **`retry.py`, `health_check.py`, `auto_restart.py`:** A suite of utilities for making the system more resilient by handling transient errors, checking session health, and automatically restarting failed sessions.

## 3. Examples (`examples/**`)

This directory contains standalone Python scripts that demonstrate how to use the orchestration framework.

-   **`run_orchestrated_discussion.py`:** The primary entry point for running a multi-agent discussion. It parses command-line arguments, builds the specified controllers, and kicks off the `facilitate_discussion` loop in the `ConversationManager`.
-   **`run_code_review_simulation.py`:** A more complex, real-world example demonstrating a collaborative code review task between two agents.
-   **`run_counting_conversation.py`:** A simple, deterministic smoke test where agents count upwards in sequence, useful for verifying basic turn-taking.
-   **`run_controller_probe.py` and `run_single_ai_wait_probe.py`:** Utilities for manually testing and debugging individual controllers.

## 4. Scripts (`scripts/**`)

This directory contains helper scripts for interacting with the running system.

-   **`orchestrator_control.sh`:** A user-friendly bash script that acts as a client for the control channel. It provides simple commands (`pause`, `resume`, `say`, `key`) that write the corresponding structured messages into the named pipe, making it easy for a human to control the live session.

## 5. Tests (`tests/**`)

This directory contains all the unit and integration tests for the project, written for `pytest`.

-   The test file structure generally mirrors the `src` directory (e.g., `test_conversation_manager.py` tests `src/orchestrator/conversation_manager.py`).
-   **`test_control_channel.py` and `test_pause_resume.py`:** These files contain tests specifically for the new human-in-the-loop feature, verifying that the named pipe works and that the `PAUSE`/`RESUME`/`KEY`/`TEXT` commands are handled correctly by the `ConversationManager`.
-   Other files test individual components like the output parser, retry logic, and controller functions in isolation.
