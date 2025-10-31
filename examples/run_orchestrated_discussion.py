#!/usr/bin/env python3
"""
Kick off a multi-AI discussion using the DevelopmentTeamOrchestrator.

This script can coordinate Claude, Gemini, Codex, and Qwen CLI sessions. You
can run all of them together or choose a specific subset for focused testing.
Each controller may attach to an existing tmux session or launch the executable
on demand, then the orchestrator runs a short discussion on the supplied topic
and prints a concise turn-by-turn summary.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import shlex
from pathlib import Path
import logging
from typing import Dict, Optional, Sequence

from src.controllers import (
    ClaudeController,
    CodexController,
    GeminiController,
    QwenController,
    TmuxController,
)
from src.controllers.session_backend import SessionSpec
from src.controllers.tmux_controller import SessionBackendError, SessionNotFoundError
from src.orchestrator import ContextManager, DevelopmentTeamOrchestrator, MessageRouter
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)

AGENT_ORDER = ("claude", "gemini", "codex", "qwen")
AGENT_DISPLAY_NAMES = {
    "claude": "Claude",
    "gemini": "Gemini",
    "codex": "Codex",
    "qwen": "Qwen",
}
_STARTUP_TIMEOUT_FALLBACKS = {
    "claude": 20,
    "gemini": 60,
    "codex": 20,
    "qwen": 25,
}

CONTROLLER_REGISTRY = {
    "claude": ClaudeController,
    "gemini": GeminiController,
    "codex": CodexController,
    "qwen": QwenController,
}


def build_controller(
    *,
    agent_key: str,
    display_name: str,
    session_name: str,
    executable: str,
    working_dir: str | None,
    auto_start: bool,
    startup_timeout: int,
    init_wait: float | None,
    bootstrap: str | None,
    kill_existing: bool,
) -> TmuxController:
    normalized_key = agent_key.lower()
    controller_cls = CONTROLLER_REGISTRY.get(normalized_key)
    if controller_cls is None:
        raise ValueError(f"No controller registered for '{agent_key}'.")

    controller = controller_cls(
        session_name=session_name,
        working_dir=working_dir,
    )

    # Work on a copy so downstream tweaks don't mutate the global config loader.
    controller.config = dict(controller.config)

    # Apply runtime overrides to the controller configuration
    controller.config["startup_timeout"] = startup_timeout
    controller.startup_timeout = startup_timeout
    controller.config["pause_on_manual_clients"] = False
    controller._pause_on_manual_clients = False  # pylint: disable=protected-access
    if init_wait is not None:
        controller.config["init_wait"] = init_wait

    exe_parts = shlex.split(executable)
    if not exe_parts:
        raise ValueError(f"No executable provided for {display_name}")

    launch_executable = exe_parts[0]
    launch_args = exe_parts[1:]

    if bootstrap:
        shell_command = f"{bootstrap} && {executable}"
        launch_executable = "bash"
        launch_args = ["-lc", shell_command]

    controller.executable = launch_executable
    controller.executable_args = tuple(launch_args)
    controller.spec = SessionSpec(
        name=controller.session_name,
        executable=launch_executable,
        working_dir=controller.working_dir,
        args=controller.executable_args,
    )

    controller.reset_output_cache()

    if kill_existing and controller.session_exists():
        if not controller.kill_session():
            raise SessionBackendError(
                f"Failed to kill existing tmux session '{session_name}' for {display_name}."
            )

    if controller.session_exists():
        controller.resume_automation(flush_pending=True)
        return controller

    if not auto_start:
        raise SessionNotFoundError(
            f"Tmux session '{session_name}' not found for {display_name}. "
            "Start the CLI manually or pass --auto-start."
        )

    controller.start()
    controller.wait_for_ready()
    return controller


def run_discussion(
    *,
    controllers: Dict[str, TmuxController],
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
        description="Run a coordinated discussion between selected AI CLIs (Claude, Gemini, Codex, Qwen)."
    )
    config = get_config()

    def default_command(agent: str) -> str:
        try:
            return config.get_executable_command(agent)
        except (KeyError, TypeError) as exc:
            parser.error(
                f"Executable for '{agent}' is not configured correctly in config.yaml: {exc}"
            )

    executable_defaults = {agent: default_command(agent) for agent in AGENT_ORDER}
    startup_defaults: Dict[str, int] = {}
    for agent in AGENT_ORDER:
        config_value = config.get(f"{agent}.startup_timeout")
        fallback = _STARTUP_TIMEOUT_FALLBACKS[agent]
        try:
            startup_defaults[agent] = int(config_value)
        except (TypeError, ValueError):
            startup_defaults[agent] = fallback
    parser.add_argument("topic", help="Topic for the discussion.")
    parser.add_argument(
        "--agents",
        nargs="+",
        choices=list(AGENT_ORDER) + ["all"],
        default=["all"],
        help=(
            "Select which agents participate. Specify one or more agent names "
            f"({', '.join(AGENT_ORDER)}) or use 'all' to include every configured agent."
        ),
    )
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
        choices=list(AGENT_ORDER),
        default="gemini",
        help="Which AI should speak first (default: gemini).",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch tmux sessions automatically if they are not running.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional path to write the conversation transcript and summary.",
    )
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Kill existing tmux sessions for the selected agents before starting.",
    )
    parser.add_argument(
        "--cleanup-after",
        action="store_true",
        help="Kill the selected agent tmux sessions after the discussion completes.",
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
    for agent in AGENT_ORDER:
        display = AGENT_DISPLAY_NAMES[agent]
        default_exec = executable_defaults[agent]
        parser.add_argument(
            f"--{agent}-session",
            default=agent,
            help=f"Tmux session name for {display} (default: {agent}).",
        )
        parser.add_argument(
            f"--{agent}-executable",
            default=default_exec,
            help=f"Executable used to start {display} (default: '{default_exec}').",
        )
        parser.add_argument(
            f"--{agent}-startup-timeout",
            type=int,
            default=startup_defaults[agent],
            help=(
                f"Seconds to wait for {display} session readiness when auto-starting "
                f"(default: {startup_defaults[agent]})."
            ),
        )
        parser.add_argument(
            f"--{agent}-init-wait",
            type=float,
            default=None,
            help=f"Seconds to pause after spawning {display} before sending the first input.",
        )
        parser.add_argument(
            f"--{agent}-bootstrap",
            default=None,
            help=f"Command to run before launching the {display} executable.",
        )
        parser.add_argument(
            f"--{agent}-cwd",
            default=None,
            help=f"Working directory for the {display} session (defaults to current directory).",
        )
        parser.add_argument(
            f"--{agent}-system-prompt",
            default=None,
            help=f"Additional system prompt sent only to {display} before the discussion.",
        )
        parser.add_argument(
            f"--{agent}-system-prompt-file",
            default=None,
            help=f"Path to a briefing file sent only to {display} (as 'Read @<file>').",
        )

    args = parser.parse_args(argv)

    override = args.startup_timeout
    if override is not None:
        for agent in AGENT_ORDER:
            field = f"{agent}_startup_timeout"
            if getattr(args, field) == parser.get_default(field):
                setattr(args, field, override)

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

    if "all" in args.agents:
        selected_agents = list(AGENT_ORDER)
    else:
        seen = set()
        selected_agents = []
        for agent in args.agents:
            if agent not in seen:
                selected_agents.append(agent)
                seen.add(agent)

    if not selected_agents:
        print("[error] No agents selected. Use --agents to specify at least one CLI.", file=sys.stderr)
        return 1

    start_with = args.start_with
    if start_with not in selected_agents:
        replacement = selected_agents[0]
        print(
            f"[info] --start-with '{start_with}' is not in the selected agent list; "
            f"switching to '{replacement}'.",
            file=sys.stderr,
        )
        start_with = replacement

    controllers: Dict[str, TmuxController] = {}

    try:
        for agent in selected_agents:
            display_name = AGENT_DISPLAY_NAMES[agent]
            controller = build_controller(
                agent_key=agent,
                display_name=display_name,
                session_name=getattr(args, f"{agent}_session"),
                executable=getattr(args, f"{agent}_executable"),
                working_dir=getattr(args, f"{agent}_cwd"),
                auto_start=args.auto_start,
                startup_timeout=getattr(args, f"{agent}_startup_timeout"),
                init_wait=getattr(args, f"{agent}_init_wait"),
                bootstrap=getattr(args, f"{agent}_bootstrap"),
                kill_existing=args.kill_existing,
            )
            controllers[agent] = controller
    except (SessionNotFoundError, SessionBackendError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

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
            controllers=controllers,
            topic=args.topic,
            max_turns=args.max_turns,
            history_size=effective_history_size,
            start_with=start_with,
            debug_prompts=args.debug_prompts,
            debug_prompt_chars=args.debug_prompt_chars,
            include_history=include_history,
            participants=selected_agents,
        )
    finally:
        if args.cleanup_after:
            for agent, controller in controllers.items():
                cleanup_controller(controller, AGENT_DISPLAY_NAMES.get(agent, agent))

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
