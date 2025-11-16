# Backend Development Guide

This guide walks backend contributors through environment setup, key modules, configuration, and testing workflows for the orchestration runtime that lives under `src/`.

## 1. Prerequisites

- Python 3.10+ (project validated on 3.11)
- tmux 3.2+ (controllers inject commands through tmux panes)
- Vendor CLIs installed and authenticated: Claude Code, Gemini CLI, Codex (Aider), Qwen CLI
- Node.js 18+ (only required if you plan to run the React UI locally)

## 2. Environment Setup

```bash
cd /home/dgray/Projects/Orchestrator
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Key Python dependencies:
- `fastapi`, `uvicorn`, `websockets` – API server + WebSocket streaming
- `pyyaml` – configuration loader
- `pydantic` – request/response models

## 3. Configuration Primer

All runtime behavior is driven by `config.yaml`:

- **Per-model tuning**: `startup_timeout`, ready/response indicators, pane geometry, CLI executable paths.
- **tmux defaults**: session names, capture lengths, input pacing.
- **Completion & loop detection**: thresholds for ending discussions and breaking out of tool loops.
- **Control channel**: named pipe path and status formatting.

Use `src/utils/config_loader.py` to read sections; never hard-code values.

## 4. Key Modules

| Area | File(s) | Responsibilities |
| --- | --- | --- |
| Orchestrator Core | `src/orchestrator/orchestrator.py` | Controller registry, prompt queueing, API host, project/discussion state. |
| Conversation Layer | `src/orchestrator/conversation_manager.py`, `context_manager.py`, `message_router.py` | Turn-taking, transcript capture, consensus/conflict detection, prompt assembly. |
| Controllers | `src/controllers/*.py` | Wrap AI CLIs, implement `send_command`, `start_session`, `get_status`, and surface automation pause signals. |
| Session Backend | `src/controllers/session_backend.py`, `tmux_controller.py` | Manage tmux panes, send key sequences, capture output, and translate errors. |
| Utilities | `src/utils/` | Logging (`logger.py`), config access, retries, auto-restart, health checks, output parsing. |
| API Surface | `src/orchestrator/web_api.py` | FastAPI app consumed by the React frontend and automation scripts. |

## 5. Running the Backend

### Foreground (development)

```bash
source venv/bin/activate
python scripts/run_api_server.py --host 0.0.0.0 --port 9100 --start-sessions
```

- `--models claude gemini` restricts preloaded controllers.
- `--start-sessions` pre-creates tmux panes; omit it if the UI will start them later.

### Background helper scripts

```bash
./backend/start_backend.sh   # uses nohup, logs to backend/logs/backend.log, port 8000
./backend/stop_backend.sh
```

These scripts activate the virtual environment automatically and record the PID under `backend/backend.pid`.

## 6. Logging & Diagnostics

- **Structured logs**: `src/utils/logger.get_logger` prefixes entries with the controller/session name. Configure logger levels in code or via environment variables (standard `logging` module).
- **Run transcripts**: CLI output snapshots are saved under `logs/` (see controller implementations for exact filenames).
- **Control channel**: When enabled in `config.yaml`, monitor the named pipe (default `/tmp/orchestrator_control`) to issue `PAUSE`, `RESUME`, or `STATUS` commands without attaching to tmux.
- **Web UI streaming**: The React dashboard subscribes to `/ws/session/{model}`; look for warnings in browser devtools if output stalls.

## 7. Testing

- Run the full regression suite: `python -m pytest`
- Focused suites include:
  - `python -m pytest test_controller.py`
  - `python -m pytest test_output_parser.py`
  - `python -m pytest test_dual_ai.py`
- Mock external CLIs and filesystem operations in unit tests to keep runs deterministic.
- Add regression tests for every bug fix (success-path + failure-path coverage per repository guidelines).

## 8. Developer Workflow Tips

- Keep docstrings PEP 257 compliant and include type hints (current modules already follow this style—match it).
- When adding controller knobs, extend `config.yaml`, update `config_loader`, and surface the new field through `MODEL_SETTING_FIELDS` in `src/orchestrator/web_api.py` so the UI can edit it.
- Use helpers in `src/utils/` instead of inlining subprocess logic; shared behavior (retries, ready detection) should stay centralized.
- Log state transitions with the controller name and project directory to simplify cross-agent debugging.

## 9. OpenAPI Schema Generation

- FastAPI automatically exposes `/openapi.json`, `/docs` (Swagger UI), and `/redoc`. Keep them enabled so operators can debug integrations quickly.
- To commit the latest schema, activate the venv and run:

```bash
source venv/bin/activate
python scripts/generate_openapi.py  # writes docs/openapi.json
```

- CI guardrails: `.github/workflows/openapi-schema.yml` reruns the script on every push/PR and fails if `docs/openapi.json` differs, so always commit the regenerated file alongside API changes.

- Clients (TypeScript/Python/etc.) can ingest `docs/openapi.json` directly for SDK generation or contract tests.

Following this guide ensures backend contributions align with the orchestration engine’s contracts and remain discoverable by future developers.
