# Context Management Guide

## Why This Exists
Phase 3 coding sessions can blow through token budgets when models carry long histories. The `[[CLEAR]]` marker lets any agent signal the orchestrator to clear its CLI context, then re-anchor on the authoritative files (PRD.md, ARCHITECTURE.md, PROJECT_TASKS.md). This prevents mid-implementation resets and keeps tasks aligned with the plan.

## Marker Syntax
- `[[CLEAR]]` → Clear the emitting agent only (safer default)
- `[[CLEAR:agent]]` → Clear a specific agent (e.g., `[[CLEAR:codex]]`)
- `[[CLEAR:all]]` → Clear all active agents

## When to Emit
- At planned checkpoints in PROJECT_TASKS.md (see `templates/PROJECT_TASKS_with_checkpoints.md`)
- After finishing a major task cluster or section
- When token usage hits ~60–70% of budget
- When confused or after a long detour; emit via MessageBoard.md if mid-task

## Orchestrator Behavior
1. Detects markers in orchestrated turns (and MessageBoard.md if polling is enabled)
2. Applies per-agent cooldown (default 30s) and ignores invalid sources
3. Dispatches model-specific clear commands (`/new` for Codex, `/clear` for Claude/Gemini/Qwen)
4. Waits for ready state, then injects:  
   `Context cleared. Re-read PRD.md, ARCHITECTURE.md, and the next section of PROJECT_TASKS.md before continuing.`
5. Logs events to `logs/context_clears.log` and updates status `clear_stats`

## Safety Guardrails
- Whitelist: only honor clears from orchestrated turns or MessageBoard.md
- Cooldown: 30s minimum between clears per agent; `[[CLEAR:all]]` checks each agent
- Logging: successes/failures recorded with timestamps and sources
- Scope: unscoped clears affect only the emitting agent; use `[[CLEAR:all]]` to broadcast

## Checkpoint Patterns
- Follow `templates/PROJECT_TASKS_with_checkpoints.md` for embedding checkpoint meta-tasks.
- Reuse `templates/CHECKPOINT_meta_task.md` to remind agents to emit `[[CLEAR:agent]]` and re-read source files.
- Architect/PM instruction files (Phase 2) include guidance on how often to insert checkpoints.

## Quick Protocol (for any agent)
1. Finish the current checkpoint section.
2. Emit `[[CLEAR:yourname]]` (or `[[CLEAR:all]]` if everyone should reset).
3. Wait for the orchestrator’s injected prompt, re-read PRD.md, ARCHITECTURE.md, PROJECT_TASKS.md.
4. Resume with the next planned task.
