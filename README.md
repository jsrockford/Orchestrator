# AI Development Team Orchestration System

A proof-of-concept system that enables Claude Code and Gemini CLI to collaborate as an autonomous development team through orchestrated conversations in tmux sessions.

## Overview

This project provides an orchestration layer that coordinates multiple AI CLI tools, allowing them to engage in structured discussions, reach consensus, detect conflicts, and collaboratively work on software development tasks. The system supports both automated workflows and manual intervention, with built-in pause/resume capabilities when humans attach to sessions.

### Key Features

- **Multi-AI Orchestration**: Coordinate conversations between Claude Code and Gemini CLI
- **Tmux-Based Control**: Programmatic command injection and output capture via tmux sessions
- **Automation-Aware**: Automatically pauses when humans attach to sessions, resumes when they detach
- **Turn-Based Conversations**: Managed turn-taking with consensus and conflict detection
- **Message Routing**: Cross-AI communication with context preservation
- **Clean Output Parsing**: Filters CLI UI elements to produce readable transcripts
- **Session Lifecycle Management**: One-command setup, execution, and teardown

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Orchestration Engine                        │
│  (Command Dispatch, Queue Management, Automation Pause)  │
└────────────┬─────────────────────────┬──────────────────┘
             │                         │
┌────────────▼──────────┐  ┌──────────▼──────────────────┐
│  Conversation Manager │  │     Context Manager         │
│  (Turn-taking, Flow)  │  │  (State, History, Memory)   │
└────────────┬──────────┘  └──────────┬──────────────────┘
             │                         │
             └──────────┬──────────────┘
                        │
           ┌────────────▼────────────┐
           │    Message Router       │
           │  (AI-to-AI Messages)    │
           └────────────┬────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│           Controller Infrastructure           │
│  TmuxController → ClaudeController/Gemini     │
└───────────────────────────────────────────────┘
```

## Project Structure

```
OrchestratorTest/
├── src/
│   ├── controllers/           # Session management and CLI control
│   │   ├── session_backend.py    # Abstract backend interface
│   │   ├── tmux_controller.py    # Tmux implementation
│   │   ├── claude_controller.py  # Claude Code wrapper
│   │   └── gemini_controller.py  # Gemini CLI wrapper
│   ├── orchestrator/          # Core orchestration logic
│   │   ├── orchestrator.py       # Command dispatch & queue management
│   │   ├── conversation_manager.py  # Turn-taking & consensus detection
│   │   ├── context_manager.py    # History & state persistence
│   │   └── message_router.py     # AI-to-AI message routing
│   └── utils/                 # Supporting utilities
│       ├── output_parser.py      # CLI output cleaning
│       ├── retry.py              # Retry logic with backoff
│       ├── health_check.py       # Session health monitoring
│       └── auto_restart.py       # Automatic session recovery
├── examples/
│   └── run_orchestrated_discussion.py  # Main CLI tool
├── config.yaml                # Session configuration
└── logs/                      # Conversation transcripts
```

## Installation

### Prerequisites

- **Python 3.8+**
- **tmux** (`sudo apt install tmux` on Ubuntu/Debian)
- **Claude Code CLI** - [Install from anthropic.com](https://claude.com/claude-code)
- **Gemini CLI** - [Install from Google](https://ai.google.dev/gemini-api/docs/cli)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd OrchestratorTest
```

2. Activate the virtual environment (if using one):
```bash
source venv/bin/activate  # On Linux/macOS
# or
venv\Scripts\activate  # On Windows
```

3. Install Python dependencies:
```bash
pip install pyyaml  # Only external dependency
```

4. Configure CLI paths in `config.yaml`:
```yaml
claude:
  executable: claude  # Or /path/to/claude if not in PATH

gemini:
  executable: gemini  # Or /path/to/gemini if not in PATH
```

## Usage

### Quick Start: Automated Discussion

Run a complete orchestrated discussion with automatic setup and cleanup:

```bash
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  --auto-start \
  --kill-existing \
  --cleanup-after \
  --log-file logs/discussion.log \
  "Discuss the best approach for implementing user authentication"
```

**Flags:**
- `--auto-start`: Automatically launch tmux sessions if they don't exist
- `--kill-existing`: Kill any existing Claude/Gemini sessions before starting
- `--cleanup-after`: Kill sessions after the discussion completes
- `--log-file`: Save conversation transcript to a file

### Manual Session Control

Start sessions manually for observation:

```bash
# Terminal 1: Start Claude
tmux new-session -s claude claude --dangerously-skip-permissions

# Terminal 2: Start Gemini (screen reader mode produces linear text)
tmux new-session -s gemini gemini --yolo --screenReader

# Terminal 3: Run orchestrated discussion (reuses existing sessions)
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  "Review the codebase and suggest refactoring opportunities"
```

### Advanced Options

Control session behavior, startup timing, and CLI flags:

```bash
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  --auto-start \
  --startup-timeout 60 \
  --max-turns 10 \
  --history-size 50 \
  --claude-session my-claude \
  --claude-executable "claude --dangerously-skip-permissions" \
  --claude-startup-timeout 15 \
  --gemini-session my-gemini \
  --gemini-executable "gemini --yolo --screenReader" \
  --gemini-startup-timeout 20 \
  --log-file logs/custom-discussion.log \
  "Design a REST API for a task management system"
```

### Manual Intervention During Discussions

The system automatically pauses automation when you attach to a session:

```bash
# In another terminal, attach to observe/intervene:
tmux attach -t claude -r  # Read-only mode (recommended)
# or
tmux attach -t claude     # Full control (automation pauses)

# Detach to resume automation:
# Press Ctrl+B, then D
```

The orchestrator detects attached clients and queues commands until you detach.

## Configuration

