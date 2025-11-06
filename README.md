# AI Development Team Orchestration System

A proof-of-concept system that enables Claude Code and Gemini CLI to collaborate as an autonomous development team through orchestrated conversations in tmux sessions. **Successfully validated with real-world code review tasks** (October 2025).

## Overview

This project provides an orchestration layer that coordinates multiple AI CLI tools, allowing them to engage in structured discussions, reach consensus, detect conflicts, and collaboratively work on software development tasks. The system supports both automated workflows and manual intervention, with built-in pause/resume capabilities when humans attach to sessions.

### Key Features

- **Multi-AI Orchestration**: Coordinate conversations between Claude Code, Gemini CLI, Codex (Aider), and Qwen CLI
- **Web UI Interface**: React-based frontend for visual monitoring and control of AI sessions
- **Integrated API Server**: FastAPI REST/WebSocket endpoints embedded in orchestrator for seamless web integration
- **Tmux-Based Control**: Programmatic command injection and output capture via tmux sessions
- **Automation-Aware**: Automatically pauses when humans attach to sessions, resumes when they detach
- **Turn-Based Conversations**: Managed turn-taking with consensus and conflict detection
- **Message Routing**: Cross-AI communication with context preservation
- **Clean Output Parsing**: Filters CLI UI elements to produce readable transcripts
- **Session Lifecycle Management**: One-command setup, execution, and teardown
- **Human Control Channel**: Named pipe-based control for pause/resume and manual intervention

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
Orchestrator/
├── src/
│   ├── controllers/           # Session management and CLI control
│   │   ├── session_backend.py    # Abstract backend interface
│   │   ├── tmux_controller.py    # Tmux implementation
│   │   ├── claude_controller.py  # Claude Code wrapper
│   │   ├── gemini_controller.py  # Gemini CLI wrapper
│   │   ├── codex_controller.py   # Codex (Aider) wrapper
│   │   └── qwen_controller.py    # Qwen CLI wrapper
│   ├── orchestrator/          # Core orchestration logic
│   │   ├── orchestrator.py       # Command dispatch & queue management
│   │   ├── web_api.py            # FastAPI REST/WebSocket endpoints
│   │   ├── conversation_manager.py  # Turn-taking & consensus detection
│   │   ├── context_manager.py    # History & state persistence
│   │   ├── message_router.py     # AI-to-AI message routing
│   │   └── control_channel.py    # Human control via named pipe
│   └── utils/                 # Supporting utilities
│       ├── output_parser.py      # CLI output cleaning
│       ├── retry.py              # Retry logic with backoff
│       ├── health_check.py       # Session health monitoring
│       └── auto_restart.py       # Automatic session recovery
├── frontend/                  # React web UI (Vite + Tailwind)
│   ├── src/
│   │   ├── components/           # UI components
│   │   │   ├── ConversationWindow.tsx  # AI session display
│   │   │   ├── ControlButton.tsx       # Session controls
│   │   │   ├── PromptInput.tsx         # Message input
│   │   │   └── ...
│   │   └── App.tsx               # Main application
│   └── package.json
├── scripts/
│   ├── run_api_server.py         # Start integrated API server
│   └── orchestrator_control.sh   # Manual control helper
├── examples/
│   └── run_orchestrated_discussion.py  # Main CLI tool
├── config.yaml                # Session configuration
└── logs/                      # Conversation transcripts
```

## Installation

### Prerequisites

- **Python 3.8+**
- **Node.js 18+** (for web UI frontend)
- **tmux** (`sudo apt install tmux` on Ubuntu/Debian)
- **Claude Code CLI** - [Install from anthropic.com](https://claude.com/claude-code)
- **Gemini CLI** - [Install from Google](https://ai.google.dev/gemini-api/docs/cli)
- **Codex (Aider)** - [Install from aider.chat](https://aider.chat/) (optional)
- **Qwen CLI** - [Install from Alibaba Cloud](https://help.aliyun.com/zh/model-studio/developer-reference/qwen-cli) (optional)

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
pip install -r requirements.txt
# Core dependencies: pyyaml, fastapi, uvicorn, websockets
```

