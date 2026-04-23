# Orchestrator Communication Workflow Analysis

**Date**: 2025-02-12
**Scope**: End-to-end communication flow from orchestrator → tmux controllers → AI CLI sessions

---

## 1. Overview: Communication Architecture

The system follows a **request-response cycle** with **automation-aware queuing**:

```
ConversationManager
    ↓
    Orchestrator.dispatch_command()
    ↓
    ├─→ Check automation state (paused by manual client?)
    ├─→ If paused: Queue command
    └─→ If active: TmuxController.send_command()
        ├─→ Send prompt text (via tmux send-keys -l)
        ├─→ Send Enter key (submit)
        └─→ Wait for response
    ↓
    ConversationManager.facilitate_discussion()
    ├─→ Read output via TmuxController.get_last_output()
    ├─→ Parse response
    ├─→ Validate response
    └─→ Record turn and continue

```

**Key players**:
- **orchestrator.py**: Tracks automation state, queues commands if paused
- **tmux_controller.py**: Sends input, reads output, detects manual attach
- **conversation_manager.py**: Orchestrates turns, prompts, and response handling
- **output_parser.py**: Cleans and extracts responses from raw CLI output

---

## 2. Input Flow: Sending Prompts to AI

### 2.1 Entry Point: `orchestrator.dispatch_command()`

**Location**: `src/orchestrator/orchestrator.py:308-394`

**What it does**:
- Checks if controller's automation is paused (due to manual attach or control channel pause)
- If paused: Queues command and returns `dispatched=False, queued=True`
- If active: Calls `controller.send_command(prompt, submit=True)`

```python
def dispatch_command(self, controller_name: str, command: str, *, submit: bool = True):
    # 1. Check automation state
    status = self.get_controller_status(controller_name)
    paused, reason, manual_clients, controller_pending = self._extract_automation(status)

    if paused:
        # 2. Queue if paused
        return self._queue_command(controller_name, command, submit, ...)

    # 3. Send if active
    result = controller.send_command(command, submit=submit)
```

**Return value** indicates:
- `dispatched=True`: Command was sent immediately
- `queued=True`: Command was queued due to pause
- `queue_source`: "orchestrator" or "controller"
- `pending`: Number of orchestrator-queued commands waiting

---

### 2.2 Command Queue Management

**TmuxController Properties**:
- `_pending_commands`: Deque storing (command, submit_flag) tuples
- `_automation_paused`: Boolean flag set when manual client attached
- `_automation_pause_reason`: Describes why paused ("manual-attach", "manual", etc.)

**Pause Detection Logic** (`tmux_controller.py:522-548`):
```python
def _update_manual_control_state(self):
    # 1. Enumerate connected clients (tmux list-clients)
    clients = self.list_clients()

    # 2. If clients exist: pause automation
    if clients:
        self._set_automation_paused(True, reason="manual-attach", flush_pending=False)

    # 3. If clients detached and we were paused: resume
    elif previous_clients and self._automation_paused:
        self._set_automation_paused(False, flush_pending=True)  # Auto-drain queued commands
```

**Resume Workflow**:
- When automation resumes: `_drain_pending_commands()` executes all queued commands
- Each queued command calls `_send_command_internal(command, submit)` in order
- If any command fails: requeue it and stop draining

---

### 2.3 Core Text Transmission: `send_command()`

**Location**: `src/controllers/tmux_controller.py:1267-1302`

**Sequence**:
1. Update manual client state
2. Check if automation is paused
3. If paused: queue and return False
4. If active: call `_send_command_internal(command, submit)`

**Critical**: Text and Enter are sent as **separate tmux operations**:

