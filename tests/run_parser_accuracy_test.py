#!/usr/bin/env python3
"""
Parser Accuracy Harness

Exercise each tmux-backed AI controller with representative prompts and capture
both the raw pane transcript and the OutputParser's cleaned interpretation.
Artifacts are written to ``scratch/parser_accuracy/<ai>/`` for manual review.
"""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.controllers.tmux_controller import (
    SessionBackendError,
    SessionNotFoundError,
    TmuxController,
)
from src.utils.config_loader import get_config
from src.utils.output_parser import OutputParser
from src.utils.exceptions import CommandTimeout, SessionDead


AI_CHOICES: Tuple[str, ...] = ("claude", "gemini", "codex")
DEFAULT_OUTPUT_DIR = Path("scratch/parser_accuracy")


@dataclass(frozen=True)
class PromptScenario:
    """Prompt metadata for a single accuracy probe."""

    key: str
    prompt: str
    description: str


DEFAULT_PROMPTS: Tuple[PromptScenario, ...] = (
    PromptScenario(
        key="simple",
        prompt=(
            "In two sentences, explain why capturing both raw transcripts and cleaned parser "
            "output is useful when verifying an automation pipeline."
        ),
        description="Short, plain-language response grounded in general automation practice.",
    ),
    PromptScenario(
        key="longform",
        prompt=(
            "Provide a detailed checklist (at least eight bullet points) of best practices "
            "for testing command-line automation harnesses that interact with tmux sessions."
        ),
        description="Long structured response with bullet formatting and no repository context.",
    ),
    PromptScenario(
        key="code",
        prompt=(
            "Write a Python function `compare_parser_outputs(raw: str, parsed: str) -> dict` "
            "that compares two strings and returns counts of lines, characters, and "
            "a boolean flag for equality. Include doctest-style usage examples."
        ),
        description="Code-heavy response requiring preserved indentation.",
    ),
    PromptScenario(
        key="markdown",
        prompt=(
            "Create a markdown table with three rows comparing logging strategies, timeout "
            "policies, and retry handling for automation controllers. Add a brief paragraph "
            "interpreting the table."
        ),
        description="Markdown table plus narrative paragraph using general operational themes.",
    ),
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ais",
        nargs="+",
        metavar="AI",
        choices=AI_CHOICES,
        default=list(AI_CHOICES),
        help="Subset of controllers to exercise.",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=[scenario.key for scenario in DEFAULT_PROMPTS],
        help="Limit the run to specific prompt categories.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for captured artifacts.",
    )
    parser.add_argument(
        "--session",
        action="append",
        metavar="AI=SESSION",
        help="Override tmux session name for an AI (e.g., --session claude=claude-dev).",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch tmux session automatically if it is not already running.",
    )
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Kill any existing tmux session before starting fresh.",
    )
    parser.add_argument(
        "--working-dir",
        help="Working directory for launched CLI processes (defaults to config behaviour).",
    )
    parser.add_argument(
        "--bootstrap",
        help="Shell command to run before the executable when auto-starting sessions.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Override wait_for_ready timeout in seconds (defaults to config response_timeout).",
    )
    parser.add_argument(
        "--check-interval",
        type=float,
        help="Override wait_for_ready polling interval in seconds.",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        help="Limit the number of transcript lines saved per prompt.",
    )
    parser.add_argument(
        "--capture-delay",
        type=float,
        help="Extra seconds to wait after wait_for_ready() before capturing output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without sending prompts.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


def load_session_overrides(entries: Optional[Iterable[str]]) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if not entries:
        return overrides
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Invalid --session override '{entry}'. Expected format AI=SESSION.")
        ai, name = entry.split("=", 1)
        ai = ai.strip().lower()
        if ai not in AI_CHOICES:
            raise ValueError(f"Unknown AI '{ai}' in session override.")
        overrides[ai] = name.strip()
    return overrides


def slugify(text: str, max_length: int = 40) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in text)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip("-")
    return cleaned or "prompt"


def select_prompts(categories: Optional[Sequence[str]]) -> List[PromptScenario]:
    if not categories:
        return list(DEFAULT_PROMPTS)
    selected = [scenario for scenario in DEFAULT_PROMPTS if scenario.key in categories]
    if not selected:
        raise ValueError(f"No prompts matched categories {categories}")
    return selected


