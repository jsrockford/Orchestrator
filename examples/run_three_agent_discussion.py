#!/usr/bin/env python3
"""
Demonstrate a three-participant discussion (Claude, Gemini, Codex agent).

The script defaults to a stubbed simulation so it can run without access to the
Claude, Gemini, or Codex CLIs. Pass ``--mode tmux`` to attempt a real tmux-backed
run using the configured controllers (requires tmux plus the CLI executables).

Flag switches mirror ``run_orchestrated_discussion.py`` so long-running tests can
be controlled consistently across the demo scripts.
"""

from __future__ import annotations

import argparse
import logging
import shlex
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from src.controllers.tmux_controller import (
    SessionBackendError,
    SessionNotFoundError,
    TmuxController,
)
from src.orchestrator.context_manager import ContextManager
from src.orchestrator.conversation_manager import ConversationManager
from src.orchestrator.message_router import MessageRouter
from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator
from src.utils.config_loader import get_config
from src.utils.output_parser import OutputParser


# --------------------------------------------------------------------------- #
# Stub controllers for the default simulation mode
# --------------------------------------------------------------------------- #

@dataclass
class StubResponsePlan:
    lines: List[str] = field(default_factory=list)
    cursor: int = 0

    def next(self) -> str:
        if not self.lines:
            return ""
        response = self.lines[self.cursor]
        self.cursor = min(self.cursor + 1, len(self.lines) - 1)
        return response


class StubController:
    """
    Simple conversational stub that satisfies the controller interface used by
    the orchestrator/conversation manager tests.
    """

    def __init__(self, responses: Iterable[str], *, role: Optional[str] = None) -> None:
        self._plan = StubResponsePlan(list(responses))
        self._last_output: str = ""
        self._paused: bool = False
        self._role = role

    # --- Controller surface -------------------------------------------------

    def get_status(self) -> Dict[str, Dict[str, object]]:
        return {
            "automation": {
                "paused": self._paused,
                "reason": None,
                "pending_commands": 0,
                "manual_clients": [],
            }
        }

    def send_command(self, command: str, submit: bool = True) -> bool:  # noqa: ARG002 - submit unused
        self._last_output = self._plan.next()
        return True

    # --- Helpers ------------------------------------------------------------

    def wait_for_ready(self, timeout: float | None = None, check_interval: float | None = None) -> bool:  # noqa: ARG002
        return True

    def get_last_output(self, *, tail_lines: int = 50) -> str:  # noqa: ARG002
        return self._last_output


# --------------------------------------------------------------------------- #
# Controller factories
# --------------------------------------------------------------------------- #

ParticipantMetadata = Dict[str, Dict[str, object]]
DEFAULT_PARTICIPANTS: Sequence[str] = ("claude", "gemini", "codex")


def build_stub_controllers() -> tuple[Dict[str, StubController], ParticipantMetadata]:
    controllers = {
        "claude": StubController(
            [
                "Initial roadmap outline with priorities.",
                "Agreeing on implementation plan.",
                "Ready to ship the increment.",
            ],
            role="lead reviewer",
        ),
        "gemini": StubController(
            [
                "Architecture impact assessment plus risks.",
                "Identified integration touchpoints.",
                "Confirmed monitoring hooks.",
            ],
            role="architect",
        ),
        "codex": StubController(
            [
                "Implementation checklist with code owners.",
                "Outlined tests and tooling updates.",
                "Deployment playbook ready.",
            ],
            role="implementation",
        ),
    }

    metadata: ParticipantMetadata = {
        "claude": {"type": "cli", "role": "lead reviewer"},
        "gemini": {"type": "cli", "role": "architect"},
        "codex": {"type": "cli", "role": "implementation"},
    }
    return controllers, metadata


def build_controller(
    *,
    name: str,
    session_name: str,
    executable: str,
    working_dir: Optional[str],
    auto_start: bool,
    startup_timeout: int,
    init_wait: Optional[float],
    bootstrap: Optional[str],
    kill_existing: bool,
) -> TmuxController:
    base_config = dict(get_config().get_section(name.lower()) or {})
    ai_config: Dict[str, object] = base_config
    ai_config["startup_timeout"] = startup_timeout
    ai_config["pause_on_manual_clients"] = False
    if init_wait is not None:
        ai_config["init_wait"] = init_wait

    if name.lower() == "gemini":
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


