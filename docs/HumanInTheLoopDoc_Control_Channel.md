# Human In The Loop - Control Channel Guide

## Overview

The control channel allows headless operation of the Human In The Loop feature via a named pipe. This enables programmatic control, automation scripts, and external tools to submit or skip human turns without using the web UI.

## Control Channel Basics

### Named Pipe Location

```
/tmp/orchestrator_control
```

### How It Works

1. Orchestrator creates named pipe on startup
2. External process writes commands to pipe
3. Orchestrator reads and processes commands
4. Commands executed asynchronously
5. Results logged, status updated

### Command Format

```
COMMAND_NAME [arguments...]
```

- Commands are **case-sensitive**
- Arguments separated by spaces
- Multi-word arguments: space-separated (not quoted)
- Each command ends with newline

## Human Turn Commands

### HUMAN_SUBMIT

Submit a response for the current human turn.

**Syntax:**
```
HUMAN_SUBMIT <response text>
```

**Arguments:**
- `<response text>`: Space-separated words forming the response
  - Example: `HUMAN_SUBMIT This looks good to me`
  - Backend reconstructs: `"This looks good to me"`

**Behavior:**
- Validates `waiting_on_human: true` (must be human's turn)
- Validates non-empty if `human.allow_empty_submissions: false`
- Records turn with metadata: `human_turn: true`, `via_control_channel: true`
- Increments turn counter
- Clears `waiting_on_human` flag
- Advances to next speaker
- Emits `human_turn_completed` WebSocket event with `via_control_channel: true`

**Example:**
```bash
echo "HUMAN_SUBMIT I agree with the proposed solution" > /tmp/orchestrator_control
```

**Success:**
- Status error cleared: `_set_status_error(None)`
- Logged: `"Control channel: HUMAN_SUBMIT processed for 'Human' (turn 5, 42 chars)"`

**Error:**
- Status error set: `_set_status_error("Not currently waiting for human input")`
- Logged: `"Control channel HUMAN_SUBMIT error: Not currently waiting for human input"`

---

### HUMAN_SKIP

Skip the current human turn without providing a response.

**Syntax:**
```
HUMAN_SKIP
```

**Arguments:** None

**Behavior:**
- Validates `waiting_on_human: true` (must be human's turn)
- Records skipped turn via `_record_human_skip()` helper
- Response text: `"[Human turn skipped]"`
- Metadata: `human_turn: true`, `skipped: true`, `via_control_channel: true`
- Increments turn counter
- Clears `waiting_on_human` flag
- Advances to next speaker
- Emits `human_turn_skipped` WebSocket event with `via_control_channel: true`

**Example:**
```bash
echo "HUMAN_SKIP" > /tmp/orchestrator_control
```

**Success:**
- Status error cleared
- Logged: `"Control channel: HUMAN_SKIP processed for 'Human' (turn 5)"`

**Error:**
- Status error set: `_set_status_error("Not currently waiting for human input")`
- Logged: `"Control channel HUMAN_SKIP error: Not currently waiting for human input"`

---

## Usage Examples

### Basic Human Turn Submission

```bash
#!/bin/bash
# Wait for human turn, then submit response

# Monitor status until human turn
while true; do
  STATUS=$(curl -s http://localhost:9100/api/discussion/status)
  WAITING=$(echo "$STATUS" | jq -r '.waiting_on_human')

  if [ "$WAITING" = "true" ]; then
    echo "Human turn detected, submitting response..."
    echo "HUMAN_SUBMIT Looks good, proceeding with implementation" > /tmp/orchestrator_control
    break
  fi

  sleep 2
done
```

### Automated Skip After Delay

```bash
#!/bin/bash
# Auto-skip human turns after 30 seconds

while true; do
  STATUS=$(curl -s http://localhost:9100/api/discussion/status)
  WAITING=$(echo "$STATUS" | jq -r '.waiting_on_human')

  if [ "$WAITING" = "true" ]; then
    echo "Human turn detected, waiting 30 seconds..."
    sleep 30

    # Check if still waiting (timeout hasn't occurred)
    STATUS=$(curl -s http://localhost:9100/api/discussion/status)
    WAITING=$(echo "$STATUS" | jq -r '.waiting_on_human')

    if [ "$WAITING" = "true" ]; then
      echo "Auto-skipping human turn"
      echo "HUMAN_SKIP" > /tmp/orchestrator_control
    fi
  fi

  sleep 2
done
```

### Conditional Response Based on AI Output

```bash
#!/bin/bash
# Submit different responses based on AI consensus

while true; do
  STATUS=$(curl -s http://localhost:9100/api/discussion/status)
  WAITING=$(echo "$STATUS" | jq -r '.waiting_on_human')

  if [ "$WAITING" = "true" ]; then
    # Read last few AI turns (pseudo-code, would need actual history endpoint)
    AI_OUTPUT=$(get_recent_ai_output)

    if echo "$AI_OUTPUT" | grep -q "ERROR"; then
      echo "HUMAN_SUBMIT Please fix the errors mentioned above" > /tmp/orchestrator_control
    elif echo "$AI_OUTPUT" | grep -q "COMPLETE"; then
      echo "HUMAN_SUBMIT Approved, looks complete" > /tmp/orchestrator_control
    else
      echo "HUMAN_SUBMIT Continue with the current approach" > /tmp/orchestrator_control
    fi

    # Wait for turn to complete
    sleep 5
  fi

  sleep 2
done
```

### Python Automation

```python
import subprocess
import time
import requests

CONTROL_PIPE = "/tmp/orchestrator_control"
API_BASE = "http://localhost:9100"

def send_control_command(command):
    """Send command to control channel."""
    with open(CONTROL_PIPE, 'w') as pipe:
        pipe.write(f"{command}\n")
        pipe.flush()
    print(f"Sent: {command}")

def get_discussion_status():
    """Get current discussion status."""
    response = requests.get(f"{API_BASE}/api/discussion/status")
    return response.json()

def human_turn_monitor():
    """Monitor for human turns and auto-respond."""
    print("Starting human turn monitor...")

    while True:
        try:
            status = get_discussion_status()

            if status.get("waiting_on_human"):
                speaker = status.get("pending_turn_participant", "Human")
                turn = status.get("manager", {}).get("turn_counter", "?")

                print(f"Human turn detected: {speaker} (turn {turn})")

                # Generate response (replace with actual logic)
                response = generate_ai_response(status)

                if response:
                    send_control_command(f"HUMAN_SUBMIT {response}")
                else:
                    send_control_command("HUMAN_SKIP")

                # Wait for turn to complete
                time.sleep(5)

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(2)

def generate_ai_response(status):
    """Generate response based on discussion status."""
    # Replace with actual logic
    turn = status.get("manager", {}).get("turn_counter", 0)

    if turn < 3:
        return "Continue with the current approach"
    elif turn < 7:
        return "Let's wrap up the discussion"
    else:
        return "Approved, implementation complete"

if __name__ == "__main__":
    human_turn_monitor()
```

---

## Integration Patterns

### Pattern 1: Human Proxy

Route human turns to external chat system (Slack, Discord, etc.)

```python
import requests
from slack_sdk import WebClient

SLACK_CHANNEL = "#orchestrator"
slack_client = WebClient(token=SLACK_BOT_TOKEN)

def forward_to_slack():
    """Forward human turn to Slack, wait for response."""
    while True:
        status = get_discussion_status()

        if status.get("waiting_on_human"):
            # Post to Slack
            slack_client.chat_postMessage(
                channel=SLACK_CHANNEL,
                text="@here It's your turn in the Orchestrator discussion! Reply here with your response."
            )

            # Listen for Slack response (requires Slack Events API)
            response = wait_for_slack_response()

            if response:
                send_control_command(f"HUMAN_SUBMIT {response}")

        time.sleep(2)
```

### Pattern 2: LLM as Human

Use another AI model to simulate human participation.

```python
import openai

def llm_as_human():
    """Use GPT-4 to generate human responses."""
    while True:
        status = get_discussion_status()

        if status.get("waiting_on_human"):
            # Get recent conversation history
            history = get_conversation_history()

            # Generate response with GPT-4
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a human participant reviewing AI discussion."},
                    {"role": "user", "content": f"Discussion history:\n{history}\n\nProvide your response:"}
                ]
            )

            human_response = response.choices[0].message.content

            send_control_command(f"HUMAN_SUBMIT {human_response}")

        time.sleep(2)
```

### Pattern 3: Scheduled Auto-Skip

Skip human turns during off-hours.

```python
from datetime import datetime

def business_hours_only():
    """Only allow human turns during business hours, auto-skip otherwise."""
    while True:
        status = get_discussion_status()

        if status.get("waiting_on_human"):
            now = datetime.now()
            hour = now.hour
            weekday = now.weekday()

            # Business hours: Mon-Fri, 9am-5pm
            if weekday < 5 and 9 <= hour < 17:
                print("Business hours - waiting for manual response")
            else:
                print("Off-hours - auto-skipping")
                send_control_command("HUMAN_SKIP")
                time.sleep(5)

        time.sleep(2)
```

---

## Error Handling

### Command Validation

Control channel commands validated before execution:

**Validation Checks:**
1. `waiting_on_human` must be `true`
2. `pending_turn_participant` must be set
3. For HUMAN_SUBMIT: response must be non-empty (if configured)

**On Validation Failure:**
- Status error set (visible in `/api/discussion/status`)
- Error logged to orchestrator logs
- Command ignored, no turn recorded

**Monitoring Errors:**
```bash
# Watch for status errors
watch -n 1 'curl -s http://localhost:9100/api/discussion/status | jq .error'
```

### Named Pipe Issues

**Pipe Not Found:**
```bash
echo "HUMAN_SUBMIT test" > /tmp/orchestrator_control
# bash: /tmp/orchestrator_control: No such file or directory
```

**Solution:** Orchestrator not running or pipe not created. Start orchestrator first.

**Permission Denied:**
```bash
echo "HUMAN_SUBMIT test" > /tmp/orchestrator_control
# bash: /tmp/orchestrator_control: Permission denied
```

**Solution:** Check pipe permissions:
```bash
ls -l /tmp/orchestrator_control
# Should be writable by your user
```

**Broken Pipe:**
```bash
echo "HUMAN_SUBMIT test" > /tmp/orchestrator_control
# bash: echo: write error: Broken pipe
```

**Solution:** Orchestrator crashed or restarted. Check orchestrator logs and restart.

---

## Best Practices

### 1. Always Check Status First

Don't blindly send commands - verify it's actually human's turn:

```bash
# Bad: Sends command without checking
echo "HUMAN_SUBMIT response" > /tmp/orchestrator_control

# Good: Checks status first
STATUS=$(curl -s http://localhost:9100/api/discussion/status)
WAITING=$(echo "$STATUS" | jq -r '.waiting_on_human')

if [ "$WAITING" = "true" ]; then
  echo "HUMAN_SUBMIT response" > /tmp/orchestrator_control
fi
```

### 2. Log All Commands

Keep audit trail of control channel usage:

```bash
COMMAND="HUMAN_SUBMIT This is my response"
echo "$(date): $COMMAND" >> /var/log/orchestrator_control.log
echo "$COMMAND" > /tmp/orchestrator_control
```

### 3. Handle Multi-Word Responses

Control channel splits on spaces - entire line after command is the response:

```bash
# All of these work:
echo "HUMAN_SUBMIT This is a multi-word response" > /tmp/orchestrator_control
echo "HUMAN_SUBMIT $(cat response.txt)" > /tmp/orchestrator_control

# Backend receives: "This is a multi-word response"
```

### 4. Monitor WebSocket Events

Subscribe to WebSocket events for real-time confirmation:

```python
import asyncio
import websockets

async def monitor_events():
    uri = "ws://localhost:9100/ws/discussion/events"
    async with websockets.connect(uri) as ws:
        async for message in ws:
            data = json.loads(message)

            if data.get("type") == "human_turn_completed":
                if data.get("via_control_channel"):
                    print(f"✓ Control channel submit confirmed (turn {data['turn']})")
```

### 5. Implement Retry Logic

Control commands may fail - implement retries with backoff:

```python
def send_with_retry(command, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            send_control_command(command)

            # Wait and verify
            time.sleep(2)
            status = get_discussion_status()

            if not status.get("waiting_on_human"):
                # Turn advanced, success
                return True

            error = status.get("error")
            if error:
                print(f"Attempt {attempt+1} failed: {error}")
        except Exception as e:
            print(f"Attempt {attempt+1} exception: {e}")

        time.sleep(2 ** attempt)  # Exponential backoff

    return False
```

---

## Security Considerations

### Named Pipe Permissions

Control pipe is world-writable by default:

```bash
ls -l /tmp/orchestrator_control
# prw-rw-rw- 1 user user 0 Jan 1 12:00 /tmp/orchestrator_control
```

**Risks:**
- Any user on system can send commands
- Malicious users could disrupt discussions
- Sensitive responses could be injected

**Mitigations:**
1. **Restrict permissions:**
   ```bash
   chmod 600 /tmp/orchestrator_control  # Only owner can write
   ```

2. **Use authentication layer:**
   - Implement token-based auth in control channel
   - Validate sender before processing commands

3. **Run in isolated environment:**
   - Docker container with limited access
   - Separate user account for orchestrator

4. **Audit logging:**
   - Log all control channel commands with timestamps
   - Monitor for suspicious activity

---

## Comparison: Control Channel vs HTTP API

| Feature | Control Channel | HTTP API |
|---------|----------------|----------|
| **Interface** | Named pipe | REST endpoints |
| **Format** | Text commands | JSON |
| **Response** | Status polling | Immediate |
| **Error handling** | Status errors | HTTP codes |
| **Authentication** | File permissions | Not implemented |
| **Remote access** | No (local only) | Yes (network) |
| **Use case** | Scripts, automation | Frontend, external apps |
| **Complexity** | Low | Medium |

**When to use Control Channel:**
- Local automation scripts
- Simple integrations
- Shell scripts and cron jobs
- Legacy system integration

**When to use HTTP API:**
- Frontend applications
- Remote clients
- Microservices
- Systems requiring error responses

---

## Troubleshooting

### Command Not Executing

**Symptom:** Send command, but nothing happens

**Diagnosis:**
1. Check if orchestrator running: `ps aux | grep orchestrator`
2. Check if discussion active: `curl http://localhost:9100/api/discussion/status`
3. Check if waiting on human: `jq .waiting_on_human <<< "$STATUS"`
4. Check status error: `jq .error <<< "$STATUS"`

**Solution:** Ensure discussion running and human turn active.

### Response Not Recorded

**Symptom:** Submit command succeeds but turn not recorded

**Diagnosis:**
1. Check orchestrator logs for errors
2. Verify conversation history: `conversation_manager._conversation_history`
3. Check turn counter incremented: `status.manager.turn_counter`

**Solution:** Check for validation errors or configuration issues.

### Timeout Still Occurs

**Symptom:** Submit via control channel but timeout still triggers

**Diagnosis:**
- Possible race condition: timeout and submit happened simultaneously
- Check timestamps in logs

**Solution:** Submit earlier before timeout, or increase `turn_timeout` value.

---

## Advanced Topics

### Command History

Control channel doesn't maintain command history by default. Implement your own:

```bash
# Wrapper script with history
HISTORY_FILE="/var/log/orchestrator_commands.log"

function orch_submit() {
  local response="$*"
  echo "$(date +%s) HUMAN_SUBMIT $response" >> "$HISTORY_FILE"
  echo "HUMAN_SUBMIT $response" > /tmp/orchestrator_control
}

function orch_skip() {
  echo "$(date +%s) HUMAN_SKIP" >> "$HISTORY_FILE"
  echo "HUMAN_SKIP" > /tmp/orchestrator_control
}

# Usage:
orch_submit This is my response
orch_skip
```

### Multi-Processing Coordination

Multiple processes sending commands - implement locking:

```python
import fcntl

def send_control_command_safe(command):
    """Send command with file locking."""
    lock_file = "/tmp/orchestrator_control.lock"

    with open(lock_file, 'w') as lock:
        # Acquire exclusive lock
        fcntl.flock(lock, fcntl.LOCK_EX)

        try:
            with open(CONTROL_PIPE, 'w') as pipe:
                pipe.write(f"{command}\n")
                pipe.flush()
        finally:
            # Release lock
            fcntl.flock(lock, fcntl.LOCK_UN)
```

---

## Related Documentation

- [Overview](./HumanInTheLoopDoc_Overview.md) - Feature description
- [API Reference](./HumanInTheLoopDoc_API_Reference.md) - HTTP endpoints
- [Configuration](./HumanInTheLoopDoc_Configuration.md) - Config reference
