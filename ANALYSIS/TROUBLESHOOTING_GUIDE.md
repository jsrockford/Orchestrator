# Communication Workflow: Troubleshooting & Debug Guide

**Purpose**: Quick reference for diagnosing issues in the orchestrator's input/output handling

---

## 1. Symptom Decoder

### Symptom: "Command appears to hang / No response from AI"

**Likely causes** (check in order):

#### 1.1 Automation is paused

**Check**:
```python
# In orchestrator code
status = orch.get_controller_status("claude")
automation = status.get("automation", {})
print(f"Paused: {automation.get('paused')}")
print(f"Reason: {automation.get('reason')}")
print(f"Manual clients: {automation.get('manual_clients')}")
print(f"Pending commands: {automation.get('pending_commands')}")
```

**Via tmux directly**:
```bash
# Check if anyone is attached
tmux list-clients -t claude
# If output shows client (e.g., "/dev/pts/3"): automation is paused
```

**Fix**:
- If manual client: `tmux detach -s claude` (if safe)
- If pause is intentional: Wait for resume
- Check orchestrator logs for pause reason

---

#### 1.2 AI is still processing previous response

**Check**:
```bash
# View pane contents
tmux capture-pane -t claude -p | tail -10

# Look for loading indicators (configured in config.yaml)
# Example: "Analyzing...", "⠦", spinners, etc.
```

**Check config**:
```yaml
claude:
  loading_indicators:
    - "⠦"
    - "⠼"
    - "Thinking..."
  response_timeout: 30  # Max wait for response
```

**Fix**:
- Increase `response_timeout` if processing legitimately takes longer
- Check if AI process is stuck: `ps aux | grep claude`
- Send Ctrl+C to interrupt: `tmux send-keys -t claude C-c`

---

#### 1.3 Ready indicator not detected

**Check**:
```bash
# Capture full pane content
tmux capture-pane -t claude -p | tail -20

# Search for expected ready indicator
tmux capture-pane -t claude -p | grep "Type your message"
```

**Check config**:
```yaml
claude:
  ready_indicators:
    - "Type your message or @path/to/file"
  startup_timeout: 10
```

**Verify indicators match actual AI output**:
```bash
# Start new session manually
tmux new-session -s test-claude "claude --dangerously-skip-permissions"

# Wait for startup
sleep 5

# Check what's actually displayed
tmux capture-pane -t test-claude -p | tail -20
```

**Fix**:
- Update `ready_indicators` to match actual prompt text
- Increase `startup_timeout` if AI takes longer to start
- Check if prompt changed in recent AI version updates

---

### Symptom: "Response is empty / No text captured"

**Likely causes**:

#### 2.1 Output capture is working but response was empty

**Check**:
```bash
# Send simple test command
tmux send-keys -t claude -l -- "echo test123"
tmux send-keys -t claude Enter

# Capture output
sleep 1
tmux capture-pane -t claude -p | tail -5
# Should see: "echo test123" or "test123"
```

**If echo works but AI doesn't respond**:
- AI process may be hung or waiting for input
- Try sending Ctrl+C: `tmux send-keys -t claude C-c`

---

#### 2.2 Delta calculation returned empty

**Check code path**:
```python
# In conversation_manager
parser = OutputParser()
parsed = parser.split_prompt_and_response(raw_output)
print(f"Prompt: {parsed.prompt!r}")
print(f"Response: {parsed.response!r}")
print(f"Cleaned: {parsed.cleaned_output!r}")
```

**Diagnose snapshot issue**:
```python
# Before sending command
pre_snapshot = self._capture_snapshot("claude")
# List of lines cached

# After response
raw = controller.get_last_output()
# If raw is empty, delta calculation failed
```

**Fix**:
- Increase `capture_lines` in config if buffer is small
- Check if pane was cleared (Ctrl+L): delta calculation handles this
- Verify tmux capture-pane is working: `tmux capture-pane -t claude -p | wc -l`

---

### Symptom: "Commands are being queued / not executing"

**Likely causes**:

#### 3.1 Automation is paused

**Check**:
```bash
# Check orchestrator status
orch.get_pending_command_count("claude")  # > 0 means commands queued
orch.get_pending_commands("claude")       # List queued commands

# Check if pause reason is legitimate
status = orch.get_controller_status("claude")
automation = status.get("automation", {})
print(f"Reason: {automation.get('reason')}")
```

