# Deployment & Operations

This guide targets operators who need to run the orchestration stack end-to-end, whether for demos, test runs, or production-like rehearsals.

## 1. Prerequisites Checklist

- Python virtual environment (`venv`) created and activated.
- Required AI CLIs installed and authenticated on the host (Claude Code, Gemini CLI, Codex/Aider, Qwen CLI).
- `tmux` available and configured for non-interactive use.
- Node.js installed if the React UI will be served locally.
- `config.yaml` tuned for the host (pane sizes, executable paths, timeouts).

## 2. Start Sequence

1. **Backend API**
   ```bash
   cd /home/dgray/Projects/Orchestrator
   source venv/bin/activate
   python scripts/run_api_server.py --host 0.0.0.0 --port 9100
   ```
   - Use `--start-sessions --models claude gemini` to pre-provision tmux panes.
   - Background mode: `./backend/start_backend.sh` (logs to `backend/logs/backend.log`, port 8000).

2. **Frontend UI**
   ```bash
   cd frontend
   npm install        # first run only
   npm run dev        # or ./start-dev.sh
   ```
   - Production build: `npm run build` then serve `frontend/dist` using any static host or reverse proxy (e.g., nginx pointing `/` to the built assets while proxying `/api` to the FastAPI server).

3. **Access**
   - Navigate to `http://localhost:9101` (per README instructions) if using the bundled dev tooling.
   - Point the UI at the backend via `VITE_API_BASE_URL` if the API runs on a separate host.

## 3. Session Lifecycle

1. Select the project directory within the UI (defaults to `/home/dgray/Projects/Orchestrator`).
2. Choose models (Claude, Gemini, Codex, Qwen) and click **Start Project** (invokes `POST /api/control/start-sessions`).
3. Watch session panes populate via WebSockets; prompts can be sent manually or by kicking off an orchestrated discussion.
4. When work is done, click **Stop Project** (or run `POST /api/control/stop-sessions`) to clean up tmux panes and release resources.

## 4. Tmux & CLI Notes

- Session names come from `config.yaml` (`tmux.claude_session`, etc.). Attach manually via `tmux attach -t claude` when troubleshooting; automation pauses automatically if `pause_on_manual_clients` is enabled.
- Pane geometry is enforced per model; adjust `pane_width`/`pane_height` when running on smaller displays.
- If a CLI hangs, use `/api/control/{model}/key/C-c` or send `Ctrl+C` directly inside tmux to unblock it.

## 5. Monitoring & Logs

- **Backend**: check `backend/logs/backend.log` (nohup mode) or console output (foreground). Look for uvicorn startup lines and controller registration messages.
- **Controllers**: per-model logs live under `logs/` with timestamps; refer to controller implementations for filenames.
- **Web UI**: browser devtools console reports WebSocket issues or REST failures.
- **System**: use `tmux list-sessions` to confirm panes exist; `ps -ef | grep run_api_server` verifies the FastAPI process.

## 6. Shutdown Procedure

1. In the UI, stop active discussions and sessions.
2. If the backend runs in foreground, press `Ctrl+C`. For nohup mode, `./backend/stop_backend.sh`.
3. Stop the frontend dev server (`Ctrl+C` in its terminal or `frontend/stop-dev.sh`).
4. Deactivate the virtual environment (`deactivate`) if desired.

## 7. Troubleshooting Quick Wins

- **API unreachable**: ensure the FastAPI host/port matches `VITE_API_BASE_URL`, and no firewall blocks the port.
- **WebSockets drop repeatedly**: check for mismatched protocols (https vs. ws) and confirm `ws://` address is reachable locally.
- **CLI refuses commands**: verify ready indicators in `config.yaml` are accurate for the CLI version; enable `debug_wait_logging` per model to inspect wait loops.
- **Named pipe control errors**: confirm the control channel is enabled and the file exists (default `/tmp/orchestrator_control`).

## 8. Verification Before Demo

- `python -m pytest` inside the activated venv.
- `npm run build && npm run typecheck` to catch frontend regressions.
- Dry-run a short discussion between two models, ensuring `[[PROJECT_COMPLETE]]` detection and explicit completion messaging work.

Keep this deployment guide updated whenever ports, scripts, or operational procedures change so anyone on the team can confidently run the system end-to-end.
