# Frontend Development Guide

The React dashboard (under `frontend/`) gives operators real-time control over orchestrated AI sessions. This guide covers the project layout, tooling, state flows, and conventions for adding features.

## 1. Toolchain & Scripts

- **Stack**: React 18 + TypeScript + Vite + TailwindCSS
- **Package manager**: npm (Node.js 18+)
- **Key scripts (`package.json`)**:
  - `npm run dev` – Vite dev server (default `http://localhost:5173`)
  - `npm run build` – production build (outputs to `frontend/dist`)
  - `npm run preview` – serve the built assets locally
  - `npm run lint` – ESLint (`@eslint/js`, React hooks plugin)
  - `npm run typecheck` – isolated `tsc --noEmit`

`frontend/start-dev.sh` opens a `gnome-terminal` window and runs `npm run dev -- --host`; `frontend/stop-dev.sh` kills running dev servers.

## 2. Project Structure

```
frontend/
├── src/
│   ├── App.tsx                  # Top-level state + layout
│   ├── main.tsx                 # React root
│   ├── types.ts                 # Shared TypeScript types (discussion settings, model fields)
│   ├── components/
│   │   ├── ConversationWindow.tsx
│   │   ├── PromptInput.tsx
│   │   ├── SessionModelSelector.tsx
│   │   ├── EditInstructionsModal.tsx
│   │   ├── ProjectSettingsModal.tsx
│   │   └── ModelSettingsModal.tsx
│   └── index.css                # Tailwind + globals
├── tsconfig.app.json / tsconfig.node.json
├── vite.config.ts
└── package.json
```

Component responsibilities:
- **ConversationWindow** – renders model transcripts streamed over WebSocket.
- **PromptInput** – single-field prompt composer with multi-model selection.
- **SessionModelSelector** – toggles which models take part in runs.
- **EditInstructionsModal** – fetches/saves agent instruction files through `/api/instructions/{model}`.
- **ProjectSettingsModal** – surfaces `/api/fs/browse` + `/api/control/start-sessions`.
- **ModelSettingsModal** – edits controller overrides via `/api/settings/model/{model}`.

## 3. Configuration & Environment Variables

- `VITE_API_BASE_URL` (optional) points the UI at a remote FastAPI host. Defaults to `http://localhost:9100`.
- WebSocket URLs are derived automatically by swapping the protocol (`http` → `ws`).
- When packaging for production, set `VITE_API_BASE_URL` during `npm run build`.

## 4. State & Data Flow

`App.tsx` manages global state using React hooks:
- `projectState` tracks whether sessions are idle/running/paused.
- `discussionSettings` + `discussionState` mirror `/api/discussion/*` endpoints.
- `sessionOutputs`, `streamStatuses`, and `streamErrors` are dictionaries keyed by model title (Claude, Codex, Gemini, Qwen).
- `useRef` keeps live references to sockets and selected models to avoid stale closures inside callbacks.

### WebSocket lifecycle
1. `ensureSocket(model)` opens `ws://.../ws/session/{model}` when the project is running.
2. Event handlers normalize server payloads (`snapshot`, `append`, `reset`, `error`) and clamp transcripts to `MAX_OUTPUT_CHARS`.
3. `closeSocket`/`closeAllSockets` gracefully tear down connections on pause/stop or when the operator deselects a model.

### REST interactions
All fetches use the native Fetch API (see `App.tsx`): POST bodies are JSON, and errors update `streamErrors` or modal-level status fields. Keep new calls colocated with the component that owns the UI so error feedback is immediate.

## 5. Styling & UI Conventions

- Tailwind classes live directly in JSX; global adjustments belong in `src/index.css`.
- Use the shared `lucide-react` icon set; add new icons through named imports.
- Cap log panes using `MAX_OUTPUT_CHARS` to prevent runaway DOM updates.
- Keep modals portal-less (rendered conditionally in `App.tsx`) to simplify keyboard navigation.

## 6. Adding Features

1. **Define data contracts** in `src/types.ts` so components share a stable shape.
2. **Extend backend first** if you need new fields/endpoints, then update this doc and `docs/backend/api_reference.md`.
3. **Introduce hooks/helpers sparingly**—prefer co-locating logic inside components unless it is reused in 3+ places.
4. **Testing**: while we do not yet have automated frontend tests, run `npm run lint` and `npm run typecheck` before opening a PR. Consider adding Vitest or Playwright when the UI stabilizes.

## 7. Connecting to the Backend

- Start the FastAPI server (`python scripts/run_api_server.py --host 0.0.0.0 --port 9100`) before launching `npm run dev`.
- If you proxy through a different host/port, set `VITE_API_BASE_URL` or add a `.env` file with `VITE_API_BASE_URL=http://devbox:9100`.
- Remember that actual tmux sessions run only on Don’s orchestrator host; never attempt to spawn CLIs from a remote machine unless tmux and the CLIs are available there.

Keeping this guide current ensures frontend contributions integrate smoothly with the orchestrator backend and follow the shared coding style.