4. Install frontend dependencies:
```bash
cd frontend
npm install
npm run build  # Build production assets
cd ..
```

5. Configure CLI paths in `config.yaml`:
```yaml
claude:
  executable: claude  # Or /path/to/claude if not in PATH

gemini:
  executable: gemini  # Or /path/to/gemini if not in PATH

codex:
  executable: aider  # Codex uses Aider CLI

qwen:
  executable: qwen  # Or /path/to/qwen if not in PATH
```

## Usage

### Web UI (Recommended)

Start the integrated API server and web UI for visual monitoring and control:

```bash
# Terminal 1: Start the orchestrator with embedded API server
source venv/bin/activate
python scripts/run_api_server.py --host 0.0.0.0 --port 8000 --start-sessions

# Terminal 2: Start the frontend dev server (development mode)
cd frontend
npm run dev
```

Then open your browser to `http://localhost:5173` to access the web interface.

**Web UI Features:**
- Real-time monitoring of all AI session outputs
- Control buttons for each session (Pause, Resume, Arrow keys, Enter)
- Edit AI instruction files directly from the browser
- Project settings and file browsing
- Multi-model selection and management

**Production deployment:**
```bash
# Build frontend production assets
cd frontend
npm run build

# Serve via integrated API server (serves static files)
python scripts/run_api_server.py --host 0.0.0.0 --port 8000
# Access at http://localhost:8000
```

### CLI Mode: Automated Discussion

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
# Terminal 1: Start Claude via sandboxed wrapper
tmux new-session -s claude safe_claude --dangerously-skip-permissions

# Terminal 2: Start Gemini (screen reader mode produces linear text)
tmux new-session -s gemini safe_gemini --yolo --screenReader

# Terminal 3: Run orchestrated discussion (reuses existing sessions)
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  "Review the codebase and suggest refactoring opportunities"
```

### Advanced Options

Control session behavior, startup timing, agent-specific instructions, and CLI flags:

```bash
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  "Design a REST API for a task management system" \
  --auto-start \
  --startup-timeout 60 \
  --max-turns 10 \
  --group-system-prompt "Initial briefing for all agents." \
  --claude-session my-claude \
  --claude-executable "claude --dangerously-skip-permissions" \
  --claude-cwd /path/to/project \
  --claude-system-prompt-file /path/to/claude_instructions.md \
  --gemini-session my-gemini \
  --gemini-executable "gemini --yolo" \
  --log-file logs/custom-discussion.log
```

**Additional Flags:**
- `--group-system-prompt <text>`: A text prompt sent to all participating agents at the beginning of the session.
- `--<agent>-system-prompt-file <path>`: Instructs a specific agent to read a file at the start of the session (e.g., `--claude-system-prompt-file CLAUDE.md`).
- `--<agent>-cwd <path>`: Sets the working directory for a specific agent's session.

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

### Human Intervention & Control

Enable the control channel in `config.yaml` (see `control_channel.enabled`) to pause automation, send
guidance, or answer permission dialogs without attaching to tmux manually. The companion guide
[`docs/Human_Control_Guide.md`](docs/Human_Control_Guide.md) covers commands, workflows, and troubleshooting.

Quick start via the helper script:

```bash
# Pause/resume orchestration
scripts/orchestrator_control.sh pause
scripts/orchestrator_control.sh resume

# Inject guidance
scripts/orchestrator_control.sh say gemini "Focus on fixing the failing tests."

# Send keystrokes (e.g., permissions dialog)
scripts/orchestrator_control.sh key qwen Down Down Enter

# Review recent manual interventions
scripts/orchestrator_control.sh history 20
```

The script default pipe is `/tmp/orchestrator_control`; override with `--pipe` or the `ORCHESTRATOR_CONTROL_PIPE` environment variable. All commands are logged to `logs/control_channel_history.log` (override with `ORCHESTRATOR_CONTROL_HISTORY`). Run `scripts/orchestrator_control.sh --help` for the full command reference.

**Tip:** Use `tmux attach -r` for read-only observation. When you detach (Ctrl+B, then `d`) the orchestrator
resumes automatically unless manually paused via the control channel.

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

Run individual component tests from the project root:

```bash
# Test output parser cleanup
python3 -m pytest tests/test_output_parser_cleanup.py

