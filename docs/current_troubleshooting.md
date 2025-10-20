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

## Next Steps

1. **Re-enable Smoke Test**  
   - Prepare to run `examples/run_orchestrated_discussion.py` with the simplified prompt (“Quick smoke test…”).  
   - Use the same wait-for-ready + response parsing approach; ensure updated controllers and config are copied to `/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux/`.  
   - Capture outputs (`logs/smoke-test.log`) and confirm both AIs exchange at least three coherent turns.

2. **Document & Clean Up**  
   - Keep `[debug]` logging for the first smoke rerun; if results are clean, remove or guard them with a verbosity flag.  
   - Summarise smoke-test findings back to `MessageBoard.md` and archive transcripts under `logs/`.

3. **Future Hardening (Optional)**  
   - Add a regression test around `OutputParser.extract_responses` for Claude/Gemini screen reader snippets.  
   - Consider a unit test or mocked harness for `run_counting_conversation.py` once we have stable prompts.

Keeping this file current ensures we can resume quickly in a new session. Prior commits touch `config.yaml`, `src/controllers/tmux_controller.py`, counting scripts, and documentation—copy the latest versions into the tmux worktree before running additional tests.
