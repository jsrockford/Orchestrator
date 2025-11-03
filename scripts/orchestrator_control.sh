#!/usr/bin/env bash
# Lightweight CLI wrapper around the orchestrator control channel FIFO.
#
# Commands:
#   pause                    Pause orchestration after the current turn
#   resume                   Resume orchestration
#   status                   Ask orchestrator to log current status
#   say <agent> <text...>    Inject a prompt for <agent>
#   key <agent> <key...>     Send raw keys to <agent>
#   history [N]              Show last N (default 10) control commands
#
# The control pipe defaults to /tmp/orchestrator_control. Override with the
# ORCHESTRATOR_CONTROL_PIPE environment variable or the --pipe flag.

set -euo pipefail

PIPE_DEFAULT="/tmp/orchestrator_control"
PIPE_PATH="${ORCHESTRATOR_CONTROL_PIPE:-$PIPE_DEFAULT}"
HISTORY_DEFAULT="logs/control_channel_history.log"
HISTORY_FILE="${ORCHESTRATOR_CONTROL_HISTORY:-$HISTORY_DEFAULT}"
STATUS_DEFAULT="/tmp/orchestrator_status.txt"
STATUS_FILE="${ORCHESTRATOR_STATUS_FILE:-$STATUS_DEFAULT}"
VALID_AGENTS=("gemini" "qwen" "claude" "codex" "both" "all")
SUPPORTED_KEYS=("escape" "esc" "enter" "return" "up" "down" "left" "right" "tab" "space" "spacebar" "c-c" "c-d")

usage() {
  cat <<'EOF'
Usage: orchestrator_control.sh [--pipe PATH] [--status-file PATH] <command> [args...]

Commands:
  pause                     Pause orchestration after current turn
  resume                    Resume orchestration
  status                    Ask orchestrator to log its status (also prints snapshot if available)
  say <agent> <text...>     Inject a TEXT command for <agent>
  key <agent> <key...>      Send KEY command to <agent>
  history [N]               Show last N logged commands (default 10)
  help                      Show this message

Agents: gemini, qwen, claude, codex, both, all
Keys:   Escape, Enter, Up, Down, Left, Right, Tab, Space, C-c, C-d ...

Examples:
  orchestrator_control.sh pause
  orchestrator_control.sh say gemini "Please summarize progress so far"
  orchestrator_control.sh key qwen Down Down Enter
  orchestrator_control.sh history 20

Environment:
  ORCHESTRATOR_CONTROL_PIPE     Override control pipe path (default /tmp/orchestrator_control)
  ORCHESTRATOR_CONTROL_HISTORY  Override control command history log path
  ORCHESTRATOR_STATUS_FILE      Override status snapshot path (default /tmp/orchestrator_status.txt)
EOF
}

error() {
  local msg=$1
  local code=${2:-1}
  printf 'Error: %s\n' "$msg" >&2
  exit "$code"
}

ensure_pipe() {
  if [[ ! -p "$PIPE_PATH" ]]; then
    error "Orchestrator not running (control pipe not found at $PIPE_PATH). Use --pipe or set ORCHESTRATOR_CONTROL_PIPE if needed."
  fi
}

log_command() {
  local line=$1
  local timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M:%S')
  local entry="$timestamp | $line"
  mkdir -p "$(dirname "$HISTORY_FILE")"
  printf '%s\n' "$entry" >> "$HISTORY_FILE"
}

send_command() {
  local payload=$1
  ensure_pipe
  # Write to the FIFO first, then persist the command so every intervention leaves an audit trail.
  printf '%s\n' "$payload" > "$PIPE_PATH"
  log_command "$payload"
  printf 'Sent: %s\n' "$payload"
}

show_history() {
  local count=${1:-10}
  if [[ ! -f "$HISTORY_FILE" ]]; then
    printf 'No history available yet (%s not found).\n' "$HISTORY_FILE"
    exit 0
  fi
  tail -n "$count" "$HISTORY_FILE"
}

show_status_snapshot() {
  if [[ -z "${STATUS_FILE:-}" ]]; then
    return
  fi
  if [[ ! -f "$STATUS_FILE" ]]; then
    printf 'Status snapshot not available (missing %s).\n' "$STATUS_FILE"
    return
  fi
  printf '\n--- Orchestrator Status (%s) ---\n' "$(date '+%Y-%m-%d %H:%M:%S')"
  cat "$STATUS_FILE"
}

is_valid_agent() {
  local agent_lower
  agent_lower=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  for candidate in "${VALID_AGENTS[@]}"; do
    if [[ "$candidate" == "$agent_lower" ]]; then
      return 0
    fi
  done
  return 1
}

is_supported_key() {
  local key_lower
  key_lower=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  for candidate in "${SUPPORTED_KEYS[@]}"; do
    if [[ "$candidate" == "$key_lower" ]]; then
      return 0
    fi
  done
  if [[ "$key_lower" =~ ^c-[[:alnum:]]$ ]]; then
    return 0
  fi
  return 1
}

# ---- argument parsing ----
if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pipe)
      shift || error "Missing value for --pipe"
      PIPE_PATH=$1
      shift || true
      ;;
    --status-file)
      shift || error "Missing value for --status-file"
      STATUS_FILE=$1
      shift || true
      ;;
    --help|-h|help)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

command_name=$1
shift || true

case "$command_name" in
  pause)
    send_command "PAUSE"
    ;;
  resume)
    send_command "RESUME"
    ;;
  status)
    send_command "STATUS"
    sleep 0.15
    show_status_snapshot
    ;;
  say)
    if [[ $# -lt 2 ]]; then
      error "say command requires an agent and prompt text"
    fi
    agent=$1
    shift
    if ! is_valid_agent "$agent"; then
      error "Invalid agent '$agent'. Valid agents: ${VALID_AGENTS[*]}"
    fi
    prompt=$*
    if [[ -z "$prompt" ]]; then
      error "Prompt text cannot be empty"
    fi
    send_command "TEXT $agent: $prompt"
    ;;
  key)
    if [[ $# -lt 2 ]]; then
      error "key command requires an agent and at least one key"
    fi
    agent=$1
    shift
    if ! is_valid_agent "$agent"; then
      error "Invalid agent '$agent'. Valid agents: ${VALID_AGENTS[*]}"
    fi
    keys=("$@")
    for key in "${keys[@]}"; do
      if ! is_supported_key "$key"; then
        error "Invalid key '$key'. Supported keys include: Escape Enter Up Down Left Right Tab Space C-c C-d"
      fi
    done
    send_command "KEY $agent ${keys[*]}"
    ;;
  history)
    count=${1:-10}
    if ! [[ "$count" =~ ^[0-9]+$ ]]; then
      error "history count must be a positive integer"
    fi
    show_history "$count"
    ;;
  *)
    # Fallback to usage because every argument should map to a documented control verb.
    usage
    error "Unknown command '$command_name'"
    ;;
esac
