# Tmux I/O Mechanics: Deep Dive

**Focused Analysis**: How tmux sessions handle input, capture output, and maintain state

---

## 1. Tmux Pane Architecture

### 1.1 Session & Pane Structure

```
Tmux Server
├── Session: "claude"
│   └── Window: 0
│       └── Pane: 0 (PID: 12345)
│           ├── Input buffer (keyboard input queue)
│           ├── Display buffer (visible text, ~200-500 lines)
│           └── Scrollback buffer (history, ~2000 lines)
│
└── Session: "gemini"
    └── Window: 0
        └── Pane: 0 (PID: 12346)
            ├── Input buffer
            ├── Display buffer
            └── Scrollback buffer
```

### 1.2 Text Flow in Tmux

```
┌─────────────────────────────────────────────┐
│  AI CLI Process (e.g., "claude")            │
│  ├── STDIN: Receives typed input            │
│  ├── STDOUT: Writes output (rendered)       │
│  └── STDERR: Error output (typically merged)│
└─────────────────────────────────────────────┘
         ↑ (pty/pipe)                    ↓
         │                                │
    [Input Queue]                    [Display Buffer]
    (unbuffered)                     (what user sees)
                                          ↓
                                    [Scrollback Buffer]
                                    (history, inspectable
                                     via capture-pane)
```

---

## 2. Sending Input: The tmux send-keys Command

### 2.1 Command Syntax

```bash
tmux send-keys -t <session>[:<window>.<pane>] [FLAGS] <key> [<key> ...]
```

**Key flags**:
- `-l`: Literal mode (send raw text, not key names)
- `-H`: Send with history (for read-only clients, unused)
- `--`: End of flags (required before text containing '-')

### 2.2 Literal Mode vs Key Mode

**Key Mode** (default):
```bash
tmux send-keys -t claude Enter
# Sends: Enter keystroke (newline)

tmux send-keys -t claude "C-m"
# Sends: Ctrl+M (same as Enter in many terminals)

tmux send-keys -t claude Up
# Sends: Up arrow keystroke
```

**Literal Mode** (text):
```bash
tmux send-keys -t claude -l -- "Hello, world!"
# Sends: H e l l o , SPACE w o r l d !
# Character by character to STDIN
# Preserves apostrophes, special chars

tmux send-keys -t claude -l -- "It's working"
# Sends: It's working (apostrophe preserved)
# Without -l, apostrophe might be interpreted as key
```

**Chunking Strategy** (TmuxController):
```python
def _send_literal_text(self, text: str) -> None:
    chunk_size = 100  # Split into 100-char chunks
    for idx in range(0, len(text), chunk_size):
        chunk = text[idx : idx + chunk_size]
        result = self._run_tmux_command([
            "send-keys", "-t", self.session_name, "-l", "--", chunk
        ])
        # Each chunk gets ~100ms to be delivered
```

**Why chunking?**
- Prevents tmux command line length issues
- Allows brief pauses between chunks for buffer flushing
- Reduces risk of input corruption on large prompts

---

## 3. Capturing Output: The tmux capture-pane Command

### 3.1 Command Syntax

```bash
tmux capture-pane -t <session>[:<window>.<pane>] -p [FLAGS]
```

**Key flags**:
- `-p`: Print to stdout (required for output capture)
- `-S <start_line>`: Start line (0 = current top, negative = scrollback)
- `-E <end_line>`: End line (-1 = bottom)
- `-J`: Join wrapped lines (default in tmux 3.0+)
- `-e`: Include escape sequences (color codes, styles)

**Common usage**:
```bash
# Get last 200 lines of visible buffer
tmux capture-pane -t claude -p -S -200 -E -1

# Get full scrollback (up to server limit)
tmux capture-pane -t claude -p -S "-" -E -1

# Get just the last line
tmux capture-pane -t claude -p -S -1 -E -1
```

**TmuxController usage**:
```python
def capture_output(self, start_line: int = 0, lines: int = 500) -> str:
    # Capture from start_line to end of pane
    result = self._run_tmux_command([
        "capture-pane", "-t", self.session_name, "-p",
        "-S", str(start_line),
        "-E", "-1"
    ])
    return result.stdout  # Raw text from pane
```

### 3.2 Gotchas with capture-pane

**Issue 1: ANSI Escape Sequences**
```
Raw pane output:
   "\033[32mSuccess\033[0m\nAll tests passed."
                  ↓ (strip_ansi)
   "Success\nAll tests passed."
```
- Solution: `OutputParser.strip_ansi()` removes ANSI codes

