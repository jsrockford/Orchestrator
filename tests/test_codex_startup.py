#!/usr/bin/env python3
"""
Manual validation script to confirm Codex startup detection works.

Launches the Codex controller, waits for the configured ready indicators,
prints diagnostic output, and cleans up the tmux session. Mirrors the
existing Claude/Gemini startup smoke tests so we can quickly sanity check
Codex when tweaking config.yaml.
"""

import sys
import time
import yaml

from src.controllers.tmux_controller import TmuxController

CONFIG_PATH = "config.yaml"
SESSION_NAME = "codex-startup-test"
WORKING_DIR = "/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux"
CODEX_KEY = "codex"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    config = load_config()
    codex_cfg = config.get(CODEX_KEY)
    if not codex_cfg:
        print(f"[error] '{CODEX_KEY}' configuration missing in {CONFIG_PATH}")
        return 1

    controller = TmuxController(
        session_name=SESSION_NAME,
        executable=codex_cfg.get("executable", "codex"),
        working_dir=WORKING_DIR,
        ai_config=codex_cfg,
    )

    if controller.session_exists():
        print("[info] Existing session detected; killing before retry…")
        controller.kill_session()
        time.sleep(1.0)

    print("[info] Starting Codex session for startup detection probe…")
    try:
        controller.start_session()
    except Exception as exc:  # noqa: BLE001
        print(f"[error] Startup failed: {exc}")
        if controller.session_exists():
            controller.kill_session()
        return 1

    print("[ok] Codex reported ready.")

    output = controller.capture_output()
    print(f"[debug] Captured {len(output)} characters from pane.")

    markers = codex_cfg.get("ready_indicators", [])
    if markers:
        print("[debug] Ready indicators configured:")
        for marker in markers:
            found = marker in output
            status = "✓" if found else "✗"
            print(f"   {status} {marker}")
    else:
        print("[warn] No ready indicators configured for Codex.")

    controller.kill_session()
    print("[info] Session cleaned up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
