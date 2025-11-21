# Human In The Loop - Configuration Reference

## Overview

This document describes all configuration options for the Human In The Loop feature, including config.yaml settings, environment variables, and runtime parameters.

## config.yaml Configuration

### Human Configuration Block

Add the `human` block to your `config.yaml` file:

```yaml
human:
  turn_timeout: 300              # Timeout in seconds (0 to disable)
  allow_empty_submissions: false # Whether to accept empty responses
  response_marker: "👤"          # Marker for human turns in transcript
```

### Configuration Fields

#### turn_timeout

**Type:** Integer (seconds)
**Default:** `300` (5 minutes)
**Range:** `0` (disabled) to `3600` (1 hour)

**Description:**
Maximum time to wait for human turn before auto-skipping. When timeout occurs:
- Turn automatically skipped
- Response recorded as `"[Human turn skipped - timeout]"`
- Metadata includes `timeout: true` and `elapsed_seconds`
- WebSocket event `human_turn_timeout` emitted
- Alert shown in UI

**Examples:**

```yaml
# 5 minutes (default)
human:
  turn_timeout: 300

# 10 minutes
human:
  turn_timeout: 600

# Disable timeout (wait indefinitely)
human:
  turn_timeout: 0

# 30 seconds (for testing)
human:
  turn_timeout: 30
```

**Recommendations:**
- **Production:** 300-600 seconds (5-10 minutes)
- **Development/Testing:** 30-60 seconds
- **Automated workflows:** 0 (disabled) or very short (10-30s)
- **Interactive sessions:** 600-900 seconds (10-15 minutes)

---

#### allow_empty_submissions

**Type:** Boolean
**Default:** `false`
**Values:** `true` | `false`

**Description:**
Whether to accept empty or whitespace-only responses.

**When `false` (recommended):**
- Empty submissions rejected with HTTP 400
- Frontend shows error alert
- User must provide non-empty text
- Prevents accidental blank submissions

**When `true`:**
- Empty submissions accepted
- Recorded as empty string in history
- May cause confusion in transcript review

**Examples:**

```yaml
# Reject empty submissions (recommended)
human:
  allow_empty_submissions: false

# Accept empty submissions
human:
  allow_empty_submissions: true
```

