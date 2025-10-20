# Gemini Input & Dual-AI Orchestration Troubleshooting Summary

**Context (October 17, 2025)**  
We stabilised tmux-based orchestration between Claude Code and Gemini CLI by combining screen reader friendly launches with reliable prompt delivery and delayed capture. Both CLIs now echo structured responses that the orchestrator can parse deterministically.

## Key Findings & Fixes

- **Screen Reader Launch Defaults**  
  - Gemini must start with `--yolo --screenReader` to avoid repaint-heavy UI.  
  - `config.yaml` and helper scripts default to those flags; copy them into the tmux worktree before each run.

- **Reliable Prompt Submission**  
  - `TmuxController` uses literal chunk sends (`send-keys -l -- …`) to preserve punctuation.  
  - Gemini keeps `submit_key: "C-m"` and a fallback literal `Enter`, with `text_enter_delay = 0.5` s so the buffer settles before submission.  
  - Added `post_text_delay = 0.5` s so tmux waits briefly after pasting before pressing Enter; controller now logs tmux return codes for both submit attempts.

- **Ready & Response Capture**  
  - Ready indicators include `"Type your message or @path/to/file"` and `"Model:"`, matching screen reader output.  
  - After each dispatch we now call `controllers[speaker].wait_for_ready()` before capturing output.  
  - Output is parsed via `OutputParser.extract_responses`, ensuring we read text following the `●/✦/Model:` markers instead of transient status lines.

- **Structured Prompting**  
  - `examples/run_counting_conversation.py` instructs each AI to respond with exactly two lines (`Line 1: current number`, `Line 2: instruction for the next speaker`) and explicitly forbids tool usage.  
  - This eliminates Gemini’s previous tendency to open files mid-conversation.

- **Diagnostic Harnesses**  
  - `test_gemini_input.py` verifies single prompt delivery.  
  - `test_counting_smoke.py` exercises alternating controller sends.  
  - `examples/run_counting_conversation.py` now produces clean transcripts (`scratch/counting_conversation.log`) showing correct 1–6 exchange.

## Current Status (Post-Fix)

1. **Prompt Delivery** – Both controllers send entire prompts without truncation; Gemini properly receives apostrophes and punctuation.
2. **Counting Harness** – The orchestrated script logs the expected sequence (`1`, `Model: 2`, `3`, `Model: 4`, …) with parsed responses recorded in `scratch/counting_conversation.log`.
3. **Observation Ready** – With `pause_on_manual_clients = false`, we can attach in read-only mode without halting automation, making live verification safe.
4. **✅ Smoke Test PASSING** – Fixed case-sensitivity bug in orchestration script; both AIs now complete multi-turn discussions successfully.

## Smoke Test Resolution (October 20, 2025)

**Problem:**
`examples/run_orchestrated_discussion.py` was not loading Gemini config correctly. Even though `config.yaml` had correct settings (`submit_key: "C-m"`, `text_enter_delay: 0.5`, `post_text_delay: 0.5`), the controller used defaults (`Enter`, `0.1s`, `0.0s`), causing prompts to submit before Gemini's input buffer fully received all text chunks.

**Root Cause:**
Case-sensitivity mismatch in `build_controller()` function:
- Script passed `name="Claude"` and `name="Gemini"` (capitalized) to `build_controller()`
- Line 38: `get_config().get_section(name)` looked for capitalized section names
- `config.yaml` has lowercase sections: `claude:` and `gemini:`
- Config lookup returned `None`, resulting in empty config dict
- Safeguard on line 45 (`if name == "gemini"`) also failed due to case mismatch

**Solution Applied:**
Modified `examples/run_orchestrated_discussion.py`:
```python
# Line 38: Force lowercase for config lookup
base_config = dict(get_config().get_section(name.lower()) or {})

# Line 45: Force lowercase for safeguard check
if name.lower() == "gemini":
    ai_config["submit_key"] = "C-m"
    ai_config["text_enter_delay"] = 0.5
    ai_config["post_text_delay"] = 0.5
```

**Verification Results:**
- ✅ Config correctly loaded: `C-m`, `0.5s`, `0.5s` delays applied
- ✅ Controller logs confirm: `Sleeping 0.500s before sending submit key 'C-m'`
- ✅ Gemini receives complete prompts with apostrophes and punctuation
- ✅ All 6 turns complete successfully (3 Claude, 3 Gemini alternating)
- ✅ Gemini responses: `Model: Hello from gemini — message received.` (consistent across all turns)

See `scratch/SmokeTestTerminal.txt` (lines 11-18 for config loading, lines 110-112, 156-158, 202-204 for successful responses) and `scratch/smoke-test.log` for full transcript.

## Next Steps

1. **Advanced Orchestration Testing**
   - Test more complex multi-turn discussions with code analysis, file operations, etc.
   - Verify conversation context preservation across longer sessions
   - Test error recovery and timeout handling in orchestrated scenarios

2. **Documentation & Cleanup**
   - Update README.md with smoke test success criteria
   - Archive successful test transcripts under `logs/`
   - Document the case-sensitivity fix for future reference

3. **Future Hardening**
   - Add regression test for case-insensitive config loading
   - Add integration test for `OutputParser.extract_responses` with both CLI formats
   - Consider adding config validation on startup to catch similar issues early

Keeping this file current ensures we can resume quickly in a new session. All core functionality is now working: tmux session management, prompt delivery, response capture, and multi-AI orchestration.