# Test automation pause/resume
python3 -m pytest tests/test_automation_pause.py

# Test conversation management
python3 -m pytest tests/test_conversation_manager.py

# Test orchestrator discussion
python3 -m pytest tests/test_orchestrator_discussion_pause.py

# Run all tests
python3 -m pytest tests/
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

### Real-World Task: Code Review Simulation

The system has been validated with a collaborative code review scenario where Claude and Gemini work together to identify bugs and propose fixes:

```bash
# Run the code review simulation
PYTHONPATH=. python3 -m examples.run_code_review_simulation \
  --auto-start \
  --kill-existing \
  --max-turns 6 \
  --log-file logs/code_review_simulation.log

# View the results
cat logs/code_review_simulation.log
```

**Proven Results (October 21, 2025):**
- ✅ All 6 turns completed successfully
- ✅ Both AIs performed high-quality technical review
- ✅ All intentional bugs identified (off-by-one error, empty list crash, no bounds checking)
- ✅ Progressive refinement: bug identification → defensive fixes → Pythonic optimization → test cases → production-ready code
- ✅ Real collaboration observed with each AI building on the other's insights
- ✅ Final output: Production-ready code with comprehensive error handling

This validates that the orchestration system works reliably for real-world collaborative software development tasks.

### Manual Testing

Verify individual controllers (run from project root with PYTHONPATH set):

```bash
# Test Claude controller
PYTHONPATH=. python3 tests/test_controller_auto.py

# Test Gemini controller
PYTHONPATH=. python3 tests/test_gemini_controller.py

# Test dual AI operation
PYTHONPATH=. python3 tests/test_dual_ai.py
```

**Note:** All tests must be run from the project root directory. The `PYTHONPATH=.` prefix ensures Python can find the `src/` modules.

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
- **[AGENTS.md](AGENTS.md)** - Codex (Aider) agent instructions
- **[QWEN.md](QWEN.md)** - Qwen CLI agent instructions
- **[Tasks.md](Tasks.md)** - Development task tracking
- **[WebDevTasks.md](WebDevTasks.md)** - Web UI integration task tracking
- **[MessageBoard.md](MessageBoard.md)** - Team discussion and technical decisions
- **[CodexConcerns.md](CodexConcerns.md)** - Architecture discussion and decisions
- **[TIMING_GUIDE.md](TIMING_GUIDE.md)** - Performance tuning guide
- **[docs/Human_Control_Guide.md](docs/Human_Control_Guide.md)** - Control channel usage guide
- **[examples/README.md](examples/README.md)** - Example usage patterns

## Success Criteria

- ✅ **Basic Conversation**: Facilitates 10+ turn conversations between AIs
- ✅ **Automation Pause**: Detects manual attachment and pauses within 1 second
- ✅ **Turn Management**: Round-robin with consensus/conflict detection
- ✅ **Context Preservation**: Maintains conversation state across sessions
- ✅ **Output Cleaning**: Removes CLI UI noise from transcripts
- ✅ **Real-World Task Validation**: Successfully completed collaborative code review (October 21, 2025)
  - 6-turn discussion with both AIs contributing unique insights
  - All intentional bugs identified and fixes proposed
  - Production-ready code generated through collaboration
- ✅ **Web UI Integration**: React-based interface with real-time monitoring (November 2025)
  - Visual display of all AI session outputs
  - Control buttons for pause/resume and keyboard input
  - Integrated API server with REST/WebSocket endpoints
  - Multi-model support (Claude, Gemini, Codex, Qwen)
- ✅ **Human Control Channel**: Named pipe-based control for manual intervention
  - Pause/resume orchestration without attaching to sessions
  - Inject commands and guidance to specific AIs
  - Command history logging and replay
- ⏳ **Error Recovery**: Handles AI timeout/errors gracefully (basic implementation complete)
- ⏳ **Task Completion**: Can complete complex multi-file projects (planned)

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