**Use Cases for `true`:**
- Acknowledgment-only turns (presence matters, content doesn't)
- Skip-equivalent without explicit skip button
- Automated workflows that may send empty responses

**Use Cases for `false` (recommended):**
- Interactive discussions requiring input
- Code reviews where feedback expected
- Documentation where comments needed

---

#### response_marker

**Type:** String
**Default:** `"👤"` (person emoji)
**Length:** 1-10 characters

**Description:**
Text/emoji marker prefixed to human turns in conversation history. Helps visually distinguish human contributions from AI responses.

**Examples:**

```yaml
# Default emoji
human:
  response_marker: "👤"

# Text marker
human:
  response_marker: "[HUMAN]"

# Different emoji
human:
  response_marker: "🧑"

# ASCII-only
human:
  response_marker: "H:"
```

**Recommendations:**
- **Unicode environments:** Use emoji (👤, 🧑, 👨, 👩)
- **ASCII-only logs:** Use text prefix (`[HUMAN]`, `H:`, `>>>`)
- **Consistency:** Match style of other markers in your system

**Note:** Currently used in backend turn recording but not yet rendered in frontend history display (Phase 7.5 deferred).

---

### Full Example config.yaml

```yaml
# Project settings
project:
  directory: "/home/user/my-project"

# Model configurations
models:
  claude:
    enabled: true
    ready_indicators:
      - ">"
  codex:
    enabled: true
    ready_indicators:
      - ">"
  gemini:
    enabled: true
    ready_indicators:
      - ">"
  qwen:
    enabled: true
    ready_indicators:
      - ">"

# Discussion settings
discussion:
  max_turns: 10
  starting_model: "claude"
  log_level: "INFO"

# Loop detection
loop_detection:
  enabled: true
  threshold: 3
  mode: "pause"  # or "stop"

# Completion detection
completion_detection:
  enabled: true
  mode: "explicit"  # or "auto"
  explicit_signal: "/done"
  fallback_phrases:
    - "looks complete"
    - "we're done"
    - "this is finished"

# Human participant (Phase 1-7 complete)
human:
  turn_timeout: 300              # 5 minutes
  allow_empty_submissions: false # Require non-empty responses
  response_marker: "👤"          # Person emoji for transcript
```

---

## Runtime Configuration

### Session-Level Settings

Some human turn behavior controlled at session start:

```typescript
// Frontend: SessionModelSelector.tsx
const [activeModels, setActiveModels] = useState<string[]>([]);

// User selects models (including Human)
// Models: ['Claude', 'Codex', 'Human']

// On start:
POST /api/sessions/start
{
  "project_directory": "/home/user/project",
  "models": ["claude", "codex", "human"]
}
```

**Session Controls:**
- Which models participate (Human included or not)
- Starting model (never Human, auto-selected first AI)
- Discussion topic and max turns
- No per-session human timeout override (uses global config)

---

### Bypass Toggle

Bypass mode is runtime state, not configuration:

```bash
# Toggle via API
POST /api/discussion/human/bypass/toggle

# Or via control channel
echo "BYPASS_TOGGLE" > /tmp/orchestrator_control  # (Not implemented yet)
```

**Bypass State:**
- Not persisted in config.yaml
- Runtime-only flag in conversation manager
- Resets to `false` when discussion ends (deferred)
- Controlled by user action during discussion

---

## Environment Variables

No environment variables currently used for Human In The Loop feature.

**Future Considerations:**
- `ORCHESTRATOR_HUMAN_TIMEOUT` - Override config timeout
- `ORCHESTRATOR_HUMAN_MARKER` - Override response marker
- `ORCHESTRATOR_HUMAN_ENABLED` - Global enable/disable

---

## Configuration Validation

### On Startup

Orchestrator validates config.yaml on startup:

```python
# src/orchestrator/config_manager.py
human_config = config.get("human", {})

# Validate turn_timeout
timeout = human_config.get("turn_timeout", 300)
if not isinstance(timeout, int) or timeout < 0:
    raise ValueError("human.turn_timeout must be non-negative integer")

# Validate allow_empty_submissions
allow_empty = human_config.get("allow_empty_submissions", False)
if not isinstance(allow_empty, bool):
    raise ValueError("human.allow_empty_submissions must be boolean")

# Validate response_marker
marker = human_config.get("response_marker", "👤")
if not isinstance(marker, str) or len(marker) == 0:
    raise ValueError("human.response_marker must be non-empty string")
```

**Validation Errors:**
- Logged to console on startup
- Orchestrator refuses to start with invalid config
- Fix config.yaml and restart

### Runtime Validation

Runtime validation on human turn submit:

```python
# Phase 3: API endpoint validation
if not human_config.get("allow_empty_submissions", False):
    if not response.strip():
        raise HTTPException(status_code=400, detail="Empty responses not allowed")
```

---

## Configuration Examples

### Example 1: Interactive Development

```yaml
human:
  turn_timeout: 120              # 2 minutes (fast iteration)
  allow_empty_submissions: false # Require feedback
  response_marker: "👤"          # Visual distinction
```

**Use Case:** Active development with frequent human input

---

### Example 2: Code Review

```yaml
human:
  turn_timeout: 600              # 10 minutes (time to review)
  allow_empty_submissions: false # Require comments
  response_marker: "👨‍💻"          # Developer emoji
```

**Use Case:** Thorough code reviews requiring detailed feedback

---

### Example 3: Automated Testing

```yaml
human:
  turn_timeout: 10               # 10 seconds (auto-skip quickly)
  allow_empty_submissions: true  # Accept empty (automated skip)
  response_marker: "[AUTO]"      # Indicate automation
```

**Use Case:** Automated tests where human turns skipped automatically

---

### Example 4: Documentation Review

```yaml
human:
  turn_timeout: 900              # 15 minutes (reading time)
  allow_empty_submissions: false # Require approval/changes
  response_marker: "📝"          # Document emoji
```

**Use Case:** Documentation review requiring careful reading

---

### Example 5: Production Monitoring

```yaml
human:
  turn_timeout: 30               # 30 seconds (quick response)
  allow_empty_submissions: true  # Acknowledge alerts quickly
  response_marker: "🚨"          # Alert emoji
```

**Use Case:** Production incident response with quick acknowledgments

---

## Configuration Migration

### From Previous Versions

If upgrading from version without Human In The Loop:

**Step 1:** Add human block to config.yaml

```yaml
# Add this block
human:
  turn_timeout: 300
  allow_empty_submissions: false
  response_marker: "👤"
```

**Step 2:** Restart orchestrator

```bash
# Stop orchestrator
pkill -f orchestrator

# Start with new config
python -m orchestrator.main
```

**Step 3:** Verify config loaded

```bash
# Check logs for:
# "Loaded configuration: human.turn_timeout=300"
```

### Backward Compatibility

Human In The Loop is backward compatible:
- If `human` block missing → defaults used
- Old discussions without human → work unchanged
- No breaking changes to existing APIs

---

## Configuration Best Practices

### 1. Set Appropriate Timeouts

```yaml
# Too short - frustrating for users
human:
  turn_timeout: 10  # ❌ Only 10 seconds

# Too long - discussions hang
human:
  turn_timeout: 3600  # ❌ 1 hour wait

# Just right - reasonable time
human:
  turn_timeout: 300  # ✅ 5 minutes
```

### 2. Require Non-Empty Responses

```yaml
# Recommended: Prevent accidental blanks
human:
  allow_empty_submissions: false  # ✅

# Use only for automation
human:
  allow_empty_submissions: true  # ⚠️ Use carefully
```

### 3. Use Clear Markers

```yaml
# Good: Visually distinct
human:
  response_marker: "👤"  # ✅ Emoji

# Good: Clear text
human:
  response_marker: "[HUMAN]"  # ✅ Bracketed

# Bad: Confusing
human:
  response_marker: "A"  # ❌ Ambiguous
```

### 4. Document Your Config

```yaml
# Add comments explaining choices
human:
  # 5 min timeout: enough for code review, prevents hanging
  turn_timeout: 300

  # Require feedback: empty submissions not useful for our workflow
  allow_empty_submissions: false

  # Emoji marker: matches our transcript style
  response_marker: "👤"
```

### 5. Version Control Your Config

```bash
# Track config changes
git add config.yaml
git commit -m "Increase human turn timeout to 10 minutes"

# Include in repository
# ✅ config.example.yaml (template)
# ❌ config.yaml (user-specific, .gitignore it)
```

---

## Troubleshooting Configuration Issues

### Config Not Loaded

**Symptom:** Changes to config.yaml not taking effect

**Diagnosis:**
```bash
# Check if config file exists
ls -l config.yaml

# Check if orchestrator reading correct file
ps aux | grep orchestrator | grep config
```

**Solution:** Restart orchestrator after config changes

---

### Timeout Not Working

**Symptom:** Human turns don't timeout after configured duration

**Diagnosis:**
```bash
# Check current config value
grep -A 2 "^human:" config.yaml

# Check logs for timeout detection
tail -f logs/orchestrator.log | grep timeout
```

**Solution:**
- Verify `turn_timeout > 0` (0 disables timeout)
- Restart orchestrator to reload config
- Check system clock (timeout uses time.time())

---

### Empty Submission Accepted

**Symptom:** Empty responses accepted despite `allow_empty_submissions: false`

**Diagnosis:**
```bash
# Verify config value
grep allow_empty_submissions config.yaml

# Check if config reloaded
# (restart orchestrator)
```

**Solution:**
- Verify YAML syntax correct (proper indentation)
- Restart orchestrator
- Check for config loading errors in logs

---

### Invalid Emoji Rendering

**Symptom:** Response marker shows as `?` or boxes

**Diagnosis:**
- Terminal/log viewer doesn't support Unicode
- File encoding issues

**Solution:**
```yaml
# Use ASCII-only marker
human:
  response_marker: "[HUMAN]"
```

---

## Related Documentation

- [Overview](./HumanInTheLoopDoc_Overview.md) - Feature description
- [API Reference](./HumanInTheLoopDoc_API_Reference.md) - HTTP endpoints
- [Control Channel](./HumanInTheLoopDoc_Control_Channel.md) - Control commands
