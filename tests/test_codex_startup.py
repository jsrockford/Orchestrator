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
from src.utils.path_helpers import get_tmux_worktree_path

CONFIG_PATH = "config.yaml"
SESSION_NAME = "codex-startup-test"
WORKING_DIR = str(get_tmux_worktree_path())
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

    executable = codex_cfg.get("executable")
    if not executable:
        print(f"[error] No executable configured for '{CODEX_KEY}' in {CONFIG_PATH}")
        return 1

    raw_args = codex_cfg.get("executable_args", [])
    if isinstance(raw_args, str):
        raw_args = [raw_args]
    if not isinstance(raw_args, (list, tuple)):
        print(f"[error] Invalid executable_args for '{CODEX_KEY}': {type(raw_args)!r}")
        return 1

    controller = TmuxController(
        session_name=SESSION_NAME,
        executable=executable,
        working_dir=WORKING_DIR,
        ai_config=codex_cfg,
        executable_args=tuple(str(arg) for arg in raw_args),
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
