# Documentation Hub

This directory hosts the layered documentation set described in `docs/Documentation_Guidelines.md`. Use the map below to jump to the right audience-specific guide.

| Audience | Start Here | Highlights |
| --- | --- | --- |
| Engineers & stakeholders | [`architecture.md`](architecture.md) | End-to-end system overview, data flow, and component responsibilities. |
| Backend developers | [`backend/development_guide.md`](backend/development_guide.md) | Environment setup, orchestrator modules, testing strategy, and config tips. |
| Backend API consumers | [`backend/api_reference.md`](backend/api_reference.md) | FastAPI surface exposed to the React UI and external automation. |
| Client builders / tooling | [`openapi.json`](openapi.json) | Machine-readable schema (`scripts/generate_openapi.py`) for SDK generation and contract tests. |
| Frontend developers | [`frontend/development_guide.md`](frontend/development_guide.md) | React/Vite project structure, state flows, and UI conventions. |
| Operators / DevOps | [`deployment.md`](deployment.md) | How to start/stop services, manage tmux sessions, and monitor logs. |
| New AI sessions | [`onboarding.md`](onboarding.md) | Quick-start checklist covering doc order, startup scripts, and collaboration rules. |

Each guide references real modules (e.g., `src/orchestrator/orchestrator.py`) and keeps success-path plus failure-path instructions close at hand. Update these docs whenever code paths change so a new contributor can reproduce your steps within 15 minutes without extra context.