def build_tmux_controllers(args) -> tuple[Dict[str, TmuxController], ParticipantMetadata]:
    controllers: Dict[str, TmuxController] = {}
    metadata: ParticipantMetadata = {
        "claude": {"type": "cli", "role": "lead reviewer"},
        "gemini": {"type": "cli", "role": "architect"},
        "codex": {"type": "cli", "role": "implementation"},
    }

    controllers["claude"] = build_controller(
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
    controllers["gemini"] = build_controller(
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
    controllers["codex"] = build_controller(
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

    return controllers, metadata


# --------------------------------------------------------------------------- #
# Discussion runner
# --------------------------------------------------------------------------- #

def run_discussion(
    controllers: Dict[str, object],
    metadata: ParticipantMetadata,
    *,
    topic: str,
    participants: Sequence[str],
    max_turns: int,
    history_size: int,
    include_history: bool,
    debug_prompts: bool,
    debug_prompt_chars: int,
) -> Dict[str, object]:
    orchestrator = DevelopmentTeamOrchestrator(controllers, metadata=metadata)
    if debug_prompts:
        orchestrator.set_prompt_debug(True, preview_chars=debug_prompt_chars)

    context_manager = ContextManager(
        history_size=history_size,
        participant_metadata=metadata,
    )
    router = MessageRouter(participants, context_manager=context_manager)
    manager = ConversationManager(
        orchestrator,
        participants,
        context_manager=context_manager,
        message_router=router,
        participant_metadata=metadata,
        max_history=history_size,
        include_history=include_history,
    )

    conversation = manager.facilitate_discussion(topic, max_turns=max_turns)
    return {
        "conversation": conversation,
        "context_manager": context_manager,
        "message_router": router,
    }


def format_turn(turn: Dict[str, object]) -> str:
    parser = OutputParser()
    response = parser.clean_output(turn.get("response") or "", strip_trailing_prompts=True)
    dispatch = turn.get("dispatch") or {}
    queued = " (queued)" if dispatch.get("queued") else ""
    metadata = turn.get("metadata") or {}
    status_bits: List[str] = []
    if metadata.get("consensus"):
        status_bits.append("consensus")
    if metadata.get("conflict"):
        status_bits.append("conflict")
    if metadata.get("queued"):
        status_bits.append("queued")
    status_suffix = f" [{' '.join(status_bits)}]" if status_bits else ""
    prompt = (turn.get("prompt") or "").strip()
    formatted_prompt = textwrap.indent(prompt or "<no prompt>", "    ")
    formatted_response = textwrap.indent(response or "<no output>", "    ")

    return "\n".join(
        [
            f"Turn {turn.get('turn')} • {turn.get('speaker')}{queued}{status_suffix}",
            "  Prompt:",
            formatted_prompt,
            "  Response:",
            formatted_response,
        ]
    )


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


def resolve_participants(
    available: Iterable[str],
    start_with: str,
) -> List[str]:
    available_list = list(available)
    normalized = [name for name in DEFAULT_PARTICIPANTS if name in available_list]
    if not normalized:
        normalized = available_list.copy()

    start = start_with.lower()
    if start not in normalized:
        return list(normalized)

    idx = normalized.index(start)
    return list(normalized[idx:] + normalized[:idx])


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    cfg = get_config()

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
    parser.add_argument(
        "topic",
        nargs="?",
        default="Align on the next sprint backlog",
        help="Discussion topic.",
    )
    parser.add_argument(
        "--topic",
        dest="topic_override",
        help="Discussion topic (overrides the positional argument).",
    )
    parser.add_argument(
        "--mode",
        choices=["stub", "tmux"],
        default="stub",
        help="Controller backend to use.",
    )
    parser.add_argument(
        "--max-turns",
        "--turns",
        type=int,
        dest="max_turns",
        default=6,
        help="Maximum number of turns to run.",
    )
    parser.add_argument(
        "--history-size",
        type=int,
        default=20,
        help="Number of turns to retain in the shared context.",
    )
    parser.add_argument(
        "--simple-prompts",
        action="store_true",
        help="Skip conversation history when building prompts.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        dest="simple_prompts",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--start-with",
        choices=["claude", "gemini", "codex"],
        default="gemini",
        help="Which participant should speak first.",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch tmux sessions automatically if they are not running.",
    )
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Kill existing tmux sessions before starting.",
    )
    parser.add_argument(
        "--cleanup-after",
        action="store_true",
        help="Kill tmux sessions after the discussion completes.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=None,
        help="Convenience override for per-agent startup timeouts.",
    )
    parser.add_argument(
        "--debug-prompts",
        action="store_true",
        help="Log prompt diagnostics before dispatch.",
    )
    parser.add_argument(
        "--debug-prompt-chars",
        type=int,
        default=200,
        help="How many characters to include when debugging prompts.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional path to write the conversation transcript and summary.",
    )

    # Claude options
    parser.add_argument(
        "--claude-session",
        default="claude",
        help="Tmux session name for Claude.",
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
        help="Seconds to wait for Claude session readiness when auto-starting.",
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
        help="Command to run before launching the Claude executable.",
    )
    parser.add_argument(
        "--claude-cwd",
        default=None,
        help="Working directory for the Claude session.",
    )

    # Gemini options
    parser.add_argument(
        "--gemini-session",
        default="gemini",
        help="Tmux session name for Gemini.",
    )
    parser.add_argument(
        "--gemini-executable",
        default=gemini_default,
        help=f"Executable used to start Gemini (default: '{gemini_default}').",
    )
    parser.add_argument(
        "--gemini-startup-timeout",
        type=int,
        default=20,
        help="Seconds to wait for Gemini session readiness when auto-starting.",
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
        help="Working directory for the Gemini session.",
    )

    # Codex options
    parser.add_argument(
        "--codex-session",
        default="codex",
        help="Tmux session name for Codex.",
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
        help="Seconds to wait for Codex session readiness when auto-starting.",
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
        help="Working directory for the Codex session.",
    )

    args = parser.parse_args(argv)

    if args.topic_override:
        args.topic = args.topic_override
    delattr(args, "topic_override")

    override = args.startup_timeout
    if override is not None:
        if args.claude_startup_timeout == parser.get_default("claude_startup_timeout"):
            args.claude_startup_timeout = override
        if args.gemini_startup_timeout == parser.get_default("gemini_startup_timeout"):
            args.gemini_startup_timeout = override
        if args.codex_startup_timeout == parser.get_default("codex_startup_timeout"):
            args.codex_startup_timeout = override

    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if args.debug_prompts:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    include_history = not args.simple_prompts
    effective_history_size = max(1, args.history_size if include_history else 1)

    if args.mode == "stub":
        controllers, metadata = build_stub_controllers()
    else:
        try:
            controllers, metadata = build_tmux_controllers(args)
        except (SessionNotFoundError, SessionBackendError, ValueError) as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1

    participants = resolve_participants(controllers.keys(), args.start_with)

    result = run_discussion(
        controllers,
        metadata,
        topic=args.topic,
        participants=participants,
        max_turns=max(1, args.max_turns),
        history_size=effective_history_size,
        include_history=include_history,
        debug_prompts=args.debug_prompts,
        debug_prompt_chars=args.debug_prompt_chars,
    )

    conversation = result["conversation"]
    context_manager: ContextManager = result["context_manager"]

    print(f"Three-agent discussion on: {args.topic}")
    print("=" * 80)
    for turn in conversation:
        print(format_turn(turn))
        print("-" * 80)

    summary = context_manager.summarize_conversation(context_manager.history)
    print("\nSummary:")
    print(summary or "(no summary available)")

    if args.log_file:
        log_path = Path(args.log_file)
        if log_path.suffix:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_path.mkdir(parents=True, exist_ok=True)
            log_path = log_path / "discussion.log"

        log_lines = ["=== Conversation Transcript ==="]
        for turn in conversation:
            log_lines.append(format_turn(turn))
            log_lines.append("-" * 80)
        log_lines.append("\n=== Shared Context Summary ===")
        log_lines.append(summary or "(no summary available)")
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        print(f"\n[log] Conversation written to {log_path}")

    if args.cleanup_after and args.mode == "tmux":
        for name, controller in controllers.items():
            cleanup_controller(controller, name.capitalize())

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