def build_controller(
    *,
    ai: str,
    session_name: str,
    executable: Optional[str],
    working_dir: Optional[str],
    auto_start: bool,
    kill_existing: bool,
    bootstrap: Optional[str],
    timeout_override: Optional[float],
    check_interval: Optional[float],
) -> TmuxController:
    config_loader = get_config()
    ai_section: Dict[str, object] = dict(config_loader.get_section(ai) or {})
    if not ai_section:
        raise ValueError(f"No configuration section found for '{ai}'.")

    executable_value = executable or ai_section.pop("executable", ai)
    exec_args_value = ai_section.pop("executable_args", [])
    if isinstance(exec_args_value, str):
        exec_args_value = shlex.split(exec_args_value)
    launch_executable = executable_value
    launch_args = list(exec_args_value)

    # Apply overrides for wait_for_ready tuning.
    if timeout_override is not None:
        ai_section["response_timeout"] = timeout_override
    if check_interval is not None:
        ai_section["ready_check_interval"] = check_interval

    ai_section.setdefault("pause_on_manual_clients", False)

    if bootstrap:
        quoted_executable = shlex.quote(executable_value)
        quoted_args = " ".join(shlex.quote(arg) for arg in launch_args)
        command_tail = f"{quoted_executable} {quoted_args}".strip()
        shell_command = f"{bootstrap} && {command_tail}" if command_tail else f"{bootstrap} && {quoted_executable}"
        launch_executable = "bash"
        launch_args = ["-lc", shell_command]

    controller = TmuxController(
        session_name=session_name,
        executable=launch_executable,
        working_dir=working_dir,
        ai_config=ai_section,
        executable_args=launch_args,
    )

    controller.reset_output_cache()

    if controller.session_exists():
        if kill_existing:
            if not controller.kill_session():
                raise SessionBackendError(f"Failed to kill existing session '{session_name}'.")
            time.sleep(1.0)
        else:
            controller.resume_automation(flush_pending=True)
            return controller

    if not auto_start:
        raise SessionNotFoundError(
            f"Session '{session_name}' not found for {ai}. "
            "Start it manually or pass --auto-start."
        )

    controller.start()
    controller.reset_output_cache()
    return controller