**Resume manually**:
```python
# If safe to resume
controller = orch.controllers["claude"]
controller.resume_automation(flush_pending=True)
```

---

#### 3.2 Too many queued commands

**Check**:
```python
pending = orch.get_pending_command_count()
print(f"Total queued: {pending} commands")

# Per controller
for name in orch.controllers.keys():
    count = orch.get_pending_command_count(name)
    print(f"{name}: {count} pending")
```

**Typical queue size**:
- Healthy: 0-2 commands
- Warning: 3-10 commands
- Problem: >10 commands

**Fix**:
- Check if draining is stalled: logs should show "Draining X queued commands"
- Check if automation keeps getting re-paused
- Monitor manually: `watch -n 1 'orch.get_pending_command_count()'`

---

## 2. Log Analysis Patterns

### 2.1 Healthy Discussion Flow

```log
[INFO] Sending command: "list files"...
[INFO] Submit key 'Enter' send-keys returned 0
[DEBUG] Waiting for response...
[DEBUG] Startup ready indicator found: "Type your message"
[INFO] Response complete; captured 342 chars
[DEBUG] Response text: "file1.txt\nfile2.txt"
[INFO] Turn 0: claude → response valid
```

**What to look for**:
- send-keys returns 0 (success)
- Ready indicator found within timeout
- Response captured (non-empty)
- Validation passed

---

### 2.2 Problematic: Automation Paused

```log
[INFO] Manual clients detected: ['/dev/pts/3']; pausing automation
[WARNING] Automation currently paused (reason: manual-attach); queueing command
[INFO] Queued command due to automation pause (pending=1)
[INFO] All manual clients detached; resuming automation
[INFO] Draining 1 queued command(s)
[INFO] Sending command: "list files"...
```

**What to look for**:
- "pausing automation" with reason
- Commands being queued
- "Draining X queued commands" on resume

---

### 2.3 Problematic: Response Validation Failed

```log
[INFO] Sending command: "list files"...
[INFO] Submit key 'Enter' send-keys returned 0
[DEBUG] Response captured: "..."
[WARNING] Response validation failed: [empty_response, min_length_not_met]
[INFO] Retry 1/2 after 1.0s...
[INFO] Sending command: "list files"...
[INFO] Response valid after retry 1
```

**What to look for**:
- Validation failures listed
- Retry attempt and delay
- Eventually: "valid after retry X" or "gave up after X retries"

---

### 2.4 Problematic: Timeout

```log
[INFO] Sending command: "list files"...
[DEBUG] Waiting for response (timeout: 30.0s)...
[DEBUG] Still waiting... (5s elapsed)
[DEBUG] Still waiting... (10s elapsed)
[DEBUG] Still waiting... (20s elapsed)
[WARNING] Response timeout after 30.0s
```

**What to look for**:
- Timeout message with elapsed seconds
- No ready indicator detected
- Previous log lines show command was sent successfully

**Fix**:
- Check if AI is actually processing: `tmux capture-pane -t claude -p | tail -5`
- Increase `response_timeout` if processing takes longer
- Check for loading indicators blocking ready detection

---

## 3. Tracing a Single Command

### 3.1 Manual Trace: Step by Step

```bash
# Step 1: Verify session exists
tmux has-session -t claude && echo "Session exists" || echo "Session missing"

# Step 2: Check automation state
# (Run in Python REPL with orchestrator loaded)
orch.get_controller_status("claude")  # Check 'automation' field

# Step 3: Send test command manually
tmux send-keys -t claude -l -- "echo hello"
tmux send-keys -t claude Enter
sleep 2

# Step 4: Capture output
tmux capture-pane -t claude -p | tail -10

# Step 5: Check for ready indicator
tmux capture-pane -t claude -p | tail -10 | grep "Type your message"
```

---

### 3.2 Programmatic Trace