```python
def _send_command_internal(self, command: str, submit: bool) -> bool:
    # 1. Snapshot previous output (for delta calculation later)
    self._snapshot_output_state()

    # 2. Normalize multiline input to single line
    text_to_send = " ".join(filter(None, text_to_send.splitlines()))

    # 3. Send text via tmux send-keys -l (literal mode, preserves punctuation)
    self._send_literal_text(text_to_send)  # Sends in 100-char chunks

    # 4. Sleep if configured (post_text_delay)
    if self.post_text_delay > 0:
        time.sleep(self.post_text_delay)

    # 5. Send submit key (Enter or configured key like C-m)
    if submit:
        self._run_tmux_command(["send-keys", "-t", session_name, self.submit_key])

        # 6. Fallback: Also send Enter if submit_key is non-standard
        if self.submit_key != "Enter":
            self._run_tmux_command(["send-keys", "-t", session_name, "Enter"])
```

**Tmux Commands Used**:
- `tmux send-keys -t <session> -l -- <chunk>`: Send literal text (90-100 chars per chunk)
- `tmux send-keys -t <session> <key>`: Send keystroke (Enter, C-m, etc.)

**Key Configuration Options**:
- `submit_key` (default: "Enter"): Key to submit
- `submit_fallback_keys`: Additional keys if primary fails
- `text_enter_delay`: Sleep before sending submit key
- `post_text_delay`: Sleep after text, before submit

---

## 3. Output Flow: Receiving & Processing Responses

### 3.1 Output Capture Mechanism

**Two methods in TmuxController**:

#### A. `capture_output()` (Base class method)
**Location**: `src/controllers/tmux_controller.py` (inherited from SessionBackend)

```python
def capture_output(self, start_line: int = 0, lines: int = 500) -> str:
    # Uses tmux capture-pane -p
    # Returns visible pane buffer (up to 'lines' rows from start_line)
    result = self._run_tmux_command([
        "capture-pane", "-t", session_name, "-p",
        "-S", str(start_line),  # start_line
        "-E", "-1"              # end (last line)
    ])
    return result.stdout
```

#### B. `get_last_output()` (Delta-based, returns new lines only)
**Location**: `src/controllers/tmux_controller.py:1371-1400`

```python
def get_last_output(self, tail_lines: int = 50) -> str:
    # 1. Capture current pane contents
    raw_output = self.capture_output()
    current_lines = raw_output.splitlines()

    # 2. Compare with cached _last_output_lines
    if self._last_output_lines and len(current_lines) >= len(self._last_output_lines):
        # 3. Calculate common prefix (skip unchanged lines)
        prefix_length = self._common_prefix_length(self._last_output_lines, current_lines)
        delta = current_lines[prefix_length:]  # Only new lines
    else:
        # Fallback: return last N lines if buffer was reset
        delta = current_lines[-tail_lines:]

    # 4. Update cache
    self._last_output_lines = current_lines
    return "\n".join(delta).strip()
```

**Snapshot Strategy**:
- Before sending command: `_snapshot_output_state()` caches current pane lines
- After response: `get_last_output()` returns only lines added since snapshot
- Prevents re-reading echoed prompt or old responses

---

### 3.2 Response Parsing: `OutputParser`

**Location**: `src/utils/output_parser.py`

**Input**: Raw tmux pane output (may include ANSI codes, UI glyphs)

**Output**: `ParsedOutput` with:
- `prompt`: Echoed/reconstructed user prompt
- `response`: Extracted AI response text
- `cleaned_output`: Output with UI elements removed
- `raw_output`: Original unmodified output

**Key Functions**:

#### `strip_ansi(text: str) -> str`
- Removes ANSI escape codes (colors, bold, etc.)
- Uses regex: `\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])`

#### `clean_output(text: str, strip_ui: bool = True) -> str`
- Removes CLI UI elements (spinners, progress bars)
- Removes ANSI codes if configured
- Trims empty lines

#### `extract_delimited_response(text: str) -> Optional[str]`
- Looks for explicit delimiters: `**[[RESPONSE_START]]**` / `**[[RESPONSE_END]]**`
- If found, extracts and normalizes content between them
- Fallback: return None (caller uses full output)

