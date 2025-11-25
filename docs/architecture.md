# System Architecture

This document provides the shared mental model for how the AI Development Team Orchestration System fits together. It explains the runtime layers, data flow, and key modules so backend, frontend, and operations contributors make compatible design choices.

## Layered View

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Web UI (frontend/)                                                          │
│    - Vite/React dashboard for run control, session streaming, and settings   │
└───────────────▲──────────────────────────────────────────────────────────────┘
                │ WebSocket + REST (FastAPI @ scripts/run_api_server.py)       
┌───────────────┴──────────────────────────────────────────────────────────────┐
│  Orchestration Core (src/orchestrator/)                                      │
│    - DevelopmentTeamOrchestrator: controller registry + API hosting          │
│    - ConversationManager: turn-taking, consensus/loop detection              │
│    - Context/Message routers: prompt history, routing, completion signals    │
└───────────────▲──────────────────────────────────────────────────────────────┘
                │ Controller contracts (send_command / get_status / etc.)      
┌───────────────┴──────────────────────────────────────────────────────────────┐
│  Session Controllers (src/controllers/)                                      │
│    - Claude/Gemini/Codex/Qwen controllers wrap vendor CLIs                   │
│    - SessionBackend + TmuxController manage panes, capture, input injection  │
└───────────────▲──────────────────────────────────────────────────────────────┘
                │ tmux panes / Named pipe control / CLI binaries               
┌───────────────┴──────────────────────────────────────────────────────────────┐
│  External Agents & Human Operators                                           │
│    - AI CLIs (Claude Code, Gemini CLI, Codex CLI, Qwen CLI)                  │
│    - Human attaches to tmux or issues commands via control pipe              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Core Responsibilities

- **DevelopmentTeamOrchestrator (`src/orchestrator/orchestrator.py`)** keeps a registry of controllers, defers automation when humans attach, queues prompts, and hosts the FastAPI server. It exposes lifecycle helpers such as `register_controller`, `start_api_server`, and discussion orchestration hooks used by the UI.
- **ConversationManager (`src/orchestrator/conversation_manager.py`)** owns structured, turn-based discussions. It selects speakers, captures transcripts, parses CLI output via `OutputParser`, and enforces completion/loop detection based on `config.yaml`.
- **Context & Message Utilities**:
  - `ContextManager` handles history persistence and prompt assembly.
  - `MessageRouter` (planned) will apply delivery rules when multi-agent messaging grows more complex.
  - `ControlChannel` exposes a named pipe (`/tmp/orchestrator_control` by default) for pause/resume when humans need to inject commands without attaching to tmux.
- **Controllers (`src/controllers/*.py`)** wrap each AI CLI, mapping orchestrator calls into tmux keystrokes. Shared behavior lives in `session_backend.py` and `tmux_controller.py`, which provision panes, detect prompts, and stream logs back through the orchestrator.
- **Utilities (`src/utils/`)** provide observable, reusable helpers: configuration loading, logging, retries, health checks, auto-restart logic, and CLI output parsing.
- **FastAPI Surface (`src/orchestrator/web_api.py`)** offers REST endpoints plus `/ws/session/{model}` streams so the React UI can start sessions, send prompts, and mirror stdout.
- **Frontend (`frontend/`)** is a Vite + React + TypeScript SPA. It displays model panes, manages project state, configures discussions, and talks to the backend via REST/WebSocket.

## Runtime Scenarios

### Web UI Run
1. Operator activates the Python virtual environment and starts the FastAPI server via `python scripts/run_api_server.py --host 0.0.0.0 --port 9100` (or `backend/start_backend.sh` for `nohup` mode).
2. React dev server (or built frontend) connects to `http://localhost:9100`. The UI calls `/api/control/start-sessions` with a project directory and a model list.
3. `DevelopmentTeamOrchestrator` instantiates controllers, which launch tmux panes configured by `config.yaml`. Controllers stream output to the API server.
4. Conversation controls (start/pause discussion, send prompts) travel through REST endpoints. Live output arrives over `/ws/session/{model}` WebSockets and populates the dashboard.
5. When automation finishes or the operator halts it, `/api/control/stop-sessions` tears down tmux panes and the orchestrator returns to `IDLE`.

### Headless CLI Run
1. `examples/run_orchestrated_discussion.py` (or future `src/cli/team_cli.py`) boots the orchestrator directly.
2. The script orchestrates discussions via `ConversationManager`, still routing to tmux-backed controllers.
3. Logs land in `logs/` and tmux output can be inspected manually or via the control channel.

## Configuration Sources

- **`config.yaml`** is the single source of truth for timing, pane geometry, ready indicators, tool policies, and tmux session names. Adjustments here automatically flow into controllers and the conversation layer.
- **Environment Variables**: The React UI reads `VITE_API_BASE_URL`; backend scripts rely on the virtual environment (`venv`) plus PATH entries for AI CLIs.
- **Instruction Files (`CLAUDE.md`, `GEMINI.md`, etc.)** store per-agent prompts. The FastAPI endpoints `/api/instructions/{model}` allow editing them from the UI.

## Data & Control Flow

1. **Prompt Dispatch**: UI issues `POST /api/control/send-prompt`. Orchestrator enqueues prompts per controller, respecting pause windows and ready indicators before injecting keystrokes through `TmuxController`.
2. **Output Capture**: Controllers stream raw pane capture. `OutputParser` strips ANSI, applies delimiters, and reports back through the WebSocket server.
3. **Completion Detection**: ConversationManager listens for explicit `[[PROJECT_COMPLETE]]` signals or consensus heuristics. When met, it halts the discussion and signals the UI.
4. **Loop / Stall Protection**: Loop detection monitors repeated tool invocations. Auto-restart utilities and health checks can restart crashed tmux sessions.
5. **Human Override**: Control channel or tmux attach triggers automation pause. Once the session is safe again, queued prompts resume in FIFO order.

## Future Extensions

The roadmap in `docs/ARCHIVE/AI_Development_Team_Orchestration_System.md` outlines additional layers (phase manager, task decomposer, CLI). When implementing them, extend this document with:
- New modules and their touchpoints.
- Sequence diagrams covering added flows.
- Configuration knobs required in `config.yaml` or the UI.

Keeping this architecture view current ensures each contributor understands how their change propagates across the orchestrator, controllers, and UI.