**Issue 2: Line Wrapping**
```
Pane width: 80 chars
Input: "This is a very long line that exceeds the pane width..."

Pane displays:
   "This is a very long line that exceeds the pane"
   "width..."

capture-pane with -J (join wrapped lines):
   "This is a very long line that exceeds the pane width..."
```
- Solution: tmux 3.0+ defaults to joining; explicit `-J` flag

**Issue 3: Scrollback Limits**
```
Default tmux scrollback: 2000 lines
If session has been active for hours with verbose output:
   - Only last 2000 lines are captured
   - Older output is lost
```
- Solution: Capture immediately after each command
- Configure larger scrollback in tmux.conf if needed

---

## 4. Output Delta Calculation: Detecting New Lines

### 4.1 The Problem

After sending a command, how do we know which output is the response?

```
Buffer before send:
   Line 1: (previous response)
   Line 2: (previous response)
   Line 3: (previous response)

After send_keys -l -- "list files" + send_keys Enter:
   Line 1: (previous response)
   Line 2: (previous response)
   Line 3: (previous response)
   Line 4: $ list files                    <-- Echo of prompt
   Line 5: file1.txt
   Line 6: file2.txt
   Line 7: $                               <-- Ready prompt

Question: Which lines are the new response?
Answer: Lines 4-7 (since line 3 before)
```

### 4.2 Snapshot & Delta Strategy

**Before sending command** (`_snapshot_output_state`):
```python
def _snapshot_output_state(self) -> None:
    raw_output = self.capture_output()
    self._last_output_lines = raw_output.splitlines()
    # Save current state: 3 lines total
```

**After getting response** (`get_last_output`):
```python
def get_last_output(self, tail_lines: int = 50) -> str:
    raw_output = self.capture_output()
    current_lines = raw_output.splitlines()  # Now 7 lines

    # Calculate common prefix
    prefix_length = self._common_prefix_length(
        self._last_output_lines,  # [Line1, Line2, Line3]
        current_lines             # [Line1, Line2, Line3, Line4, Line5, Line6, Line7]
    )
    # Result: prefix_length = 3 (first 3 lines match)

    delta = current_lines[prefix_length:]
    # Result: delta = [Line4, Line5, Line6, Line7]
    # This is the response!

    self._last_output_lines = current_lines  # Update cache
    return "\n".join(delta).strip()
```

### 4.3 Edge Case: Buffer Reset

**Scenario 1: User clears screen (Ctrl+L)**
```
Before: 500 lines cached
After clear: 1 line in buffer

current_lines.length (1) < self._last_output_lines.length (500)
→ Fallback: return last 50 lines of current buffer
```

**Scenario 2: Output scrolled out of scrollback**
```
Before: Lines cached up to line 2000
Buffer recycles: Only lines 1-2000 visible
After capture: Lines show from cache #1800

Prefix match fails because early lines shifted out
→ Fallback: return last 50 lines
```

---

## 5. Waiting for Response Completion

### 5.1 Detection Strategy

**Problem**: How do we know the AI has finished responding?

**Solution: Multi-factor detection via `wait_for_ready()`**

```python
def wait_for_ready(self, timeout: float = 30) -> bool:
    deadline = time.time() + timeout

    while time.time() < deadline:
        output = self.capture_output()
        search_text = self._indicator_text(output)  # Strip ANSI

        # Check 1: Loading indicators present?
        if self.loading_indicators:
            has_loading = any(
                indicator in search_text
                for indicator in self.loading_indicators
            )
            if has_loading:
                # Still processing
                time.sleep(0.5)
                continue

        # Check 2: Ready indicator present?
        ready_found = any(
            indicator in search_text
            for indicator in self.ready_indicators
        )
        if ready_found:
            return True

        time.sleep(0.5)

    return False  # Timeout
```

### 5.2 Configuration: Ready & Loading Indicators

**Example for Claude**:
```yaml
claude:
  ready_indicators:
    - "Type your message or @path/to/file"  # Shows when ready for input
    - "Thinking..."                          # Alternative indicator
  loading_indicators:
    - "⠦"  # Spinner characters
    - "⠼"
    - "Analyzing..."
```

**Example for Gemini**:
```yaml
gemini:
  ready_indicators:
    - "Type your message or @path/to/file"
    - "Model:"
  loading_indicators:
    - "Enhancing..."
    - "⠋"  # Different spinner
    - "⠙"
  ready_stabilization_delay: 2.0  # Extra pause after ready detected
```

**Logic**:
1. Wait for loading indicator to **disappear**
2. Then wait for ready indicator to **appear**
3. Optional: Wait additional `ready_stabilization_delay` for buffer to settle

---

## 6. Automation Pause Detection: Manual Client Detection