#### `split_prompt_and_response(text: str) -> ParsedOutput`
- Separates echoed prompt from response using heuristics
- Tries multiple detection methods:
  1. Look for repeated prompt text at top
  2. Use delimiter markers if present
  3. Assume response is last N lines if prompt not found

---

### 3.3 Response Validation

**Location**: `src/utils/output_parser.py` (ValidationResult, validate_response)

**Validation checks** (configurable in config.yaml):
- Response is not empty
- Response contains minimum length characters
- Response doesn't match error patterns (config defined)
- Response contains expected content patterns

**Configuration example**:
```yaml
response_validation:
  min_response_length: 50
  error_patterns:
    - "error"
    - "failed"
    - "invalid"
  max_retries: 2
  retry_backoff_seconds: [1, 2]  # 1s, then 2s
```

**Return**: `ValidationResult` with:
- `valid`: Whether response passed all checks
- `cleaned_output`: Sanitized response text
- `issues`: List of validation failures
- `should_retry`: Whether orchestrator should retry

---

## 4. Response Cycle in ConversationManager

**Location**: `src/orchestrator/conversation_manager.py:370-700`

### 4.1 Main Loop: `facilitate_discussion()`

```python
def facilitate_discussion(self, topic: str, max_turns: int = 10):
    conversation = []

    while turn_counter < max_turns:
        # 1. Determine next speaker
        speaker = self.determine_next_speaker(conversation)

        # 2. Build prompt (includes context, previous responses)
        prompt = self._build_prompt(speaker, topic, conversation)

        # 3. Dispatch to orchestrator
        dispatch_summary = self.orchestrator.dispatch_command(speaker, prompt)
        is_queued = dispatch_summary.get("queued")

        if is_queued:
            # Command was queued (automation paused); wait and retry later
            continue

        # 4. Capture new output (response)
        parsed_output = self._read_last_output(speaker, pre_snapshot)

        # 5. Validate response
        parser = self._output_parsers.setdefault(speaker, OutputParser())
        validation_result = parser.validate_response(parsed_output, speaker)

        # 6. Retry if invalid (configurable max_retries)
        if not validation_result.valid and retries_used < max_retries:
            # Increment retry counter, sleep, and loop back to step 2
            continue

        # 7. Build turn record
        turn_record = {
            "turn": turn_counter,
            "speaker": speaker,
            "prompt": prompt,
            "dispatch": dispatch_summary,
            "response": validation_result.response_text or parsed_output.response,
            "validation": {
                "valid": validation_result.valid,
                "issues": validation_result.issues,
                "attempts": attempt,
            }
        }
        conversation.append(turn_record)
        turn_counter += 1
```

### 4.2 Prompt Building: `_build_prompt()`

**Includes**:
1. Participant greeting (e.g., "claude, we're collaborating on: Design API")
2. Topic/task description
3. Recent conversation history (if enabled)
4. Context from previous speakers (via MessageRouter)

**Result**: Assembled prompt sent to AI session

---

## 5. Automation Pause & Resume Mechanics

### 5.1 Detection: Manual Attach

**When human attaches to tmux session**:

```bash
tmux attach -t claude  # User takes control
```

**TmuxController detects this**:
1. Next `send_command()` calls `_update_manual_control_state()`
2. `list_clients()` returns list of connected clients
3. If clients exist: set `_automation_paused = True, reason = "manual-attach"`
4. Command is queued instead of sent

**Configuration option**:
```yaml
tmux:
  pause_on_manual_clients: true  # Enable auto-pause on attach
```

### 5.2 Resume: Manual Detach

**When human detaches**:

```bash
# User presses Ctrl+B, then D
# Detaches from tmux
```

**TmuxController resumes**:
1. Next operation calls `_update_manual_control_state()`
2. `list_clients()` returns empty list
3. If automation was paused due to "manual-attach": set `_automation_paused = False`
4. Call `_drain_pending_commands()` to flush queued commands

