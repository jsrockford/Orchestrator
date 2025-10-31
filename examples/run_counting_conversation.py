#!/usr/bin/env python3
"""
Let Claude, Gemini, and Codex count upward together using the orchestrator.

The first AI starts at 1, the next replies with 2, and so on until the target count.
The script records the transcript and verifies that every number appears in order.
"""

from __future__ import annotations

import argparse
import re
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional

from src.controllers.tmux_controller import SessionBackendError, SessionNotFoundError, TmuxController
from src.orchestrator import ContextManager, DevelopmentTeamOrchestrator, MessageRouter
from src.orchestrator.conversation_manager import ConversationManager
from src.utils.config_loader import get_config
from src.utils.output_parser import OutputParser


def build_controller(
    *,
    name: str,
    session_name: str,
    executable: str,
    working_dir: Optional[str],
    auto_start: bool,
    startup_timeout: int,
    init_wait: Optional[float],
    kill_existing: bool,
) -> TmuxController:
    cfg = get_config()
    base = dict(cfg.get_section(name.lower()) or {})
    base["startup_timeout"] = startup_timeout
    if init_wait is not None:
        base["init_wait"] = init_wait

    parts = executable.split()
    controller = TmuxController(
        session_name=session_name,
        executable=parts[0],
        working_dir=working_dir,
        ai_config=base,
        executable_args=tuple(parts[1:]),
    )
    controller.reset_output_cache()

    if kill_existing and controller.session_exists():
        controller.kill()

    if controller.session_exists():
        controller.resume_automation(flush_pending=True)
        return controller

    if not auto_start:
        raise SessionNotFoundError(
            f"Session '{session_name}' not found for {name}. Start manually or use --auto-start."
        )

    controller.start()
    controller.wait_for_ready()
    return controller


def parse_args(argv: list[str]) -> argparse.Namespace:
    cfg = get_config()
    tmux_cfg = cfg.get_section("tmux")

    parser = argparse.ArgumentParser(description="Have Claude, Gemini, and Codex count together.")

    def default_command(agent: str) -> str:
        try:
            return cfg.get_executable_command(agent)
        except (KeyError, TypeError) as exc:
            parser.error(
                f"Executable for '{agent}' is not configured correctly in config.yaml: {exc}"
            )

    claude_default = default_command("claude")
    gemini_default = default_command("gemini")
    codex_default = default_command("codex")
    parser.add_argument("--count-to", type=int, default=20, help="Highest number to reach (default 20).")
    parser.add_argument("--auto-start", action="store_true", help="Launch sessions automatically if needed.")
    parser.add_argument("--kill-existing", action="store_true", help="Kill sessions before starting.")
    parser.add_argument("--claude-session", default=tmux_cfg.get("claude_session", "claude"))
    parser.add_argument("--gemini-session", default=tmux_cfg.get("gemini_session", "gemini"))
    parser.add_argument(
        "--claude-executable",
        default=claude_default,
        help=f"Command to launch Claude (default: '{claude_default}').",
    )
    parser.add_argument(
        "--gemini-executable",
        default=gemini_default,
        help=f"Command to launch Gemini (default: '{gemini_default}').",
    )
    parser.add_argument("--claude-startup-timeout", type=int, default=20)
    parser.add_argument("--gemini-startup-timeout", type=int, default=60)
    parser.add_argument("--claude-init-wait", type=float, default=None)
    parser.add_argument("--gemini-init-wait", type=float, default=None)
    parser.add_argument("--claude-cwd", default=None)
    parser.add_argument("--gemini-cwd", default=None)
    parser.add_argument("--codex-session", default=tmux_cfg.get("codex_session", "codex"))
    parser.add_argument(
        "--codex-executable",
        default=codex_default,
        help=f"Command to launch Codex (default: '{codex_default}').",
    )
    parser.add_argument("--codex-startup-timeout", type=int, default=20)
    parser.add_argument("--codex-init-wait", type=float, default=None)
    parser.add_argument("--codex-cwd", default=None)
    parser.add_argument("--log-file", default=None, help="Optional path to write the transcript.")
    parser.add_argument(
        "--history-size",
        type=int,
        default=10,
        help="How many turns to keep in context (default 10).",
    )
    parser.add_argument(
        "--turn-delay",
        type=float,
        default=1.0,
        help="Seconds to pause before dispatching each prompt (default 1.0).",
    )
    parser.add_argument(
        "--initial-delay",
        type=float,
        default=2.0,
        help="Seconds to wait after startup before starting the count (default 2.0).",
    )
    parser.add_argument(
        "--response-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for each AI response before giving up (default 30s).",
    )
    return parser.parse_args(argv)


def capture_scrollback_lines(controller: TmuxController) -> List[str]:
    try:
        snapshot = controller.capture_scrollback()
    except (SessionBackendError, SessionNotFoundError):
        return []
    return snapshot.splitlines()


def compute_delta(previous: List[str], current: List[str], tail_limit: int) -> List[str]:
    if previous and len(current) >= len(previous):
        limit = min(len(previous), len(current))
        prefix = 0
        while prefix < limit and previous[prefix] == current[prefix]:
            prefix += 1
        delta = current[prefix:]
    else:
        delta = current

    if tail_limit and len(delta) > tail_limit:
        delta = delta[-tail_limit:]
    return delta