### 6.1 List Active Clients

**Command**:
```bash
tmux list-clients -t <session>
```

**Output examples**:
```
# No clients attached
$ tmux list-clients -t claude
(output empty)
(exit code: 0)

# One client attached
$ tmux list-clients -t claude
/dev/pts/3

# Multiple clients
$ tmux list-clients -t claude
/dev/pts/3
/dev/pts/4
```

### 6.2 Detection in TmuxController

```python
def _update_manual_control_state(self) -> None:
    try:
        clients = self.list_clients()
    except SessionNotFoundError:
        self._manual_clients = []
        return

    previous_clients = list(self._manual_clients)
    self._manual_clients = clients

    if not self._pause_on_manual_clients:
        return

    # Detect attach (transition from 0 → 1+ clients)
    if clients:
        self._set_automation_paused(True, reason="manual-attach", flush_pending=False)
        self.logger.info(f"Manual clients detected: {clients}; pausing automation")

    # Detect detach (transition from 1+ → 0 clients)
    elif previous_clients and self._automation_paused:
        if self._automation_pause_reason == "manual-attach":
            self._set_automation_paused(False, flush_pending=True)
            self.logger.info("All manual clients detached; resuming automation")
```

### 6.3 When is this called?

**Frequency**: Before each `send_command()` call
```python
def send_command(self, command: str, submit: bool = True) -> bool:
    self._update_manual_control_state()  # ← Check manual attach
    if self._automation_paused:
        self._enqueue_command(command, submit)
        return False
    # ... continue with send
```

**Polling interval**: Determined by orchestrator's turn timing
- Typical: Every 2-5 seconds (one command per turn)
- Minimum: 0.5 seconds if tests are fast

---

## 7. Sending vs. Queuing Logic

### 7.1 Decision Tree

```
send_command(prompt) called
    ↓
_update_manual_control_state()  ← Check if human attached
    ↓
Is automation paused?
    ├─ YES → _enqueue_command(prompt) → return False
    │        (Queued for later)
    │
    └─ NO → _send_command_internal(prompt)
            ├─ Snapshot output state
            ├─ Send text (chunked)
            ├─ Send Enter key
            └─ return True (Dispatched)
```

### 7.2 Queued Command Replay

**When automation resumes**:
```python
def _set_automation_paused(self, paused: bool, ..., flush_pending: bool = True):
    if not paused and flush_pending:
        self._drain_pending_commands()

def _drain_pending_commands(self) -> None:
    # Process queue in FIFO order
    while self._pending_commands and not self._automation_paused:
        command, submit = self._pending_commands.popleft()
        try:
            self._send_command_internal(command, submit)
        except Exception as exc:
            # Requeue if failed
            self._pending_commands.appendleft((command, submit))
            break
```

**Guarantees**:
- FIFO order preserved
- No command loss on pause
- Commands re-executed in original sequence
- If drain fails: remaining commands stay queued

---

## 8. Keystroke Handling: Submit Keys

### 8.1 Standard Submit Keys

**Default**: `Enter` (sends ASCII 0x0D)

**Alternatives configured per-AI**:
```yaml
claude:
  submit_key: "Enter"
  submit_fallback_keys: ["C-m"]  # Ctrl+M fallback

gemini:
  submit_key: "C-m"               # Use Ctrl+M
  submit_fallback_keys: []

qwen:
  submit_key: "C-m"
  submit_fallback_keys: ["Enter"]
```

### 8.2 Submit Sequence

```python
def _send_command_internal(self, command: str, submit: bool) -> bool:
    # ... send text ...

    if submit:
        # 1. Sleep before submit (configurable)
        if self.text_enter_delay > 0:
            time.sleep(self.text_enter_delay)

        # 2. Send primary submit key
        result = self._run_tmux_command([
            "send-keys", "-t", session, self.submit_key
        ])

        # 3. Send Enter as fallback (if primary is non-standard)
        if self.submit_key != "Enter":
            self._run_tmux_command([
                "send-keys", "-t", session, "Enter"
            ])

        # 4. Trigger fallback keys if needed
        if self.submit_fallback_keys:
            self._trigger_fallback_submit_if_needed()
```

**Why fallbacks?**
- Some CLIs need multiple submit signals
- Different terminal modes interpret keys differently
- Ensures reliability across Linux/macOS/WSL

---

## 9. Output Cleaning: ANSI & UI Removal

### 9.1 ANSI Escape Code Removal

**Pattern**:
```regex
\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])
```

**Examples**:
```
Raw:    "\033[32mSUCCESS\033[0m"
Cleaned: "SUCCESS"

Raw:    "\033[1;33mWarning: \033[0m\033[31mFailed\033[0m"
Cleaned: "Warning: Failed"
```