**Auto-drain sequence**:
```python
def _drain_pending_commands(self):
    while self._pending_commands and not self._automation_paused:
        command, submit = self._pending_commands.popleft()
        try:
            self._send_command_internal(command, submit)
        except Exception:
            # Re-queue if failed
            self._pending_commands.appendleft((command, submit))
            break
```

---

## 6. Status Reporting & Introspection

### 6.1 Controller Status: `get_status()`

**Location**: `src/controllers/tmux_controller.py:1127-1146`

Returns dictionary:
```python
{
    "session": "claude",
    "exists": true,
    "working_dir": "/path/to/project",
    "executable": "claude",
    "automation": {
        "paused": false,
        "reason": null,
        "pending_commands": 0,
        "manual_clients": []
    },
    "health": {
        "total_checks": 42,
        "failures": 0,
        "success_rate": 1.0,
        "last_check": "2025-02-12T15:30:00Z"
    },
    "restart": {
        "policy": "ON_FAILURE",
        "attempts": 0,
        "last_attempt": null
    }
}
```

### 6.2 Orchestrator Introspection

**Pending command counts**:
```python
# Per controller
orch.get_pending_command_count("claude")  # Returns int

# All controllers
orch.get_pending_command_count()  # Returns int

# Detailed list
orch.get_pending_commands("claude")  # Returns [(command, submit), ...]
```

---

## 7. Key Timing & Delays

**Configuration Options** (in `config.yaml` per AI):

| Setting | Default | Purpose |
|---------|---------|---------|
| `startup_timeout` | 10s | Max wait for AI to show ready indicators |
| `response_timeout` | 30s | Max wait for response completion |
| `text_enter_delay` | 0.1s | Pause before sending submit key |
| `post_text_delay` | 0.0s | Pause after text, before submit |
| `ready_check_interval` | 0.5s | Poll interval while waiting for ready |
| `ready_stabilization_delay` | 1-2s | Pause after ready indicator detected |
| `loading_indicator_settle_time` | 1.0s | Pause after loading spinner disappears |

**Typical flow timing**:
1. Send text: 100-200ms (chunks of 100 chars at ~1ms each)
2. Pause after text: 0-100ms (post_text_delay)
3. Send Enter: 10-20ms
4. Wait for response: 1-30s (response_timeout)
5. Parse and validate: 10-100ms

---

## 8. Error Handling & Recovery

### 8.1 Session Errors

| Exception | Cause | Recovery |
|-----------|-------|----------|
| `SessionDead` | Session no longer exists | Auto-restart (configurable) |
| `SessionUnresponsive` | No output detected | Health check triggers restart |
| `SessionStartupTimeout` | AI not ready in time | Raise error, user must retry |
| `CommandTimeout` | Response took too long | Retry with backoff (configurable) |

### 8.2 Output Parsing Fallbacks

**If parsing fails**:
1. Try delimiter markers (`**[[RESPONSE_START]]**`)
2. Try prompt echo detection
3. Fallback: Use last N lines as response
4. If still invalid: Retry entire turn (if max_retries not exceeded)

---

## 9. Sequence Diagram: Happy Path

```
ConversationManager                Orchestrator               TmuxController
       |                                  |                           |
       +------ facilitate_discussion() ---->|                          |
       |      (topic, max_turns)            |                          |
       |                                    +-- dispatch_command() ------>|
       |                                    |   (prompt_text)           |
       |                                    |                      Check automation?
       |                                    |                      (paused=false)
       |                                    |                           |
       |                                    |<-- send_command() --------+
       |                                    |    return True            |
       |                                    |                      send_keys -l
       |                                    |                      send_keys Enter
       |                                    |                           |
       |<------ dispatch_summary -----------+                          |
       |      (dispatched=true, queued=false)                          |
       |                                                               |
       +-- _read_last_output() ------>|                               |
       |                              |                          get_last_output()
       |                              |                          (delta from snapshot)
       |                              |<------ raw output --------+
       |                                                               |
       +-- parser.validate_response()                                |
       |    (parse, clean, validate)                                 |
       |                                                               |
       +-- append turn_record to conversation                        |
       |                                                               |
       +-- determine_next_speaker() -->                              |
       |    (round-robin, next speaker)                              |
       |                                                               |
       | [LOOP: next iteration]                                      |
```

