# Repository Guidelines

## Project Structure & Module Organization
The orchestration runtime lives in `src/`, with session-aware controllers in `src/controllers/` (`claude_controller.py`, `gemini_controller.py`, `tmux_controller.py`) and shared helpers in `src/utils/` covering logging, retries, auto-restart logic, and output parsing. Top-level pytest suites such as `test_controller.py`, `test_dual_ai.py`, and `test_output_parser.py` exercise end-to-end flows; use them as templates when adding scenarios. Runtime configuration (timeouts, executable names, tmux session policy) sits in `config.yaml`, and execution logs stream to `logs/` for post-run diagnostics.

## Build, Test, and Development Commands
Create or activate a virtual environment before installing dependencies (`python -m venv venv && source venv/bin/activate`). Install runtime packages with:
```bash
pip install -r requirements.txt
```
Run the full regression suite via `python -m pytest`, or narrow the scope with commands like `python -m pytest test_controller_auto.py -k "wait_for_ready"` when debugging a specific behavior.

## Coding Style & Naming Conventions
Follow PEP 8 defaults: four-space indentation, snake_case functions, CapWords classes, and docstrings on controller entrypoints that interact with tmux panes or external CLIs. Prefer small helpers in `src/utils/` instead of inlining subprocess or retry logic, and emit logs through `get_logger` with session name and timeout context. No formatter is enforced, so keep manual diffs tidy.

## Testing Guidelines
Add integration tests at the repository root (`test_*.py`) for cross-component flows, and colocate fine-grained helpers beside the code they exercise. Name tests after the scenario and expected outcome (e.g., `test_wait_for_ready_times_out_cleanly`). Every change needs success-path and failure-path coverage, plus a regression test for fixes. Mock external processes so suites stay deterministic, and run `python -m pytest` before every review.

## Collaboration & Communication Protocol
Use `CodexConcerns.md` as the shared message board for multi-agent coordination. Preface every contribution with your agent name (e.g., `Codex:`, `Claude:`, `Gemini:`), keep replies in a single paragraph unless bullets add clarity, and terminate each entry with `-------` on its own line. Record key technical findings, action items, and plan updates there so other agents can catch up asynchronously next session.

## Commit & Pull Request Guidelines
Existing history uses short, imperative summaries (`Enhance startup detection with loading indicator checks`); follow that format and keep subjects under ~70 characters. Squash incidental noise so each commit bundles one logical change and include body bullets when tweaking configuration defaults. Pull requests should link the motivating task or spec section, describe observable impacts (timeouts, retries, logging), and list verification steps such as `python -m pytest` or a tmux smoke test.

## Configuration Tips
Treat `config.yaml` as the source of truth for controller behavior—adjust timeouts, restart policies, and session names there rather than hard-coding values. After updates, rerun `python -m pytest test_config.py` and spot-check the affected controller to confirm the new thresholds behave as expected.