```python
from src.controllers.tmux_controller import TmuxController
from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator

# Setup
orch = DevelopmentTeamOrchestrator()
controller = orch.controllers["claude"]

# Step 1: Check status
status = orch.get_controller_status("claude")
print(f"Status: {status}")

# Step 2: Capture before
before = controller.capture_output()
print(f"Before: {len(before)} chars, {len(before.splitlines())} lines")

# Step 3: Send command
result = orch.dispatch_command("claude", "list files")
print(f"Dispatch result: {result}")

# Step 4: Wait a bit and capture after
import time
time.sleep(2)
after = controller.get_last_output()
print(f"After: {len(after)} chars, {len(after.splitlines())} lines")
print(f"Response: {after!r}")

# Step 5: Parse and validate
from src.utils.output_parser import OutputParser
parser = OutputParser()
parsed = parser.split_prompt_and_response(after)
validation = parser.validate_response(parsed, "claude")
print(f"Valid: {validation.valid}")
print(f"Issues: {validation.issues}")
```

---

## 4. Common Configuration Issues

### Issue: Submit Key Not Working

**Symptom**: Text arrives but isn't submitted (not processing)

**Check config**:
```yaml
claude:
  submit_key: "C-m"  # Ctrl+M
  submit_fallback_keys: ["Enter"]
  text_enter_delay: 0.1
  post_text_delay: 0.0
```

**Diagnostic**:
```bash
# Test different submit keys manually
tmux send-keys -t claude -l -- "test1"
tmux send-keys -t claude Enter
sleep 1
# Should process

tmux send-keys -t claude -l -- "test2"
tmux send-keys -t claude "C-m"
sleep 1
# Should also process
```

**Fix**:
- Swap submit_key and fallback
- Add additional fallback keys
- Increase text_enter_delay to give pane time to accept input

---

### Issue: Ready Indicator Not Matching

**Symptom**: Timeout waiting for ready indicator

**Check actual prompt**:
```bash
tmux new-session -s debug "claude --dangerously-skip-permissions"
sleep 5
tmux capture-pane -t debug -p
# Look at exact text displayed
```

**Update config**:
```yaml
claude:
  ready_indicators:
    - "EXACT_TEXT_FROM_PROMPT"  # Copy exact string
    - "Type your message or @path/to/file"
```

---

### Issue: Output Capture Too Small

**Symptom**: Response is truncated or incomplete

**Check config**:
```yaml
tmux:
  capture_lines: 200  # Default, may be too small
```

**Increase**:
```yaml
tmux:
  capture_lines: 500  # Larger pane buffer
  # Or per-AI:
claude:
  capture_lines: 500
```

**Verify tmux scrollback**:
```bash
# Check scrollback size
tmux show-options -t claude | grep history-limit
# Default is usually 2000; adjust if needed
```

---

## 5. Recovery Procedures

### 5.1 Unblock Paused Automation

**Situation**: Automation is paused waiting for manual client to detach

**Option 1: Manual detach**
```bash
tmux detach -s claude
# Automation should resume automatically
```

**Option 2: Force resume**
```python
controller = orch.controllers["claude"]
controller.resume_automation(flush_pending=True)
```

**Option 3: Kill client**
```bash
# If client is non-responsive
tmux kill-session -t claude
# Warning: This kills the entire session!
```

---

### 5.2 Drain Queued Commands

**Check pending**:
```python
pending = orch.get_pending_commands("claude")
print(f"Queued: {len(pending)} commands")
for cmd, submit in pending:
    print(f"  - {cmd[:50]}... (submit={submit})")
```

**Manual drain**:
```python
result = orch.process_pending("claude")
print(f"Flushed: {result['flushed']}")
print(f"Remaining: {result['remaining']}")
print(f"Paused: {result['paused']}")
```

---

### 5.3 Restart Session

**Check if responsive**:
```bash
tmux send-keys -t claude -l -- "echo alive"
tmux send-keys -t claude Enter
sleep 1
tmux capture-pane -t claude -p | grep alive
# If no output, session may be hung
```

**Kill and restart**:
```python
controller = orch.controllers["claude"]
controller.kill()  # Terminate session
time.sleep(1)
controller.start()  # Restart
controller.wait_for_startup()  # Wait for ready
```

---

## 6. Performance Tuning

### 6.1 Speed Up Response Capture

**Current timings** (typical):
- send_keys text: 100ms (for 100 chars)
- send_keys Enter: 5ms
- capture_pane: 10ms
- parse response: 5ms
- **Total**: ~120ms per command

**Optimization**:
```yaml
claude:
  text_enter_delay: 0.05  # Reduce from 0.1s
  post_text_delay: 0.0    # Set to 0 if not needed

tmux:
  capture_lines: 300      # Reduce from 500 if responses are short
```