---

## 10. Questions & Edge Cases

### Q1: What if command is sent but automation is paused between dispatch and send?

**Answer**: TmuxController checks automation state at start of `send_command()`. If paused between dispatch check and actual send, the orchestrator detects this and reports `dispatched=false, queue_source=controller`. The orchestrator doesn't retry but may queue again.

### Q2: How does output ordering work with multiple interleaved commands?

**Answer**: Commands are sent sequentially, never in parallel. Each turn completes (response read, validated) before next turn starts. Tmux pane buffer is linear, so output order is guaranteed.

### Q3: What happens if response is still loading when next turn starts?

**Answer**: ConversationManager waits for response completion via `wait_for_ready()`. If CLI is still processing previous response, next prompt is queued by the orchestrator until automation resumes.

### Q4: Can we interrupt a command mid-flight?

**Answer**: Yes, via:
- `send_ctrl_c()`: Sends Ctrl+C to interrupt current operation
- Control channel: `KEY <agent> ctrl+c` command
- Manual attach: User can Ctrl+C manually in tmux

### Q5: How are multiline prompts handled?

**Answer**: All newlines are replaced with spaces before sending. A prompt like:
```
"List the files\nThen summarize them"
```
Becomes:
```
"List the files Then summarize them"
```

This prevents accidental submission on line breaks.

---

## 11. Testing the Workflow

### Unit Test Entry Points

```bash
# Test output parsing
pytest tests/test_output_parser_cleanup.py

# Test automation pause/resume
pytest tests/test_automation_pause.py

# Test conversation management
pytest tests/test_conversation_manager.py

# Test orchestrator + discussions
pytest tests/test_orchestrator_discussion_pause.py
```

### Manual Integration Test

```bash
# Start Claude in tmux
tmux new-session -s claude "claude --dangerously-skip-permissions"

# Run orchestrated discussion
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  "Discuss error handling best practices" \
  --auto-start \
  --max-turns 3 \
  --log-file logs/test-manual.log

# Watch the log
tail -f logs/test-manual.log
```

### Observing Pause/Resume

```bash
# Terminal 1: Start orchestration
PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
  "Test topic" --auto-start --max-turns 20

# Terminal 2: Attach to tmux (triggers pause)
tmux attach -t claude

# Terminal 3: Check status
watch -n 1 "tail logs/orchestrator.log | grep automation"

# In Terminal 2: Press Ctrl+B, then D (detach)
# Watch Terminal 3 for "Resuming automation"
```

---

## 12. Architectural Benefits

1. **Automation-aware queuing**: Human can take control without losing work
2. **Sequential processing**: No race conditions or interleaving
3. **Output delta calculation**: Efficient and accurate response capture
4. **Retry logic**: Handles transient parse failures gracefully
5. **Composable**: Controllers, parsers, managers are independent

---

## Summary Table

| Component | Responsibility | Key Methods |
|-----------|-----------------|-------------|
| **Orchestrator** | Track automation state, queue/dispatch | `dispatch_command()`, `process_pending()` |
| **TmuxController** | Send input, read output, detect manual attach | `send_command()`, `get_last_output()`, `_update_manual_control_state()` |
| **ConversationManager** | Turn-taking, prompt building, validation | `facilitate_discussion()`, `_build_prompt()`, `_read_last_output()` |
| **OutputParser** | Parse & clean responses | `validate_response()`, `split_prompt_and_response()` |
| **ContextManager** | Maintain conversation history | `build_prompt()`, `record_turn()` |
| **MessageRouter** | Broadcast context between participants | `deliver()`, `prepare_prompt()` |

