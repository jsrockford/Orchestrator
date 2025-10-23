# Output End Marker Problem - Troubleshooting Document

**Date:** 2025-10-22
**Status:** ACTIVE INVESTIGATION
**Phase:** 6.1 - Codex Integration & N-Agent Orchestration
**Critical Blocker:** Premature turn-passing in multi-agent discussions

---

## Problem Statement

The orchestration system is passing turns between AI agents BEFORE they finish responding, resulting in incomplete responses and "chaos" where multiple AIs process simultaneously. This bug affects ALL orchestrated discussions (2-agent and 3-agent), though it's most visible in 3-agent tests.

### Observable Symptoms
- Turns pass after 30-60 seconds even when AI is still generating output
- Responses get truncated mid-thought
- Status indicators like "Worked for 1m 01s" appear, but turn passes before completion
- Multiple AIs sometimes process simultaneously instead of turn-based sequencing

---

## Technical Background

### System Architecture

**Orchestration Flow:**
1. `ConversationManager.facilitate_discussion()` manages turn-taking
2. For each turn, calls `orchestrator.dispatch_command(speaker, prompt)`
3. After dispatch, calls `_read_last_output(speaker)` to capture response
4. `_read_last_output()` calls `controller.wait_for_ready()` with NO parameters (line 328)
5. `wait_for_ready()` determines when AI has finished responding

**Critical Files:**
- `src/orchestrator/conversation_manager.py` - Turn-taking logic
- `src/controllers/tmux_controller.py` - Response completion detection
- `config.yaml` - Marker and indicator configuration

### Current Detection Mechanism

`TmuxController.wait_for_ready()` (lines 933-984) uses three checks:

1. **Loading Indicator Detection** (lines 963-971)
   - Scans last 6 lines for patterns like "Working for...", "⠦", "Planning integration"
   - If found, resets stabilization counter and continues waiting

2. **Output Stabilization** (lines 974-979)
   - Waits for buffer to stop changing (no new content between checks)
   - Requires N consecutive stable checks (configured per AI)

3. **Response Readiness Check** (line 976)
   - Calls `_is_response_ready(tail_lines)`
   - Must return True before considering AI ready

### The `_is_response_ready()` Method (lines 903-923)

```python
def _is_response_ready(self, tail_lines: Sequence[str]) -> bool:
    if not tail_lines:
        return False

    tail_text = "\n".join(tail_lines)

    # Check if completion markers present (e.g., "› ")
    markers_present = (
        not self.response_complete_markers
        or self._contains_any(tail_text, self.response_complete_markers)
    )
    # Check if ready indicators present (e.g., "Type your message")
    indicators_present = (
        not self.ready_indicators
        or self._contains_any(tail_text, self.ready_indicators)
    )

    # Return True ONLY if both are satisfied (or not configured)
    if self.response_complete_markers and not markers_present:
        return False
    if self.ready_indicators and not indicators_present:
        return False

    return True
```

---

## Root Cause Analysis

### The Core Bug

**Problem:** `_is_response_ready()` checks if markers exist ANYWHERE in `tail_lines`, not specifically at the END where a new prompt appears.

**Why This Fails:**

1. AI receives command: `"What is our current project focus?"`
2. Tmux echoes command with prompt: `"› What is our current project focus?"`
3. AI starts processing and generating output (150+ lines)
4. `wait_for_ready()` captures output and extracts `tail_lines`
5. `_is_response_ready()` searches ALL of `tail_lines` for `"› "`
6. Finds `"› "` from the COMMAND ECHO (not the new prompt)
7. Returns True prematurely, even though AI is still generating response

**Visual Representation:**

```
[Buffer contents - 100 lines captured]
Line 1:  › What is our current project focus?    <-- OLD PROMPT (command echo)
Line 2:  • Exploring codebase...
Line 3:  └ Reading files...
...
Line 85: ─ Worked for 51s ─────────────
Line 86: • Now analyzing...              <-- AI STILL WORKING
Line 87: - Plan: Step 1...
...
Line 100: [Response continues...]

_is_response_ready() searches lines 1-100 for "› "
→ FOUND on line 1 (the echo)
→ Returns True ✓
→ Turn passes ✗ (AI hasn't finished!)
```

**What Should Happen:**

