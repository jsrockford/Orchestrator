# Human Control Guide

This guide explains how to monitor and influence orchestrated discussions at runtime. It covers
the control channel FIFO, the helper shell wrapper, and common intervention workflows such as
pausing automation or answering permission prompts.

## Overview

The orchestrator exposes a **control channel** backed by a named pipe (FIFO). External tools can
write structured commands into this pipe to control live conversations without attaching directly
to the tmux panes. The channel is disabled unless `config.yaml` sets:

```yaml
control_channel:
  enabled: true
  pipe: /tmp/orchestrator_control
```

When enabled, the orchestrator listens for control commands after each agent turn. Commands are
validated, logged to `logs/control_channel_history.log`, and executed immediately. A companion
script, `scripts/orchestrator_control.sh`, wraps the FIFO with ergonomic subcommands.

## Control Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `PAUSE` | `PAUSE` | Pause automation and leave sessions idle for human interaction. |
| `RESUME` | `RESUME` | Resume orchestration after a manual pause or tmux attach. |
| `STATUS` | `STATUS` | Emit a multi-line status snapshot and write it to the status file. |
| `TEXT` | `TEXT <target> <message>` | Inject a plain-text message into one or more agents. |
| `KEY` | `KEY <target> <seq…>` | Send key sequences (e.g., `Enter`, `C-c`, `Down`) to agents. |
| `SAY` | `SAY <target> <message>` | Alias for `TEXT` to improve readability. |

**Targets** can be a single agent (`claude`), a comma-separated list (`claude,gemini`), or the
keyword `all`. See [`src/orchestrator/conversation_manager.py`](../src/orchestrator/conversation_manager.py)
for the target resolver and command handlers.

## Shell Wrapper (`orchestrator_control.sh`)

Use the helper script to avoid manual pipe management. The script provides the following commands:

- `pause`: Pause orchestration after the current turn.
- `resume`: Resume orchestration.
- `status`: Request a status snapshot from the orchestrator.
- `say <agent> <text...>`: Inject a text prompt for a specific agent.
- `key <agent> <key...>`: Send a sequence of raw keys to an agent. Supported keys include `Escape`, `Enter`, `Up`, `Down`, `Left`, `Right`, `Tab`, `Space`, and control characters like `C-c`.
- `history [N]`: Show the last N (default 10) commands sent through the control channel.
- `help`: Display the full command reference.

```bash
# Pause and resume orchestration
scripts/orchestrator_control.sh pause
scripts/orchestrator_control.sh resume

# Send guidance
scripts/orchestrator_control.sh say gemini "Focus on writing tests."

# Drive permission dialog
scripts/orchestrator_control.sh key claude Enter

# Check status and tail history
scripts/orchestrator_control.sh status
scripts/orchestrator_control.sh history 20
```

Key options:

- `--pipe <path>`: Override the FIFO path (default `/tmp/orchestrator_control`).
- `--status-file <path>`: Override the status snapshot location (default `/tmp/orchestrator_status.txt`).
- `--help`: Show the full command reference and exit.

## Environment Variables

The shell wrapper's behavior can also be configured using environment variables, which are overridden by command-line flags.

- `ORCHESTRATOR_CONTROL_PIPE`: Sets the path to the control channel FIFO.
- `ORCHESTRATOR_CONTROL_HISTORY`: Sets the path to the command history log file (default `logs/control_channel_history.log`).
- `ORCHESTRATOR_STATUS_FILE`: Sets the path where the status snapshot is written.

## Common Use Cases

### Handling Permission Prompts

1. Run the orchestrator with the control channel enabled.
2. When a CLI prompts for confirmation, send `KEY` commands to the relevant agent:
   ```bash
   scripts/orchestrator_control.sh key claude Enter
   ```
3. Resume automation once the prompt clears:
   ```bash
   scripts/orchestrator_control.sh resume
   ```

### Supplying Human Guidance

Provide additional context or requirements mid-run:

```bash
scripts/orchestrator_control.sh say all "Remember to add regression tests."
```

The orchestrator queues the message as the next prompt sent to each agent.

### Monitoring Progress

Run `STATUS` periodically (or tail the status file) to see:

- Current mode (RUNNING/PAUSED/ERROR)
- Turn counts and progress bar
- Active agent and last responder
- Per-agent idle timers and last completed turn

The snapshot is also written to `logs/control_channel_history.log` alongside command history.

## Troubleshooting

- **Command rejected**: Check `logs/control_channel_history.log` for validation errors. The STATUS
  output also echoes the last error message.
- **No status file**: Ensure `control_channel.status.write_file` is true and the orchestrator has
  permission to write to the target directory.
- **KEY sequence ineffective**: Inspect the controller logs to confirm the agent supports direct
  key dispatch (e.g., Qwen requires mixed `send_key`/`send_keys` handling which the orchestrator
  manages automatically).
- **Paused unexpectedly**: Attaching to a tmux pane automatically pauses automation. Detach to let
  the orchestrator resume, or run `resume`.

## Best Practices

- Keep the CLI helper in sync with the repo when copying files to a test worktree.
- Use read-only tmux attaches (`tmux attach -r`) whenever possible to avoid leaving automation in
  a paused state.
- Tail `logs/automation.log` and `logs/control_channel_history.log` during manual interventions for
  a complete audit trail.
- Disable the control channel in environments where the FIFO would be exposed to untrusted users.

