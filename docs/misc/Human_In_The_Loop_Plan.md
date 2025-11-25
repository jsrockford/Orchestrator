# Human In The Loop Plan

This plan adds a Human participant to the round-robin discussion without breaking current “Send to model(s)” injections.

## Goals
- Allow selecting Human alongside AI models for a session.
- Include Human in the turn rotation; pause on the human turn until Submit or Skip.
- Reuse the existing input area; keep “Send to model(s)” injections working as today.
- Avoid new deadlocks; skip or timeout rather than blocking the run.

## Backend Plan
- **Session modeling**: Add a human participant type in conversation/context state; flag in session config to include/exclude. The human is treated like an agent for history but has no tmux controller.
- **Turn selection**: Extend `ConversationManager` to consider human when enabled and not skipped for the current turn. Human turns set a `waiting_on_human` state and halt automated dispatch until resolved.
- **Turn resolution**: Add API endpoints (or extend existing) for `human_submit(text)` and `human_skip()`. On submit, record a turn, append to history, and advance rotation. On skip or timeout, record a skipped human turn and advance.
- **Timeouts**: Optional `human.turn_timeout` config to auto-skip after N seconds to prevent stalls. Log when timeouts occur.
- **Loop/completion**: Exclude human turns from loop detection. Completion detection can optionally consider human statements; default to ignore to avoid false positives.
- **Control channel**: Keep existing control-channel injections unchanged (they remain out-of-band). If needed, allow a control-channel command to submit or skip the human turn for headless operation.

## Frontend/UI Plan
- **Session setup**: Add a Human checkbox alongside model selection. Store in session state and send to backend when starting a discussion.
- **Shared input reuse**: Keep the existing textarea. When `waiting_on_human` is true, swap the action buttons to `Submit` and `Skip` and show a “Your turn” banner. Outside human turns, preserve current “Send to model(s)” behavior unchanged.
- **State cues**: Display a small indicator when the system is waiting on human input; after submit/skip, return to normal view.
- **Error handling**: If a human submit fails, surface a toast/inline error and keep the turn active. On timeout auto-skip, show a brief notice in the UI.

## Config & Data Shapes
- Add `human` block to `config.yaml` (enabled default false, turn_timeout, prompt label). Include a session-scoped flag to enable human for a run.
- API payloads: include `waiting_on_human` and pending-turn metadata in status responses; accept submit/skip requests.

## Testing Plan
- Unit: conversation manager chooses human when enabled; skips when disabled; loop detection ignores human; completion detection unaffected.
- Integration: start session with human enabled; human submit advances to next model; skip advances; timeout triggers skip; send-to-model injection still works mid-session.
- Frontend: UI shows human banner, submit/skip wiring; normal injection unaffected.

## Rollout Notes
- Default Human disabled to preserve current behavior.
- Ensure logs clearly mark human turns (submitted, skipped, timed out).
- Document flows in onboarding/docs once implemented.