```
[Buffer contents after AI finishes]
Line 1:  • Analyzing complete
Line 2:  - Recommendations: ...
Line 3:
Line 4:  Next steps:
Line 5:  1. Implement fix
Line 6:  2. Run tests
Line 7:
Line 8:  › [Cursor here - NEW PROMPT]    <-- ACTUAL COMPLETION MARKER

Check ONLY last 5 lines (4-8) for "› "
→ FOUND on line 8 (the new prompt)
→ Returns True ✓
→ Turn passes ✓ (AI has finished!)
```

---

## Attempted Fixes & Results

### Fix Attempt 1: Add Response Markers (Codex)
**Date:** 2025-10-22 (First iteration)
**Changes:**
- Added `response_complete_markers` to config.yaml for each AI
- Added `loading_indicators` to config.yaml
- Modified `wait_for_ready()` to check for markers

**Result:** FAILED - Still premature turn-passing

**Why It Failed:** Checked markers anywhere in buffer, not at the end

---

### Fix Attempt 2: Check Last 5 Lines Only (Claude + Gemini recommended)
**Date:** 2025-10-22 (Second iteration)
**Changes:**
- Modified `_is_response_ready()` to check only last 5 lines for markers
- Increased `tmux.capture_lines` from 100 to 500 in config.yaml

