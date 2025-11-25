# PROJECT_TASKS with Checkpoints (Template)

Use this layout to interleave implementation tasks with checkpoint meta-tasks that trigger `[[CLEAR]]`.

## Section 0 – Foundations
- [ ] Setup repo, venv, deps
- [ ] Configure API/CLI credentials
- [ ] Smoke test orchestrator start/stop
- [ ] **CHECKPOINT:** See `CHECKPOINT 0` below

## Section 1 – Feature Area A
- [ ] Task 1.1 – Implement core logic (acceptance: …)
- [ ] Task 1.2 – Tests for core logic (acceptance: …)
- [ ] Task 1.3 – Wire to API/UI (acceptance: …)
- [ ] **CHECKPOINT:** See `CHECKPOINT 1` below

## Section 2 – Feature Area B
- [ ] Task 2.1 – …
- [ ] Task 2.2 – …
- [ ] **CHECKPOINT:** See `CHECKPOINT 2` below

## Checkpoints (emit `[[CLEAR]]`)
### CHECKPOINT 0: Foundations Complete
- Trigger: After Section 0 tasks
- Agent: `[[CLEAR:codex]]`
- Re-read: PRD.md, ARCHITECTURE.md, next section of PROJECT_TASKS.md
- Next focus: Section 1 – Feature Area A

### CHECKPOINT 1: Feature Area A Complete
- Trigger: After Section 1 tasks
- Agent: `[[CLEAR:codex]]`
- Re-read: PRD.md, ARCHITECTURE.md, next section of PROJECT_TASKS.md
- Next focus: Section 2 – Feature Area B

### CHECKPOINT 2: Feature Area B Complete
- Trigger: After Section 2 tasks
- Agent: `[[CLEAR:codex]]`
- Re-read: PRD.md, ARCHITECTURE.md, next section of PROJECT_TASKS.md
- Next focus: Section 3 – …

> Adjust agent names, sections, and task details per project. Add more checkpoints for risky/long-running sections. Honor cooldowns enforced by the orchestrator.