def compute_delta(previous: List[str], current: List[str], *, tail_limit: Optional[int]) -> List[str]:
    if previous and len(current) >= len(previous):
        limit = min(len(previous), len(current))
        prefix = 0
        while prefix < limit and previous[prefix] == current[prefix]:
            prefix += 1
        delta = current[prefix:]
    else:
        delta = current

    if tail_limit is not None and len(delta) > tail_limit:
        delta = delta[-tail_limit:]

    return delta


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, content: str) -> None:
    if content and not content.endswith("\n"):
        content = f"{content}\n"
    path.write_text(content, encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("parser_accuracy")

    try:
        session_overrides = load_session_overrides(args.session)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    prompts = select_prompts(args.categories)
    cfg = get_config()
    tmux_section = cfg.get_section("tmux") or {}
    capture_delay = (
        args.capture_delay if args.capture_delay is not None else float(tmux_section.get("capture_delay", 0.25))
    )
    tail_limit = args.tail_lines if args.tail_lines is not None else int(tmux_section.get("capture_lines", 500))

    if args.dry_run:
        logger.info("Dry run requested; no prompts will be sent.")
        logger.info("AIs: %s", ", ".join(args.ais))
        for scenario in prompts:
            logger.info("  - %s: %s", scenario.key, scenario.description)
        return 0

    output_root = ensure_directory(args.output_dir)
    parser = OutputParser()

    controllers: Dict[str, TmuxController] = {}
    pane_snapshots: Dict[str, List[str]] = {}
    per_ai_dirs: Dict[str, Path] = {}

    for ai in args.ais:
        session_key = f"{ai}_session"
        session_name = session_overrides.get(ai, tmux_section.get(session_key, ai))
        ai_config = cfg.get_section(ai) or {}
        executable = ai_config.get("executable", ai)
        working_dir = args.working_dir or ai_config.get("working_dir")
        try:
            controller = build_controller(
                ai=ai,
                session_name=session_name,
                executable=executable,
                working_dir=working_dir,
                auto_start=args.auto_start,
                kill_existing=args.kill_existing,
                bootstrap=args.bootstrap,
                timeout_override=args.timeout,
                check_interval=args.check_interval,
            )
        except (SessionNotFoundError, SessionBackendError) as exc:
            logger.error("Failed to prepare %s controller: %s", ai, exc)
            continue

        controllers[ai] = controller
        per_ai_dirs[ai] = ensure_directory(output_root / ai)
        pane_snapshot = controller.capture_scrollback()
        pane_snapshots[ai] = pane_snapshot.splitlines()
        controller.resume_automation(flush_pending=False)
        logger.info("Prepared controller for %s (session=%s).", ai, session_name)

    if not controllers:
        logger.error("No controllers available; aborting.")
        return 1

    summary_rows: List[Dict[str, object]] = []

    for ai, controller in controllers.items():
        ai_dir = per_ai_dirs[ai]
        previous_lines = pane_snapshots[ai]
        logger.info("Running %d prompts against %s.", len(prompts), ai)

        for index, scenario in enumerate(prompts, start=1):
            prompt_slug = slugify(f"{index:02d}-{scenario.key}")
            raw_path = ai_dir / f"{prompt_slug}.raw.txt"
            parsed_path = ai_dir / f"{prompt_slug}.parsed.txt"
            metadata_path = ai_dir / f"{prompt_slug}.meta.json"

            controller.reset_output_cache()
            controller.resume_automation(flush_pending=False)

            start_time = time.perf_counter()
            queued = False
            ready = False
            error: Optional[str] = None
            raw_delta: List[str] = []

            logger.info("[%s] Prompt %s: %s", ai, scenario.key, scenario.description)
            try:
                sent = controller.send_command(scenario.prompt, submit=True)
                queued = not sent
                if queued:
                    logger.debug("[%s] Command queued; resuming automation.", ai)
                    controller.resume_automation(flush_pending=True)

                ready = controller.wait_for_ready(timeout=args.timeout, check_interval=args.check_interval)
                if not ready:
                    error = "wait_for_ready returned False"

                time.sleep(capture_delay)

                pane_output = controller.capture_scrollback()
                current_lines = pane_output.splitlines()
                raw_delta = compute_delta(previous_lines, current_lines, tail_limit=tail_limit)
                if not raw_delta:
                    fallback = controller.get_last_output(tail_lines=tail_limit)
                    if fallback:
                        raw_delta = fallback.splitlines()
                previous_lines = current_lines
            except (SessionBackendError, SessionNotFoundError, SessionDead, CommandTimeout) as exc:
                error = str(exc)
                logger.error("[%s] Error while processing prompt '%s': %s", ai, scenario.key, exc)
            duration = time.perf_counter() - start_time

            raw_text = "\n".join(raw_delta)
            parsed_text = parser.clean_output(raw_text, strip_trailing_prompts=True)
            response_pairs = parser.extract_responses(raw_text)

            write_text(raw_path, raw_text)
            write_text(parsed_path, parsed_text)
            metadata = {
                "ai": ai,
                "prompt_key": scenario.key,
                "prompt": scenario.prompt,
                "description": scenario.description,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "duration_seconds": duration,
                "queued": queued,
                "ready": ready,
                "error": error,
                "raw_lines": len(raw_delta),
                "parsed_lines": len(parsed_text.splitlines()) if parsed_text else 0,
                "raw_path": str(raw_path),
                "parsed_path": str(parsed_path),
                "response_pairs": response_pairs,
            }
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            summary_rows.append(
                {
                    "ai": ai,
                    "prompt": scenario.key,
                    "duration": duration,
                    "raw_lines": len(raw_delta),
                    "parsed_lines": metadata["parsed_lines"],
                    "error": error,
                    "raw_path": raw_path,
                    "parsed_path": parsed_path,
                }
            )

        pane_snapshots[ai] = previous_lines

    logger.info("Run complete. Artifacts stored in %s", output_root)
    logger.info("Summary:")
    for row in summary_rows:
        status = "ok" if row["error"] is None else "error"
        logger.info(
            "  %s | %s | %s | raw=%d lines parsed=%d lines | %s",
            row["ai"],
            row["prompt"],
            f"{row['duration']:.2f}s",
            row["raw_lines"],
            row["parsed_lines"],
            status,
        )

    has_error = any(row["error"] is not None for row in summary_rows)
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
