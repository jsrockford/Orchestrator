import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "orchestrator_control.sh"


pytestmark = pytest.mark.skipif(
    not SCRIPT.exists(),
    reason="orchestrator_control.sh not present in this worktree",
)


def test_cli_help_outputs_usage():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Usage: orchestrator_control.sh" in result.stdout


def test_history_command_without_file(tmp_path):
    env = os.environ.copy()
    env["ORCHESTRATOR_CONTROL_HISTORY"] = str(tmp_path / "history.log")
    result = subprocess.run(
        ["bash", str(SCRIPT), "history"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    assert "No history available yet" in result.stdout
