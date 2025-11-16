# Onboarding Guide

Welcome to the AI Development Team Orchestrator. This short playbook gets a fresh AI session productive in minutes by pointing to the right documents, commands, and collaboration habits.

## 1. Read These First

Order matters—each layer assumes the previous one:

1. **Repository overview:** `README.md`
   - Architecture summary, feature list, and proofs-of-concept.
   - Ports: FastAPI on `9100`, React/Vite dev server on `9101`.
2. **Documentation hub:** `docs/README.md`
   - Skim the table to find your specialty guide.
3. **Role-specific deep dives:**
   - Architecture → `docs/architecture.md`
   - Backend/API → `docs/backend/development_guide.md` & `docs/backend/api_reference.md`
   - Frontend → `docs/frontend/development_guide.md`
   - Deployment/Ops → `docs/deployment.md`
4. **Ground rules:** `AGENTS.md`,'CLAUDE.md','GEMINI.md','QWEN.md' - These are instruction files for resptective AI CLI Models; ONLY use yours, NEVER read or alter another model's instruction file! If you are not sure which one applies to you...ASK!
   - Repository boundaries, coding standards, testing policy, MessageBoard etiquette.
5. **Current work:** `Tasks.md`, `WebDevTasks.md`, and the tail of `MessageBoard.md`
   - Align with in-flight tasks before making changes.

## 2. Environment & Services

> All commands assume the repo root `/home/dgray/Projects/Orchestrator`.

1. Activate Python virtualenv:
   ```bash
   source venv/bin/activate
   ```
2. Install backend deps (rarely changes):
   ```bash
   pip install -r requirements.txt
   ```
3. Install frontend deps (first run only):
   ```bash
   (cd frontend && npm install)
   ```

### Start Everything

Preferred: one command launches both FastAPI (9100) and Vite dev server (9101):

```bash
./start_all.sh
```

Need manual control? Use the individual scripts:

```bash
# Backend foreground
source venv/bin/activate
python scripts/run_api_server.py --host 0.0.0.0 --port 9100

# Backend background helper
./backend/start_backend.sh    # logs -> backend/logs/backend.log

# Frontend dev server
./frontend/start-dev.sh       # opens gnome-terminal running npm run dev -- --host
```

Stopping:

```bash
./stop_all.sh                # Preferred; calls both helpers
./frontend/stop-dev.sh       # Stops Vite dev server
./backend/stop_backend.sh    # Stops background FastAPI process
```

## 3. Typical Workflow

1. **Sync context**
   - Read latest `MessageBoard.md` entry and any linked docs.
2. **Plan**
   - Outline steps (use AGENTS plan tool if complex).
3. **Develop**
   - Keep edits inside repo; follow PEP 8/257 and type hints.
   - Use `scripts/generate_openapi.py` when API schemas change and commit `docs/openapi.json`.
   - Frontend lives under `frontend/` (Vite + React + Tailwind).
4. **Validate**
   - Request Don to run `python -m pytest` in the TestOrch worktree when needed.
   - For local UI checks, run `npm --prefix frontend run build`.
5. **Document**
   - Append outcomes to `MessageBoard.md` (`Codex: ... -------` format).
   - Update relevant docs per `docs/Documentation_Guidelines.md`.

## 4. Collaboration Protocol

- **MessageBoard:** append-only log for progress/issues. Use single paragraph unless bullets add clarity; always end with `-------`.
- **CodexConcerns:** architecture debates or cross-agent coordination (archive located under `old/` if needed).
- **Completion signals:** explicitly state `[[PROJECT_COMPLETE]]` plus a human-readable confirmation when objectives finish.
- **No destructive commands:** never run `git reset --hard` or edit outside the repo.

## 5. Useful References

- API schema regeneration: `scripts/generate_openapi.py` → `docs/openapi.json`
- Control channel tooling: `scripts/orchestrator_control.sh`, `docs/deployment.md`
- Discussion status: `GET /api/discussion/status` (`http://localhost:9100/api/discussion/status`)
- Frontend state flows: `frontend/src/App.tsx`, `frontend/src/components/*`

> Need more detail? Jump back to `docs/README.md` and follow the audience-specific guides.

Happy hacking! Document deviations or discoveries on the MessageBoard so the next session can pick up instantly.