**Result:** FAILED (Don's latest report)

**Why It Failed:** [TO BE DIAGNOSED]

---

## Current Configuration

### config.yaml Markers (After Fix Attempt 2)

```yaml
claude:
  response_complete_markers:
    - "› "
  loading_indicators:
    - "⎿"
    - "Running…"
    - "Waiting…"
    - "Working…"

gemini:
  response_complete_markers:
    - "› "
    - "Type your message or @path/to/file"
  loading_indicators:
    - "⠦"
    - "⠼"
    - "Enhancing..."
    - "Counting electrons..."

codex:
  response_complete_markers:
    - "› "
    - "context left"
  loading_indicators:
    - "Planning integration"
    - "Working for"
    - "◦"

tmux:
  capture_lines: 500  # Increased from 100
```

---

## Test Procedure

### Standard 3-Agent Test

**Command:**
```bash
PYTHONPATH=. python3 examples/run_three_agent_discussion.py \
  --mode tmux \
  --auto-start \
  --gemini-startup-timeout 60 \
  --log-file logs/three_agent_discussion.log \
  "Codex integration check-in"
```

**Expected Behavior:**
- Turn 0: Gemini receives prompt, generates FULL response, turn passes when done
- Turn 1: Codex receives prompt, generates FULL response, turn passes when done
- Turn 2: Claude receives prompt, generates FULL response, turn passes when done
- Repeat for max_turns

**Actual Behavior (Current):**
- Turns pass after 30-60 seconds regardless of completion
- Responses truncated mid-generation
- Status shows "Worked for 1m 01s" but turn already passed

### Test Outputs

**Log Files:**
- `scratch/TerminalOutput.txt` - Timing and high-level flow
- `scratch/three_agent_discussion.log` - Full conversation transcript with prompts/responses

**Key Metrics to Check:**
- Time between command dispatch and next turn
- Presence of completion markers in captured responses
- Whether responses appear complete or truncated

---

## Next Steps (Don's Recommendation)

### Fallback Strategy: Test One AI at a Time

**Goal:** Determine correct completion detection method for EACH AI individually before combining them.

**Approach:**

1. **Create single-AI test script** (similar to `run_controller_probe.py`)
2. **Test Claude alone:**
   - Send command
   - Manually observe when response completes
   - Note exact buffer contents at completion
   - Identify reliable end-of-response marker
   - Tune `response_complete_markers` and `loading_indicators`

3. **Test Gemini alone:**
   - Same process as Claude
   - Document Gemini-specific markers

4. **Test Codex alone:**
   - Same process as Codex
   - Document Codex-specific markers

5. **Validate each AI individually** until `wait_for_ready()` works reliably

6. **Then test 2-agent combinations:**
   - Claude + Gemini
   - Claude + Codex
   - Gemini + Codex

7. **Finally test 3-agent** once 2-agent is stable

---

## Debugging Checklist

When investigating a failed test, check:

### 1. Timing Analysis
- [ ] How long between command dispatch and next turn?
- [ ] Does this match AI's "Worked for Xs" status?
- [ ] Is timing consistent or variable across turns?

### 2. Buffer Capture
- [ ] What are the LAST 10 lines of captured output?
- [ ] Is the completion marker (`"› "`) present?
- [ ] If yes, is it at the END or in the MIDDLE?
- [ ] Is the output truncated mid-sentence?

### 3. Marker Configuration
- [ ] Are `response_complete_markers` correct for this AI?
- [ ] Are `loading_indicators` triggering appropriately?
- [ ] Do markers appear in actual output at completion time?

### 4. Code Path Verification
- [ ] Is `_is_response_ready()` being called?
- [ ] What does it return (check logs with DEBUG level)?
- [ ] Is `capture_lines` large enough?

### 5. AI-Specific Behavior
- [ ] Does this AI show consistent prompt patterns?
- [ ] Are there intermediate prompts during processing?
- [ ] Does output include unexpected markers?

---

## Key Insights from Team Discussion

### Claude's Analysis
- Both 2-agent and 3-agent tests use IDENTICAL code paths through `ConversationManager`
- Bug existed since multi-turn discussions were implemented
- 2-agent tests appeared to work due to luck (faster responses)
- 3-agent test exposed the bug due to longer, more complex responses
- Root cause is checking markers anywhere in buffer instead of at the end

### Gemini's Analysis
- This is a **state machine problem**: system incorrectly transitions to "Ready" state
- Need deterministic "new prompt appeared at END" detection, not heuristic "marker exists somewhere"
- This is exactly what production hardening phase is designed to catch
- Fix must be robust before proceeding to other features

### Codex's Implementation
- Added marker-based detection (good architecture)
- Config-driven approach allows per-AI customization
- But marker checking logic needs refinement

---

## Technical Details for Resume

### Files to Review
1. `src/controllers/tmux_controller.py`
   - Lines 933-984: `wait_for_ready()` implementation
   - Lines 903-923: `_is_response_ready()` helper

2. `src/orchestrator/conversation_manager.py`
   - Line 328: Where `wait_for_ready()` is called (with NO parameters)
   - Lines 92-174: `facilitate_discussion()` turn-taking logic

3. `config.yaml`
   - Lines 27-33: Claude markers
   - Lines 63-70: Gemini markers
   - Lines 100-106: Codex markers
   - Line 121: `capture_lines` setting

### Test Files
- `examples/run_three_agent_discussion.py` - Multi-agent test script
- `scratch/TerminalOutput.txt` - Latest test timing data
- `scratch/three_agent_discussion.log` - Latest test transcript

---

## Questions to Answer

### Primary Question
**Why did Fix Attempt 2 fail when we specifically checked only the last 5 lines?**

Possible reasons:
1. The fix wasn't actually deployed (check git diff)
2. The last 5 lines don't contain the new prompt (buffer timing issue)
3. The markers are wrong for these AIs (need actual observation)
4. There's a different race condition we haven't identified
5. `_tail_lines()` isn't working as expected

### Investigation Path
1. **Verify the fix was deployed:** Check `_is_response_ready()` implementation in actual running code
2. **Add debug logging:** Print what last 5 lines contain when check happens
3. **Manual observation:** Watch tmux session during test to see actual completion behavior
4. **Single-AI testing:** Isolate each AI to determine correct markers empirically

---

## Success Criteria

### Definition of "Fixed"
- 3-agent discussion completes with ALL responses fully captured
- No premature turn-passing
- Timing logs show appropriate wait times (variable based on response length)
- Responses include complete thoughts, recommendations, and natural conclusions
- Status indicators like "Worked for Xs" align with actual turn timing

### How to Validate
1. Run 3-agent test with 6-10 turns
2. Manually review ALL responses in log file
3. Verify each response has natural conclusion (not truncated)
4. Check timing: turns should pass quickly for short responses, slowly for long ones
5. Confirm no "chaos" (multiple AIs processing simultaneously)

---

## Contact Points

**Latest Test Results:**
- See `scratch/TerminalOutput.txt` and `scratch/three_agent_discussion.log`

**Latest Code:**
- Branch: `development`
- Recent commits show marker-based detection implementation

**MessageBoard Discussion:**
- See `MessageBoard.md` lines 1186-1378 for full team discussion
- Don's direction at line 1377: Test one AI at a time if next attempt fails

---

## Notes

- This bug is a **critical blocker** for Phase 6.1 completion
- Cannot proceed to Phase 6.B (Production Hardening) until resolved
- Web UI development (future phase) depends on stable orchestration
- The fix is theoretically sound but practical implementation has failed twice
- Empirical observation of actual AI behavior may be required

**Last Updated:** 2025-10-22
**Next Action:** Single-AI isolation testing to determine correct markers per AI
