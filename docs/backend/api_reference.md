# Backend API Reference

The FastAPI application defined in `src/orchestrator/web_api.py` exposes REST and WebSocket endpoints that the React UI—and external automation—use to control the orchestrator. This reference summarizes each surface, expected payloads, and notable responses.

- **Base URL (default dev)**: `http://localhost:9100`
- **WebSocket base**: replace `http` with `ws` (e.g., `ws://localhost:9100/ws/...`)
- **Auth**: no authentication yet; all endpoints are trusted within the local network.

## Health

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Returns `{ "status": "ok", "timestamp": "...", "project_state": "IDLE" }` for readiness probes. |

## Control Endpoints

| Method | Path | Body | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/control/pause` | `{ "reason": "manual", "models": ["claude"] }` (models optional) | Pauses automation; orchestrator stops injecting prompts. |
| `POST` | `/api/control/resume` | `{ "models": ["claude"] }` (optional) | Resumes automation for the specified controllers. |
| `POST` | `/api/control/{model}/key/{key_name}` | Optional `{ "delay": 0.1 }` | Sends a single key (e.g., `Enter`, `C-c`) to a model’s tmux pane. |
| `POST` | `/api/control/send-prompt` | `{ "prompt": "Run tests", "models": ["claude","gemini"], "submit": true }` | Broadcasts prompts to selected controllers; optionally skips `Enter` when `submit=false`. |
| `GET` | `/api/control/status` | — | Returns orchestrator, discussion, and per-controller state (automation paused, last heartbeat, etc.). |
| `POST` | `/api/control/start-sessions` | `{ "project_directory": "/path", "models": ["claude","gemini"] }` | Creates tmux sessions, registers controllers, and points them at the chosen project directory. |
| `POST` | `/api/control/stop-sessions` | `{ "models": ["codex"] }` (optional) | Tears down controller sessions; leaving `models` empty stops all. |

## Discussion Management

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/discussion/configure` | `{ "max_turns": 12, "starting_model": "claude", "participants": ["claude","gemini"], "discussion_topic": "...", "include_history": true, "log_level": "INFO" }` | Persists discussion defaults inside the orchestrator. |
| `POST` | `/api/discussion/start` | `{ "project_directory": "...", "max_turns": 10, ... }` | Launches a turn-based conversation using `ConversationManager`. |
| `POST` | `/api/discussion/stop` | `{ "reason": "operator request" }` (optional) | Signals the discussion thread to halt and waits for cleanup. |
| `GET` | `/api/discussion/status` | — | Returns turn counters, active speaker, topic, and any error string. |

## Instruction Files

Each AI has a dedicated Markdown file (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `QWEN.md`). The API lets the UI fetch or replace them without touching the filesystem directly.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/instructions/{model_name}` | Returns `{ "model": "claude", "content": "..." }`. `model_name` must be lowercase (`claude`, `gemini`, `codex`, `qwen`). |
| `POST` | `/api/instructions/{model_name}` | Body `{ "content": "...", "project_directory": "/path" }`; writes the instruction file relative to the project directory. |

## Model Settings Overrides

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/settings/model/{model_name}` | Returns the editable `MODEL_SETTING_FIELDS` plus current values for the specified project directory. |
| `POST` | `/api/settings/model/{model_name}` | Body `{ "project_directory": "/path", "overrides": { "pane_width": 220 } }`; saves overrides to the orchestrator’s in-memory map for that project. |
| `DELETE` | `/api/settings/model/{model_name}` | Body `{ "project_directory": "/path" }`; removes any overrides to fall back to `config.yaml`. |

## Filesystem Helpers

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/fs/browse` | Body `{ "path": "/home/dgray/Projects" }`; lists directory entries plus metadata for the file picker modal. |
| `POST` | `/api/fs/prepare-project` | Body `{ "path": "/home/dgray/Projects/Orchestrator" }`; validates the directory and seeds per-project metadata. |
| `POST` | `/api/fs/create-folder` | Body `{ "path": "/home/dgray/Projects/Orchestrator/docs", "folderName": "notes" }`; creates a child folder. |

## Streaming Sessions

| Method | Path | Description |
| --- | --- | --- |
| `WEBSOCKET` | `/ws/session/{model_name}` | Streams JSON events for a controller (`snapshot`, `append`, `reset`, `error`). The frontend subscribes to one socket per model to mirror tmux output in real time. |

Example WebSocket message:

```json
{ "type": "append", "content": "pytest -q\nAll tests passed\n" }
```

## Error Handling

- REST endpoints return standard HTTP status codes with JSON payloads containing `detail`.
- Session errors (e.g., tmux pane missing) raise `SessionNotFoundError` mapped to `404`.
- Validation issues from Pydantic models result in `422 Unprocessable Entity`.
- WebSocket streams send `{ "type": "error", "message": "..." }` before closing.

## Versioning & Extensibility

- Keep documentation synchronized with `MODEL_SETTING_FIELDS` and new REST routes; when adding endpoints, update this file and the frontend types in `frontend/src/types.ts`.
- Swagger/OpenAPI generation can be added later by mounting `/docs` via FastAPI’s built-in support if we expose the app over HTTPS. For now, this Markdown reference is the source of truth.