**Tradeoff**: Faster = less reliable. Only reduce if experiencing issues.

---

### 6.2 Reduce Memory Usage

**Issue**: Queue grows too large (many paused commands)

**Check**:
```python
# Monitor queue size
pending_count = orch.get_pending_command_count()
# Each command ~100-500 bytes
# 1000 commands = 100-500 KB
```

**Reduce**:
- Process pending more frequently (shorter polling interval)
- Reduce max_turns to restart discussion sooner
- Investigate why automation keeps getting paused

---

## 7. Testing & Validation

### 7.1 Unit Test: Response Parsing

```python
from src.utils.output_parser import OutputParser

parser = OutputParser()

# Test case: Simple response
test_output = """
$ list files
file1.txt
file2.txt
$
"""
parsed = parser.split_prompt_and_response(test_output)
assert "file1.txt" in parsed.response
assert parsed.prompt is not None
```

---

### 7.2 Unit Test: Automation Pause/Resume

```python
from src.controllers.tmux_controller import TmuxController

controller = TmuxController("test-session", "claude", ...)

# Start paused
controller.pause_automation(reason="test")
assert controller.automation_paused == True

# Queue command
command_sent = controller.send_command("hello")
assert command_sent == False  # Not sent, queued
assert len(controller.get_pending_commands()) == 1

# Resume and drain
controller.resume_automation(flush_pending=True)
assert controller.automation_paused == False
assert len(controller.get_pending_commands()) == 0
```

---

### 7.3 Integration Test: Full Cycle

```bash
# Run test orchestrated discussion
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  "Test message: say hello to each other" \
  --auto-start \
  --kill-existing \
  --max-turns 3 \
  --log-file logs/test-trace.log

# Monitor for issues
tail -f logs/test-trace.log | grep -E "ERROR|WARNING|TIMEOUT"

# Verify completion
grep "Turn 2:" logs/test-trace.log  # Should exist if 3 turns completed
```

---

## 8. Emergency Procedures

### 8.1 Stuck Session (No Response)

**Escalation steps**:
1. Send Ctrl+C: `tmux send-keys -t claude C-c`
2. Wait 2 seconds
3. Capture output: `tmux capture-pane -t claude -p | tail -5`
4. If still no response: Kill session
   ```bash
   tmux kill-session -t claude
   sleep 1
   # Restart via orchestrator
   python3 -c "orch.controllers['claude'].start()"
   ```

---

### 8.2 Orphaned Queue (Commands Lost)

**Check**:
```python
pending = orch.get_pending_commands("claude")
if pending:
    print(f"Lost {len(pending)} commands:")
    for cmd, submit in pending:
        print(f"  {cmd[:30]}...")
```

**Recovery**:
- If commands are important: note them and re-submit manually
- If safe: clear queue by restarting orchestrator
- Consider improving logging to avoid future losses

---

## 9. Glossary of Terms

| Term | Definition |
|------|-----------|
| **Pane** | Single tmux window division where process runs |
| **Scrollback** | Historical buffer of pane output (2000+ lines) |
| **Ready indicator** | Text pattern showing AI is ready for input |
| **Loading indicator** | Text pattern showing AI is processing |
| **Snapshot** | Cached pane contents before sending command |
| **Delta** | New output lines since snapshot |
| **Automation paused** | Commands are queued, not immediately sent |
| **Manual client** | Human attached to tmux session |
| **Dispatch** | Send command immediately vs. queue |
| **Fallback key** | Secondary submit key if primary fails |

---

## Quick Reference Card

```
# Check if automation is paused
orch.get_controller_status("claude")["automation"]["paused"]

# See queued commands
orch.get_pending_commands("claude")

# Resume and flush queue
orch.controllers["claude"].resume_automation(flush_pending=True)

# Send test command manually
tmux send-keys -t claude -l -- "echo test"
tmux send-keys -t claude Enter

# View last output
tmux capture-pane -t claude -p | tail -20

# Check ready indicator
tmux capture-pane -t claude -p | grep "Type your message"

# Kill stuck session
tmux kill-session -t claude

# Run test discussion
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py "test" \
  --auto-start --max-turns 3 --log-file logs/test.log

# Watch for errors
tail -f logs/test.log | grep -E "ERROR|WARNING"
```

---

**For additional help**: Check orchestrator logs in `logs/` directory or enable DEBUG level logging in `config.yaml`.