Edit `config.yaml` to customize behavior:

```yaml
claude:
  executable: claude
  executable_args:
    - "--dangerously-skip-permissions"
  startup_timeout: 10
  response_marker: "●"
  ready_indicators:
    - "────────────────────────"
    - "? for shortcuts"
  submit_key: "Enter"
  text_enter_delay: 0.1

gemini:
  executable: gemini
  executable_args:
    - "--yolo"
    - "--screenReader"
  startup_timeout: 20
  response_marker: "✦"
  ready_indicators:
    - "Type your message or @path/to/file"
    - "Model:"
  submit_key: "C-m"
  text_enter_delay: 0.5

tmux:
  claude_session: claude
  gemini_session: gemini
  capture_lines: 200         # Lines to capture per output read
```

## Testing

### Unit Tests

Run individual component tests:

```bash
# Test output parser cleanup
python3 -m pytest test_output_parser_cleanup.py

# Test automation pause/resume
python3 -m pytest test_automation_pause.py

# Test conversation management
python3 -m pytest test_conversation_manager.py

# Test orchestrator discussion
python3 -m pytest test_orchestrator_discussion_pause.py
```

### Integration Tests

Test with live CLI sessions:

```bash
# Full automated lifecycle test
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  --auto-start --kill-existing --cleanup-after \
  --max-turns 3 \
  --log-file logs/test-run.log \
  "Test message: Say hello to each other"

# Check the log
cat logs/test-run.log
```

### Manual Testing

Verify individual controllers:

```bash
# Test Claude controller
python3 test_controller_auto.py

# Test Gemini controller
python3 test_gemini_controller.py

# Test dual AI operation
python3 test_dual_ai.py
```

## Example Output

```
=== Conversation Transcript ===
0: claude
  Prompt:
    claude, we're collaborating on: Design a REST API for task management.
    Provide your next contribution focusing on actionable steps.
  Response:
    Let me outline the core endpoints we'll need:

    1. Tasks CRUD:
       - POST /api/tasks - Create task
       - GET /api/tasks - List all tasks
       - GET /api/tasks/:id - Get single task
       - PUT /api/tasks/:id - Update task
       - DELETE /api/tasks/:id - Delete task

    2. Authentication:
       - POST /api/auth/login
       - POST /api/auth/logout
       - POST /api/auth/refresh
-
1: gemini
  Prompt:
    gemini, we're collaborating on: Design a REST API for task management.
    Provide your next contribution focusing on actionable steps.
    Recent context: claude: Let me outline the core endpoints...
  Response:
    Great start! I'd add:

    3. Task Assignment:
       - POST /api/tasks/:id/assign - Assign to user
       - GET /api/users/:id/tasks - Get user's tasks

    4. Filtering & Search:
       - GET /api/tasks?status=pending&assignee=user123
       - GET /api/tasks/search?q=urgent

    Should we define the data models next?
-

=== Shared Context Summary ===
claude: Let me outline the core endpoints... | gemini: Great start! I'd add...
```

## Troubleshooting

### "Session not found" errors

Ensure tmux sessions are running or use `--auto-start`:
```bash
tmux list-sessions  # Check existing sessions
```

### Automation doesn't resume after detaching

The orchestrator should detect detachment within ~1 second. If stuck, check:
```bash
tmux list-clients -t claude  # Should show no clients when detached
```

### Output capture is empty

Increase capture buffer size in `config.yaml`:
```yaml
tmux:
  capture_lines: 500  # Default: 200
```

### Commands not being sent

Check automation status:
```python
controller.get_status()["automation"]
# Should show: {"paused": false, ...}
```

## Development

### Adding a New Controller Backend

Implement the `SessionBackend` interface:

```python
from src.controllers.session_backend import SessionBackend, SessionSpec

class MyBackend(SessionBackend):
    def start(self) -> None:
        # Launch your CLI tool
        pass

    def send_text(self, text: str) -> None:
        # Send text without newline
        pass

    def send_enter(self) -> None:
        # Send newline/enter key
        pass

    # ... implement remaining abstract methods
```

### Extending the Orchestrator

Add custom turn logic in `ConversationManager`:

```python
def determine_next_speaker(self, context):
    # Custom logic to pick next AI
    if should_prioritize_claude(context):
        return "claude"
    return super().determine_next_speaker(context)
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Claude Code agent instructions
- **[GEMINI.md](GEMINI.md)** - Gemini CLI agent instructions
- **[Tasks.md](Tasks.md)** - Development task tracking
- **[CodexConcerns.md](CodexConcerns.md)** - Architecture discussion and decisions
- **[TIMING_GUIDE.md](TIMING_GUIDE.md)** - Performance tuning guide
- **[examples/README.md](examples/README.md)** - Example usage patterns

## Success Criteria

- ✅ **Basic Conversation**: Facilitates 10+ turn conversations between AIs
- ✅ **Automation Pause**: Detects manual attachment and pauses within 1 second
- ✅ **Turn Management**: Round-robin with consensus/conflict detection
- ✅ **Context Preservation**: Maintains conversation state across sessions
- ✅ **Output Cleaning**: Removes CLI UI noise from transcripts
- ⏳ **Error Recovery**: Handles AI timeout/errors gracefully (in progress)
- ⏳ **Task Completion**: Can complete simple projects from requirements (planned)

## Contributing

This is a proof-of-concept project. When contributing:

1. Update `Tasks.md` to mark completed items
2. Add tests for new functionality
3. Post design discussions to `MessageBoard.md`
4. Update your respective instruction file (CLAUDE.md, GEMINI.md, or AGENTS.md)

## License

[Specify License]

## Acknowledgments

Built using Claude Code CLI and Gemini CLI as the foundation for AI-to-AI collaboration.
