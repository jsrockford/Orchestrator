## Codex Refresh – Web UI Integration (Phase 0 & 1)

### Branch & Code State
- Active branch: `feature/web-integration` (branched off `webdev` to retain React UI work).
- FastAPI embedded in `DevelopmentTeamOrchestrator` via `start_api_server`/`stop_api_server`; uvicorn runs in-process with clean shutdown.
- Backend endpoints live in `src/orchestrator/web_api.py`: pause/resume/key/status with FIFO retry + 503 handling.
- Frontend buttons (Esc/Resume/Arrow/Enter) now call the REST endpoints (see `frontend/src/App.tsx` + `frontend/src/components/ConversationWindow.tsx`).
- Backend test coverage in `tests/test_web_api.py` (skips if `httpx` missing). `httpx` installed; `python -m pytest tests/test_web_api.py -q` should run.
- Helper script `scripts/run_api_server.py` spins up orchestrator + API; `--start-sessions` auto-launches tmux sessions.

### Known Issues / Open Threads
- API writes to `/tmp/orchestrator_control`; FIFO only exists when the main orchestrator loop or `orchestrator_control.sh` has created it. If absent, endpoints return 503. Need a deterministic control-channel bootstrap for standalone API runs.
- Browser root (`/`) returning `{"detail":"Not Found"}` is expected—only `/api/...` routes exist. Use `/api/control/status` to verify server health.
- Frontend DevTools showed multiple 404s; confirm the fetch base URL matches backend host/port (`import.meta.env.VITE_API_BASE_URL`?) and that the API server is running before reloading UI.
- Control command history log (`logs/control_channel_history.log`) is not produced when using the standalone script; only the FIFO reflects writes. Need an alternative tail target or emit our own structured log.
- Phase 2 (WebSocket streaming) not started; phase 1 verification still pending—ensure commands reach tmux before advancing.

### Reproduction / Validation Commands
```bash
# activate env
source venv/bin/activate

# run orchestrator + API (auto-start tmux sessions)
python scripts/run_api_server.py --start-sessions --host 0.0.0.0 --port 8000

# optional: confirm FIFO presence
ls -l /tmp/orchestrator_control  # this is NOT being created!

# frontend dev server (separate terminal)
cd frontend
npm run dev

# backend tests (requires httpx)
python -m pytest tests/test_web_api.py -q
```

### Debugging Notes Captured from Current Session
- When manual here-doc tests were attempted, CLI input hung at `>` prompt—likely due to missing terminating `PY` marker; ensure heredocs end with newline + `PY`.
- `test_api_client.py` under `tmp/` failed with `ModuleNotFoundError: No module named 'src'` because script not run from repo root or missing `PYTHONPATH` injection—use `PYTHONPATH=$(pwd)` when running ad-hoc tests.
- Browser saw 404 responses even after API available; verify commands fired after backend restarts (old uvicorn processes lingered on 8000/5173—clean up via `tmux kill-server` and ensure no orphan uvicorn before relaunch).
- `scripts/run_api_server.py` exits if tmux session already exists; handle with `tmux kill-server` or enhance script to reuse sessions in future iteration.

### Coordination Reminders
- Append-only updates to `MessageBoard.md`; prefix entries with `Codex:` and terminate with `-------`.
- Use `CodexConcerns.md` for multi-agent sync if needed (same formatting rules).
- Phase 0/1 priority per `WebDevTasks.md`: stabilize control-plane (REST) before WebSocket streaming. Document next steps + issues on the board after each working block.

### Immediate Next Steps (for next session)
1. Make FIFO lifecycle reliable when launching via API script (either create pipe on demand or embed orchestrator main loop).
2. Reproduce 404s from frontend, capture request URLs, and confirm backend handlers invoked; adjust frontend base URL or router definitions as needed.
3. Provide user-facing checklist for browser validation once commands succeed (e.g., press Esc → expect pause event, verify tmux state).
4. Once control plane verified, outline Phase 2 implementation plan (WebSocket streaming) before coding.
http://localhost:8000/api/control/claude/key/Escape api call from pushing 'Esc' produces a 404 error in the Network tab in Developer in the Browser