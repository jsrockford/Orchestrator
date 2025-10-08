# Orchestrated Discussion Example

`run_orchestrated_discussion.py` wires the `DevelopmentTeamOrchestrator`,
`ConversationManager`, `ContextManager`, and `MessageRouter` together so Claude
and Gemini can exchange updates automatically.

## Prerequisites

- `tmux` installed and on `$PATH`
- Claude Code and Gemini CLI binaries available on `$PATH`
- (Optional) Existing tmux sessions named `claude` and `gemini`

If the sessions are not running you can allow the script to create them by
passing `--auto-start`.

## Usage

```bash
python examples/run_orchestrated_discussion.py "Decide next sprint focus" --auto-start
```

Important flags:

- `--claude-session` / `--gemini-session`: tmux session names (defaults: `claude`, `gemini`)
- `--claude-executable` / `--gemini-executable`: CLI binaries or quoted commands (e.g., `claude --dangerously-skip-permissions`, `gemini --yolo`)
- `--claude-startup-timeout` / `--gemini-startup-timeout`: Seconds to allow each CLI to become ready (defaults: 10s for Claude, 20s for Gemini)
- `--claude-init-wait` / `--gemini-init-wait`: Extra delay after spawning before the first input (useful for slower startups)
- `--claude-cwd` / `--gemini-cwd`: Working directories for the sessions
- `--max-turns`: Maximum number of turns the discussion should run (default: 6)
- `--log-file`: Write the transcript and context summary to the provided file (or directory)

## Manual Workflow

1. Start or verify Claude and Gemini tmux sessions:
   ```bash
   tmux new -s claude -d claude
   tmux new -s gemini -d gemini
   ```
2. Run the orchestrated discussion:
   ```bash
    python examples/run_orchestrated_discussion.py "Coordinate release plan"
   ```
3. Observe the transcript and context summary printed to stdout.

During a session you can still attach manually (`tmux attach -t claude`)—the
orchestrator will detect pauses, queue outgoing prompts, and resume once you
detach.
