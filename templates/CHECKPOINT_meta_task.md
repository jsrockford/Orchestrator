# CHECKPOINT Meta-Task (Snippet)

Use this snippet inside PROJECT_TASKS.md to mark checkpoint boundaries and instruct the emitting agent to clear context.

```
### CHECKPOINT: <Section Name> Complete
- Trigger: After finishing <tasks/section>
- Agent: [[CLEAR:<agent_name>]]
- Re-read: PRD.md, ARCHITECTURE.md, next section of PROJECT_TASKS.md
- Next focus: <brief description of upcoming section>
```

Notes:
- Keep checkpoints every 3–5 major tasks or at module boundaries.
- Use scoped clears (agent-specific) unless all agents need a reset (`[[CLEAR:all]]`).
- The orchestrator enforces cooldowns; if a clear is skipped, log a reason in MessageBoard.md.