### 9.2 CLI UI Element Removal

**Common patterns**:
```
Spinner glyphs:      ⠦ ⠼ ⠴ (Braille)
Progress bars:       ▁▂▃▄▅▆▇█
Loading text:        "Loading..." "Processing..."
Menu glyphs:         ⊷ ✓ ✗
```

**Configuration**:
```yaml
output_parser:
  strip_ui: true
  strip_trailing_prompts: false
  ui_patterns:
    - "⠦"
    - "Analyzing..."
    - "^\s*[▁▂▃▄▅▆▇█]"  # Regex for progress bars
```

---

## 10. Response Delimiters

### 10.1 Explicit Markers

**Optional feature**: AI can wrap responses in markers

**Markers**:
```
**[[RESPONSE_START]]**
This is the AI's response content.
It can span multiple lines.
**[[RESPONSE_END]]**
```

**Benefit**: Unambiguous response extraction even with complex output

**Usage in OutputParser**:
```python
def extract_delimited_response(self, text: str) -> Optional[str]:
    if "**[[RESPONSE_START]]**" in text and "**[[RESPONSE_END]]**" in text:
        start = text.index("**[[RESPONSE_START]]**") + len("**[[RESPONSE_START]]**")
        end = text.index("**[[RESPONSE_END]]**")
        return text[start:end].strip()
    return None  # Fallback to other extraction methods
```

---

## 11. Health Check: Detecting Dead Sessions

### 11.1 Check Methods

**Method 1: Session Existence**
```bash
tmux has-session -t claude
# Exit code: 0 if exists, 1 if not
```

**Method 2: Responsive Output**
```bash
tmux capture-pane -t claude -p
# If returns output: session is responsive
# If empty: may indicate hung process
```

**Method 3: Command Echo**
```bash
# Send test command, check if echoed
send_keys -l -- "echo health_check_12345"
send_keys Enter
# Then capture and look for "health_check_12345"
```

### 11.2 Configuration

```yaml
tmux:
  health_check_interval: 30.0        # Check every 30s
  health_check_timeout: 5.0          # Timeout for checks
  max_failed_health_checks: 3        # Auto-restart after 3 failures
```

---

## 12. Performance Characteristics

### 12.1 Timing

| Operation | Time | Notes |
|-----------|------|-------|
| send_keys (text chunk) | 1-5ms | Per 100-char chunk |
| send_keys (keystroke) | 0.5-1ms | Single key |
| capture_pane (200 lines) | 5-20ms | Depends on pane size |
| strip_ansi (1000 chars) | 1-2ms | Regex processing |
| split_prompt_response | 2-5ms | Heuristics |
| wait_for_ready (avg) | 100-500ms | Poll interval 0.5s |

### 12.2 Scalability

**Pane size limits**:
- Maximum visible buffer: ~500 lines (configurable)
- Scrollback buffer: ~2000 lines (server setting)
- Width limit: Typically 200+ characters

**Queue capacity**:
- No hard limit on pending commands
- Memory scales with queue size (~100 bytes per command)

---

## 13. Debugging Tools

### 13.1 Manual Inspection

```bash
# Check session details
tmux list-sessions -F "#{session_name} #{session_windows}"

# Monitor pane contents
watch -n 0.5 'tmux capture-pane -t claude -p | tail -20'

# Check active clients
tmux list-clients -t claude

# Send test command
tmux send-keys -t claude -l -- "echo test"
tmux send-keys -t claude Enter

# Get scrollback with escape sequences visible
tmux capture-pane -t claude -p -e | cat -A
# ^ shows ANSI codes as [<sequence>
```

### 13.2 Logging

**Enable debug logging in config**:
```yaml
logging:
  level: DEBUG
  controllers:
    tmux_controller:
      debug_wait_logging: true  # Verbose wait-for-ready logs
```

**Key logs to watch**:
```
[INFO] Sending command: "list files"
[INFO] Submit key 'Enter' send-keys returned 0
[DEBUG] Startup ready indicator found: 'Type your message'
[DEBUG] Waiting for response... (15/30 seconds elapsed)
[DEBUG] Response complete; captured 342 chars
```

---

## Summary

The tmux I/O system provides:
- **Reliable text delivery** via chunked literal mode
- **Accurate output capture** with delta calculation
- **Responsiveness detection** via indicator patterns
- **Human interruption** via client attachment monitoring
- **Queue safety** with FIFO replay on resume

All operations are **synchronous** and **sequential**, eliminating race conditions while maintaining high reliability for the orchestration system.

