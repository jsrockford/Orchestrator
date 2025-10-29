#!/usr/bin/env python3
"""
Kick off a multi-AI discussion using the DevelopmentTeamOrchestrator.

This script expects Claude, Gemini, and Codex CLI sessions to be available
(either already running inside tmux, or launchable via the configured
executables). It wires the controllers into the orchestrator, runs a short
discussion on the supplied topic, and prints a concise turn-by-turn summary.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import shlex
from pathlib import Path
import logging
from typing import Dict, Optional, Sequence

from src.controllers.tmux_controller import SessionBackendError, SessionNotFoundError, TmuxController
from src.orchestrator import ContextManager, DevelopmentTeamOrchestrator, MessageRouter
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)


def build_controller(
    *,
    name: str,
    session_name: str,
    executable: str,
    working_dir: str | None,
    auto_start: bool,
    startup_timeout: int,
    init_wait: float | None,
    bootstrap: str | None,
    kill_existing: bool,
) -> TmuxController:
    base_config = dict(get_config().get_section(name.lower()) or {})
    ai_config: Dict[str, object] = base_config
    ai_config["startup_timeout"] = startup_timeout
    ai_config["pause_on_manual_clients"] = False
    if init_wait is not None:
        ai_config["init_wait"] = init_wait

    if name.lower() == "gemini":
        # Ensure Gemini uses the reliable submit behaviour even if the active
        # config copy is stale in the tmux worktree.
        ai_config["submit_key"] = "C-m"
        ai_config["text_enter_delay"] = 0.5
        ai_config["post_text_delay"] = 0.5

    exe_parts = shlex.split(executable)
    if not exe_parts:
        raise ValueError(f"No executable provided for {name}")

    launch_executable = exe_parts[0]
    launch_args = exe_parts[1:]

    if bootstrap:
        shell_command = f"{bootstrap} && {executable}"
        launch_executable = "bash"
        launch_args = ["-lc", shell_command]

    controller = TmuxController(
        session_name=session_name,
        executable=launch_executable,
        working_dir=working_dir,
        ai_config=ai_config,
        executable_args=launch_args,
    )

    controller.reset_output_cache()

    if kill_existing and controller.session_exists():
        if not controller.kill_session():
            raise SessionBackendError(
                f"Failed to kill existing tmux session '{session_name}' for {name}."
            )

    if controller.session_exists():
        controller.resume_automation(flush_pending=True)
        return controller

    if not auto_start:
        raise SessionNotFoundError(
            f"Tmux session '{session_name}' not found for {name}. "
            "Start the CLI manually or pass --auto-start."
        )

    controller.start()
    controller.wait_for_ready()
    return controller


def run_discussion(
    *,
    claude: TmuxController,
    gemini: TmuxController,
    codex: TmuxController,
    topic: str,
    max_turns: int,
    history_size: int,
    start_with: str,
    debug_prompts: bool = False,
    debug_prompt_chars: int = 200,
    include_history: bool = True,
    context_manager: ContextManager | None = None,
    message_router: MessageRouter | None = None,
    participants: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    controllers = {"claude": claude, "gemini": gemini, "codex": codex}
    orchestrator = DevelopmentTeamOrchestrator(controllers)
    if debug_prompts:
        orchestrator.set_prompt_debug(True, preview_chars=debug_prompt_chars)
    context_manager = context_manager or ContextManager(history_size=history_size)
    canonical_map = {name.lower(): name for name in controllers}

    if participants is None:
        participants = list(controllers.keys())
    else:
        normalized = []
        for participant in participants:
            normalized_name = canonical_map.get(participant.lower())
            if normalized_name is None:
                raise ValueError(f"Unknown participant '{participant}'.")
            normalized.append(normalized_name)
        participants = normalized

    start_key = canonical_map.get(start_with.lower())
    if start_key is None:
        raise ValueError(f"Unknown --start-with value '{start_with}'.")
    if start_key in participants:
        start_idx = participants.index(start_key)
        participants = participants[start_idx:] + participants[:start_idx]

    router = message_router or MessageRouter(participants, context_manager=context_manager)

    result = orchestrator.start_discussion(
        topic,
        max_turns=max_turns,
        context_manager=context_manager,
        message_router=router,
        participants=participants,
        include_history=include_history,
    )
    return {
        "conversation": result["conversation"],
        "context_manager": context_manager,
        "message_router": router,
    }


def format_turn(turn: Dict[str, object]) -> str:
    speaker = turn.get("speaker", "unknown")
    prompt = (turn.get("prompt") or "").strip()
    response = (turn.get("response") or "").strip()
    metadata = turn.get("metadata") or {}
    status_bits = []
    if metadata.get("queued"):
        status_bits.append("queued")
    if metadata.get("consensus"):
        status_bits.append("consensus")
    if metadata.get("conflict"):
        status_bits.append("conflict")
    status_suffix = f" [{' '.join(status_bits)}]" if status_bits else ""

    prompt_block = textwrap.indent(prompt, "    ")
    response_block = textwrap.indent(response, "    ") if response else "    (no response captured yet)"

    return "\n".join(
        [
            f"{turn.get('turn')}: {speaker}{status_suffix}",
            "  Prompt:",
            prompt_block,
            "  Response:",
            response_block,
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a coordinated discussion between Claude, Gemini, and Codex."
    )
    config = get_config()

    def default_command(agent: str) -> str:
        try:
            return config.get_executable_command(agent)
        except (KeyError, TypeError) as exc:
            parser.error(
                f"Executable for '{agent}' is not configured correctly in config.yaml: {exc}"
            )

    claude_default = default_command("claude")
    gemini_default = default_command("gemini")
    codex_default = default_command("codex")
    parser.add_argument("topic", help="Topic for the discussion.")
    parser.add_argument(
        "--max-turns",
        type=int,
        default=6,
        help="Maximum number of turns to run (default: 6).",
    )
    parser.add_argument(
        "--history-size",
        type=int,
        default=20,
        help="Number of turns to retain in the shared context (default: 20).",
    )
    parser.add_argument(
        "--simple-prompts",
        action="store_true",
        help="Skip conversation history when building prompts (smoke-test mode).",
    )
    parser.add_argument(
        "--start-with",
        choices=["claude", "gemini", "codex"],
        default="gemini",
        help="Which AI should speak first (default: gemini).",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch tmux sessions automatically if they are not running.",
    )
    parser.add_argument(
        "--claude-session",
        default="claude",
        help="Tmux session name for Claude (default: claude).",
    )
    parser.add_argument(
        "--claude-executable",
        default=claude_default,
        help=f"Executable used to start Claude (default: '{claude_default}').",
    )
    parser.add_argument(
        "--claude-startup-timeout",
        type=int,
        default=10,
        help="Seconds to wait for Claude session readiness when auto-starting (default: 10).",
    )
    parser.add_argument(
        "--claude-init-wait",
        type=float,
        default=None,
        help="Seconds to pause after spawning Claude before sending the first input.",
    )
    parser.add_argument(
        "--claude-bootstrap",
        default=None,
        help="Command to run before launching the Claude executable (e.g., 'echo 2 | ...').",
    )
    parser.add_argument(
        "--claude-cwd",
        default=None,
        help="Working directory for the Claude session (defaults to current directory).",
    )
    parser.add_argument(
        "--gemini-session",
        default="gemini",
        help="Tmux session name for Gemini (default: gemini).",
    )
    parser.add_argument(
        "--gemini-executable",
        default=gemini_default,
        help=f"Executable used to start Gemini (default: '{gemini_default}').",
    )
    parser.add_argument(
        "--gemini-startup-timeout",
        type=int,
        default=60,
        help="Seconds to wait for Gemini session readiness when auto-starting (default: 60).",
    )
    parser.add_argument(
        "--gemini-init-wait",
        type=float,
        default=None,
        help="Seconds to pause after spawning Gemini before sending the first input.",
    )
    parser.add_argument(
        "--gemini-bootstrap",
        default=None,
        help="Command to run before launching the Gemini executable.",
    )
    parser.add_argument(
        "--gemini-cwd",
        default=None,
        help="Working directory for the Gemini session (defaults to current directory).",
    )
    parser.add_argument(
        "--codex-session",
        default="codex",
        help="Tmux session name for Codex (default: codex).",
    )
    parser.add_argument(
        "--codex-executable",
        default=codex_default,
        help=f"Executable used to start Codex (default: '{codex_default}').",
    )
    parser.add_argument(
        "--codex-startup-timeout",
        type=int,
        default=20,
        help="Seconds to wait for Codex session readiness when auto-starting (default: 20).",
    )
    parser.add_argument(
        "--codex-init-wait",
        type=float,
        default=None,
        help="Seconds to pause after spawning Codex before sending the first input.",
    )
    parser.add_argument(
        "--codex-bootstrap",
        default=None,
        help="Command to run before launching the Codex executable.",
    )
    parser.add_argument(
        "--codex-cwd",
        default=None,
        help="Working directory for the Codex session (defaults to current directory).",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional path to write the conversation transcript and summary.",
    )
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Kill existing Claude/Gemini/Codex tmux sessions before starting.",
    )
    parser.add_argument(
        "--cleanup-after",
        action="store_true",
        help="Kill Claude/Gemini/Codex tmux sessions after the discussion completes.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=None,
        help="Convenience override for all --*-startup-timeout values.",
    )
    parser.add_argument(
        "--debug-prompts",
        action="store_true",
        help="Log prompt diagnostics before each dispatch.",
    )
    parser.add_argument(
        "--debug-prompt-chars",
        type=int,
        default=200,
        help="How many characters of each prompt to include in debug logs (default 200).",
    )
    parser.add_argument(
        "--group-system-prompt",
        default=None,
        help="Optional system prompt sent to every AI before the discussion begins.",
    )
    parser.add_argument(
        "--group-system-prompt-file",
        default=None,
        help="Path to a briefing file; sends 'Read @<file>' to every AI before the discussion.",
    )
    parser.add_argument(
        "--claude-system-prompt",
        default=None,
        help="Additional system prompt sent only to Claude before the discussion.",
    )
    parser.add_argument(
        "--claude-system-prompt-file",
        default=None,
        help="Path to a briefing file sent only to Claude (as 'Read @<file>').",
    )
    parser.add_argument(
        "--gemini-system-prompt",
        default=None,
        help="Additional system prompt sent only to Gemini before the discussion.",
    )
    parser.add_argument(
        "--gemini-system-prompt-file",
        default=None,
        help="Path to a briefing file sent only to Gemini (as 'Read @<file>').",
    )
    parser.add_argument(
        "--codex-system-prompt",
        default=None,
        help="Additional system prompt sent only to Codex before the discussion.",
    )
    parser.add_argument(
        "--codex-system-prompt-file",
        default=None,
        help="Path to a briefing file sent only to Codex (as 'Read @<file>').",
    )

    args = parser.parse_args(argv)

    override = args.startup_timeout
    if override is not None:
        if args.claude_startup_timeout == parser.get_default("claude_startup_timeout"):
            args.claude_startup_timeout = override
        if args.gemini_startup_timeout == parser.get_default("gemini_startup_timeout"):
            args.gemini_startup_timeout = override
        if args.codex_startup_timeout == parser.get_default("codex_startup_timeout"):
            args.codex_startup_timeout = override

    return args


def cleanup_controller(controller: Optional[TmuxController], label: str) -> None:
    if controller is None:
        return

    try:
        if controller.session_exists():
            if controller.kill_session():
                print(f"[cleanup] Killed {label} session '{controller.session_name}'.")
            else:
                print(
                    f"[cleanup] Unable to kill {label} session '{controller.session_name}'.",
                    file=sys.stderr,
                )
    except (SessionNotFoundError, SessionBackendError) as exc:
        print(f"[cleanup] Error while killing {label} session: {exc}", file=sys.stderr)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.debug_prompts:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    include_history = not args.simple_prompts
    effective_history_size = max(1, args.history_size if include_history else 1)

    claude: Optional[TmuxController] = None
    gemini: Optional[TmuxController] = None
    codex: Optional[TmuxController] = None

    try:
        claude = build_controller(
            name="Claude",
            session_name=args.claude_session,
            executable=args.claude_executable,
            working_dir=args.claude_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.claude_startup_timeout,
            init_wait=args.claude_init_wait,
            bootstrap=args.claude_bootstrap,
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
            bootstrap=args.gemini_bootstrap,
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
            bootstrap=args.codex_bootstrap,
            kill_existing=args.kill_existing,
        )
    except (SessionNotFoundError, SessionBackendError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    controllers = {"claude": claude, "gemini": gemini, "codex": codex}

    prompt_queue: Dict[str, list[str]] = {name: [] for name in controllers}
    if args.group_system_prompt or args.group_system_prompt_file:
        group_prompt = args.group_system_prompt or f"Read @{args.group_system_prompt_file}"
        for prompts in prompt_queue.values():
            prompts.append(group_prompt)

    for ai_name, controller in controllers.items():
        if controller is None:
            continue

        prompt_arg = getattr(args, f"{ai_name}_system_prompt", None)
        file_arg = getattr(args, f"{ai_name}_system_prompt_file", None)
        if prompt_arg or file_arg:
            prompt_queue[ai_name].append(prompt_arg or f"Read @{file_arg}")

    if any(prompts for prompts in prompt_queue.values()):
        for name, controller in controllers.items():
            if controller is None:
                continue

            for prompt in prompt_queue[name]:
                logger.info("Sending pre-discussion system prompt to %s", name)
                try:
                    controller.send_command(prompt)
                    controller.wait_for_ready(timeout=30)
                except Exception as exc:  # pylint: disable=broad-except
                    print(
                        f"[error] Failed to deliver pre-discussion prompt to {name}: {exc}",
                        file=sys.stderr,
                    )
                    return 1

    try:
        result = run_discussion(
            claude=claude,
            gemini=gemini,
            codex=codex,
            topic=args.topic,
            max_turns=args.max_turns,
            history_size=effective_history_size,
            start_with=args.start_with,
            debug_prompts=args.debug_prompts,
            debug_prompt_chars=args.debug_prompt_chars,
            include_history=include_history,
        )
    finally:
        if args.cleanup_after:
            cleanup_controller(claude, "Claude")
            cleanup_controller(gemini, "Gemini")
            cleanup_controller(codex, "Codex")

    conversation = result["conversation"]
    context_manager: ContextManager = result["context_manager"]

    print("\n=== Conversation Transcript ===")
    for turn in conversation:
        print(format_turn(turn))
        print("-")

    print("\n=== Shared Context Summary ===")
    summary = context_manager.summarize_conversation(context_manager.history)
    print(summary or "(no summary available)")

    if args.log_file:
        log_path = Path(args.log_file)
        if log_path.suffix:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_path.mkdir(parents=True, exist_ok=True)
            log_path = log_path / "discussion.log"

        log_lines = ["=== Conversation Transcript ==="]
        log_lines.extend(format_turn(turn) + "\n-" for turn in conversation)
        log_lines.append("\n=== Shared Context Summary ===")
        log_lines.append(summary or "(no summary available)")
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        print(f"\n[log] Conversation written to {log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