def build_prompt(number: int, speaker: str, next_speaker: str) -> str:
    return (
        f"You are counting upward with {next_speaker}. Respond with ONLY the number {number}."
        f" Then instruct {next_speaker} to add 1 and reply with the next number."
        " Do not add extra commentary."
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    transcript_path = Path(args.log_file) if args.log_file else None
    parser = OutputParser()

    try:
        claude = build_controller(
            name="Claude",
            session_name=args.claude_session,
            executable=args.claude_executable,
            working_dir=args.claude_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.claude_startup_timeout,
            init_wait=args.claude_init_wait,
            kill_existing=args.kill_existing,
        )
        gemini = build_controller(
            name="Gemini",
            session_name=args.gemini_session,
            executable=args.gemini_executable,
            working_dir=args.gemini_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.gemini_startup_timeout,
            init_wait=args.gemini_init_wait,
            kill_existing=args.kill_existing,
        )
        codex = build_controller(
            name="Codex",
            session_name=args.codex_session,
            executable=args.codex_executable,
            working_dir=args.codex_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.codex_startup_timeout,
            init_wait=args.codex_init_wait,
            kill_existing=args.kill_existing,
        )
    except (SessionBackendError, SessionNotFoundError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    controllers: Dict[str, TmuxController] = {"claude": claude, "gemini": gemini, "codex": codex}
    orchestrator = DevelopmentTeamOrchestrator(controllers)
    context_manager = ContextManager(history_size=args.history_size)
    router = MessageRouter(["claude", "gemini", "codex"], context_manager=context_manager)
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini", "codex"],
        context_manager=context_manager,
        message_router=router,
        max_history=args.history_size,
    )

    conversation = []
    if args.initial_delay > 0:
        print(f"[info] Waiting {args.initial_delay:.1f}s before starting the count...")
        time.sleep(args.initial_delay)

    turn_delay = max(0.0, args.turn_delay)
    next_number = 1
    current_speaker_index = 0  # 0 -> claude, 1 -> gemini
    transcript_lines: list[str] = []

    while next_number <= args.count_to:
        speaker = manager.participants[current_speaker_index]
        next_speaker = manager.participants[(current_speaker_index + 1) % len(manager.participants)]
        next_target = next_number + 1
        prompt_lines = [
            f"Current number: {next_number}",
            f"Reply using exactly two lines:",
            f"Line 1: {next_number}",
            f"Line 2: Next speaker ({next_speaker}) should reply with {next_target}.",
            "Do not open files, run commands, or use tools. No additional commentary or formatting.",
        ]
        prompt = "\n".join(prompt_lines)

        if turn_delay:
            time.sleep(turn_delay)

        controller = controllers[speaker]
        before_lines = capture_scrollback_lines(controller)
        dispatch = orchestrator.dispatch_command(speaker, prompt)
        controller.wait_for_ready(timeout=max(int(args.response_timeout), 1))
        after_lines = capture_scrollback_lines(controller)
        delta_lines = compute_delta(before_lines, after_lines, tail_limit=300)
        if delta_lines:
            raw_output = "\n".join(delta_lines)
        else:
            fallback = controller.get_last_output(tail_lines=300)
            raw_output = fallback or ""

        cleaned_output = parser.clean_output(raw_output, strip_trailing_prompts=True)
        pairs = parser.extract_responses(raw_output) or parser.extract_responses(cleaned_output)
        response = pairs[-1]["response"].strip() if pairs else cleaned_output.strip() or raw_output.strip()
        reported_number: Optional[int] = None
        if response:
            numbers = re.findall(r"\d+", response)
            if numbers:
                reported_number = int(numbers[0])

        turn_record = {
            "turn": len(conversation),
            "speaker": speaker,
            "prompt": prompt,
            "response": response,
            "metadata": dispatch,
        }
        conversation.append(turn_record)
        transcript_lines.append(f"{next_number}: {speaker}: {response}")

        print(f"[debug] Raw output from {speaker}:\n{raw_output}\n---")
        if cleaned_output:
            print(f"[debug] Cleaned output from {speaker}:\n{cleaned_output}\n---")
        if pairs:
            print(f"[debug] Parsed response from {speaker}: {pairs[-1]['response']}\n---")

        if not response:
            print(f"[warn] No response captured for turn {len(conversation)-1} ({speaker}).")
            break

        # Update number by parsing the response's first integer.
        if reported_number is None:
            print(f"[warn] Could not parse number from {speaker}'s response: {response!r}")
            break

        if reported_number != next_number:
            print(f"[warn] Expected {next_number} but {speaker} replied with {reported_number}.")
            break

        next_number += 1
        current_speaker_index = (current_speaker_index + 1) % len(manager.participants)

    if transcript_path:
        transcript_path.write_text("\n".join(transcript_lines), encoding="utf-8")
        print(f"\nTranscript written to {transcript_path}")

    print("=== Transcript Preview ===")
    for line in transcript_lines[-10:]:
        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
