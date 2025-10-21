# Claude Code Interaction Findings

## Test Date
2025-10-06

## Environment
- **OS**: WSL2 (Ubuntu)
- **Tmux Version**: 3.2a
- **Claude Code Version**: v2.0.8
- **Model**: Sonnet 4.5

## Test 1.1: Startup Behavior

### Observations

#### Startup Sequence
1. **Trust Prompt** (appears immediately):
   - Dialog asking "Do you trust the files in this folder?"
   - Shows directory path
   - Option 1 (default): "Yes, proceed"
   - Option 2: "No, exit"
   - Requires Enter key to confirm

2. **Initialization Time**:
   - Trust prompt: < 1 second
   - After confirming trust: ~3 seconds to ready state
   - **Total startup time: ~8 seconds** (including 5 second initial wait)

3. **Ready State Display**:
   ```
    ▐▛███▜▌   Claude Code v2.0.8
   ▝▜█████▛▘  Sonnet 4.5 · Claude Pro
     ▘▘ ▝▝    /mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux

   ────────────────────────────────────────────────────────────────────────────────
   > Try "fix typecheck errors"
   ────────────────────────────────────────────────────────────────────────────────
     ? for shortcuts                                 Thinking off (tab to toggle)
   ```

### Prompt Patterns

1. **Input Prompt**: `>`
   - Always visible at the start of the input line
   - Appears even when processing (not a reliable ready indicator)

2. **Status Indicators**:
   - Bottom right: "Thinking off (tab to toggle)" when idle
   - Shows "Thinking" status changes during processing (needs confirmation)

### Command Injection Test

**Test Command**: "What is 2 + 2?"

**Initial Method (FAILED)**:
```bash
tmux send-keys -t claude-poc "What is 2 + 2?" Enter
```

**Result**: Command accepted but not submitted
- Text appeared in the interface
- Enter key treated as Shift+Enter (multi-line continuation)
- Command never submitted to Claude Code

**SOLUTION FOUND**: Send text and Enter as separate commands
```bash
# Send the text first
tmux send-keys -t claude-poc "What is 2 + 2?"
# Then send Enter separately to submit
tmux send-keys -t claude-poc Enter
```

**Result with Correct Method**: ✅ SUCCESS
- Command properly submitted
- Claude Code generates response
- Full interaction works as expected

## Key Findings

### ✅ What Works
1. **Tmux session creation**: Successfully creates detached session
2. **Claude Code startup**: Launches correctly in tmux
3. **Trust prompt automation**: Can be automated with `tmux send-keys Enter`
4. **Command injection**: ✅ **WORKING** - Text and Enter must be sent separately
5. **Response generation**: ✅ **WORKING** - Claude Code responds correctly when commands properly submitted
6. **Session control**: Can cancel operations with Ctrl+C
7. **Output capture**: `tmux capture-pane` reliably captures display
8. **Read-only monitoring**: Can attach with `-r` flag for observation without interference

### ⚠️ Critical Implementation Details
1. **Command submission**: Must send text and Enter as **separate** `tmux send-keys` commands
   - Single command with `Enter` parameter creates multi-line input
   - Two separate commands properly submits the query

### ❓ Unknown/To Investigate
1. ~~Why doesn't the tmux instance respond to queries?~~ **SOLVED** - Enter key must be sent separately
2. How to reliably detect when response is complete?
3. What's the best strategy for capturing streaming responses?
4. Can we detect errors vs successful responses programmatically?

## Timing Measurements

| Event | Time (seconds) |
|-------|----------------|
| Tmux session creation | < 1 |
| Trust prompt appearance | < 1 |
| Trust confirmation → Ready | ~3 |
| **Total startup** | **~8** |
| Command injection latency | < 0.1 |
| Output capture latency | < 0.1 |

## Next Steps

### Immediate Actions
1. **Investigate response issue**:
   - Check Claude Code logs in tmux session
   - Try attaching manually to observe behavior
   - Check environment variables
   - Verify API authentication in tmux context

2. **Alternative test approaches**:
   - Try simpler commands (e.g., "help", "?")
   - Test with file operations in the worktree
   - Attempt to trigger tool usage

3. **Documentation review**:
   - Check Claude Code docs for programmatic usage
   - Look for CLI flags or options for automation
   - Review tmux integration best practices

### Workarounds to Explore
1. Use expect script instead of tmux (Approach 2)
2. Try PTY-based control (Approach 3)
3. Investigate if Claude Code has a headless/API mode
4. Check if environment setup is needed in tmux context

## Configuration Recommendations

Based on findings, update `config.yaml`:

```yaml
claude:
  startup_timeout: 10  # Confirmed: 8 seconds observed
  response_timeout: 30  # TBD - no response observed yet
  prompt_pattern: ">"  # Confirmed but not reliable for ready detection
  trust_auto_confirm: true  # Can be automated

tmux:
  session_name: "claude-poc"
  capture_lines: 100
  startup_wait: 5  # Wait after session creation
  post_command_wait: 3  # Wait after sending command (needs tuning)
```

## Open Questions

1. **Does Claude Code support programmatic interaction via tmux?**
   - If yes, what's the correct method?
   - If no, which alternative approach should we use?

2. **Is the lack of response due to:**
   - Authentication/API key issues?
   - TTY detection preventing operation?
   - Missing environment variables?
   - Claude Code's security model blocking tmux interaction?

3. **Can we detect when Claude Code is actually ready vs just showing the prompt?**
   - Need to identify additional indicators
   - May require parsing status messages
   - Could involve timing-based heuristics
