#!/usr/bin/env python3
"""Run the Option 1 CLAUDE↔Gemini code review simulation."""

from __future__ import annotations

import argparse
import textwrap
from enum import Enum
from pathlib import Path
from typing import Dict

from examples.run_orchestrated_discussion import build_controller, run_discussion
from src.orchestrator.context_manager import ContextManager
from src.utils.config_loader import get_config
from src.utils.logger import get_logger


LOGGER = get_logger("examples.code_review_simulation")


DEFAULT_TURN_PLAN = textwrap.dedent(
    """
    Conversation structure:
    1. Claude: Identify the most critical bug or omission you spot in the function. Mention why it matters.
    2. Gemini: Add a new finding that Claude did not cover. Highlight the impact if left unresolved.
    3. Claude: Propose a fix or guard for one of Gemini's observations.
    4. Gemini: Validate Claude's proposal, add one more improvement opportunity, and note any test you would run.
    5. Claude: Summarize the defects found and list concrete next steps (fixes, tests).
    6. Gemini: Provide the final sign-off gate: can this ship as-is? If not, state blocking reasons succinctly.
    Keep each turn focused, reference specific lines, and avoid repeating prior points.
    """
).strip()


class InclusionStrategy(str, Enum):
    EMBED_FULL = "embed_full"
    HYBRID = "hybrid"
    REFERENCE_ONLY = "reference_only"


def _format_display_path(snippet_path: Path) -> str:
    """Return project-relative path when possible for prompt readability."""

    try:
        return snippet_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return snippet_path.as_posix()


def _render_code_block(lines: list[str]) -> str:
    """Render lines as a Python code block with consistent indentation."""

    if lines:
        formatted = textwrap.indent("\n".join(lines), "    ")
    else:
        formatted = textwrap.indent("# (file is empty)", "    ")
    return f"```python\n{formatted}\n```"


def _render_preview_block(lines: list[str], preview_lines: int) -> tuple[str, bool]:
    """Return a preview code block and whether it was truncated."""

    preview_limit = max(preview_lines, 1)
    preview = lines[:preview_limit]
    truncated = len(lines) > preview_limit
    return _render_code_block(preview), truncated


def determine_inclusion_strategy(
    *,
    line_count: int,
    size_bytes: int,
    embed_threshold: int,
    reference_threshold: int,
    size_threshold: int,
) -> InclusionStrategy:
    """Select how to include the target file in prompts."""

    if size_bytes > size_threshold or line_count > reference_threshold:
        return InclusionStrategy.REFERENCE_ONLY
    if line_count > embed_threshold:
        return InclusionStrategy.HYBRID
    return InclusionStrategy.EMBED_FULL


class ReviewContextManager(ContextManager):
    """Context manager that keeps the review scenario front-and-centre."""

    def __init__(self, scenario: str, *, history_size: int = 20) -> None:
        super().__init__(history_size=history_size)
        self._scenario = scenario

    def build_prompt(self, ai_name: str, task: str, *, include_history: bool = True) -> str:  # type: ignore[override]
        lines = [
            f"{ai_name.title()}, you're co-reviewing the Python helper below.",
        ]
        if not self.history:
            lines.append(self._scenario)
        else:
            lines.append(
                "Revisit the original snippet and review plan above; add insights we haven't covered yet."
            )

        if include_history:
            recent = self._format_recent_history()
            if recent:
                lines.append(f"Recent discussion: {recent}")

        return "\n\n".join(lines)


def build_topic(
    snippet_path: Path,
    turn_plan: str,
    snippet_lines: list[str],
    *,
    strategy: InclusionStrategy,
    preview_lines: int,
) -> str:
    """Compose the orchestrator topic for the code review scenario."""

    display_path = _format_display_path(snippet_path)
    reference_token = f"@{display_path}"
    total_lines = len(snippet_lines)

    sections: list[str] = [
        textwrap.dedent(
            """
            You are participating in an asynchronous code review of a Python helper. Review the
            function exactly as written (do not assume missing context) and follow the
            turn-by-turn plan. Focus on correctness, defensive coding, and actionable guidance.
            """
        ).strip()
    ]

    if strategy is InclusionStrategy.EMBED_FULL:
        sections.append(
            textwrap.dedent(
                f"""
                Target file `{display_path}` (you may also open `{reference_token}` directly in your CLI):
                {_render_code_block(snippet_lines)}
                """
            ).strip()
        )
    elif strategy is InclusionStrategy.HYBRID:
        preview_block, truncated = _render_preview_block(snippet_lines, preview_lines)
        preview_header = (
            f"Preview (first {min(total_lines, max(preview_lines, 1))} of {total_lines} lines shown)."
            if total_lines
            else "Preview (file is empty)."
        )
        section = textwrap.dedent(
            f"""
            Target file `{display_path}`. Open `{reference_token}` to inspect the full code.
            {preview_header}
            {preview_block}
            """
        ).strip()
        if truncated:
            section += f"\n(Preview truncated after {max(preview_lines, 1)} of {total_lines} lines.)"
        sections.append(section)
    else:
        sections.append(
            textwrap.dedent(
                f"""
                Target file `{display_path}`. Open `{reference_token}` to review the complete implementation.
                """
            ).strip()
        )

    sections.append(turn_plan.strip())
    sections.append(
        textwrap.dedent(
            """
            Expectations:
            - Each turn must add a new insight or decision, avoiding duplication.
            - Reference concrete behaviours (e.g., empty ranges, index bounds) when raising issues.
            - Prefer concise bullet points when listing defects or next steps.
            - Keep outputs under 220 words per turn.
            """
        ).strip()
    )

    return "\n\n".join(sections).strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the CLAUDE↔Gemini code review simulation scenario."
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
    parser.add_argument(
        "--snippet",
        type=Path,
        default=Path(__file__).with_name("buggy_review_target.py"),
        help="Path to the Python file the AIs should review (default: buggy_review_target.py).",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=6,
        help="Maximum number of turns to run (default: 6).",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch tmux sessions automatically if they are not already running.",
    )
    parser.add_argument(
        "--claude-session",
        default="claude",
        help="Tmux session name for Claude (default: claude).",
    )
    parser.add_argument(
        "--gemini-session",
        default="gemini",
        help="Tmux session name for Gemini (default: gemini).",
    )
    parser.add_argument(
        "--claude-executable",
        default=claude_default,
        help=f"Command used to launch Claude Code CLI (default: '{claude_default}').",
    )
    parser.add_argument(
        "--gemini-executable",
        default=gemini_default,
        help=f"Command used to launch Gemini CLI (default: '{gemini_default}').",
    )
    parser.add_argument(
        "--claude-working-dir",
        default=None,
        help="Working directory for Claude CLI session (default: None).",
    )
    parser.add_argument(
        "--gemini-working-dir",
        default=None,
        help="Working directory for Gemini CLI session (default: None).",
    )
    parser.add_argument(
        "--claude-startup-timeout",
        type=int,
        default=30,
        help="Startup timeout for Claude CLI (default: 30 seconds).",
    )
    parser.add_argument(
        "--gemini-startup-timeout",
        type=int,
        default=30,
        help="Startup timeout for Gemini CLI (default: 30 seconds).",
    )
    parser.add_argument(
        "--claude-init-wait",
        type=float,
        default=None,
        help="Optional extra wait after launching Claude CLI (seconds).",
    )
    parser.add_argument(
        "--gemini-init-wait",
        type=float,
        default=None,
        help="Optional extra wait after launching Gemini CLI (seconds).",
    )
    parser.add_argument(
        "--claude-bootstrap",
        default=None,
        help="Shell snippet to run before starting Claude CLI (e.g., activate venv).",
    )
    parser.add_argument(
        "--gemini-bootstrap",
        default=None,
        help="Shell snippet to run before starting Gemini CLI.",
    )
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Stop existing tmux sessions before launching new ones.",
    )
    parser.add_argument(
        "--history-size",
        type=int,
        default=20,
        help="Shared context window turn count (default: 20).",
    )
    parser.add_argument(
        "--debug-prompts",
        action="store_true",
        help="Log prompt previews for debugging.",
    )
    parser.add_argument(
        "--prompt-preview-chars",
        type=int,
        default=220,
        help="Character preview length when --debug-prompts is set (default: 220).",
    )
    parser.set_defaults(include_history=True)
    parser.add_argument(
        "--no-history",
        action="store_false",
        dest="include_history",
        help="Skip conversation history when building prompts (smoke-test style).",
    )
    parser.add_argument(
        "--turn-plan-file",
        type=Path,
        default=None,
        help="Optional path to a text file containing a custom turn plan.",
    )
    parser.add_argument(
        "--embed-threshold",
        type=int,
        default=50,
        help="Maximum line count to embed the full code (default: 50).",
    )
    parser.add_argument(
        "--reference-threshold",
        type=int,
        default=100,
        help="Line count above which only the @-reference is provided (default: 100).",
    )
    parser.add_argument(
        "--size-threshold",
        type=int,
        default=5000,
        help="File size in bytes above which only the @-reference is provided (default: 5000).",
    )
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=30,
        help="Number of lines to show in the hybrid preview (default: 30).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs/code_review_simulation.log"),
        help="File path to store the conversation transcript (default: logs/code_review_simulation.log).",
    )
    return parser.parse_args(argv)


def load_turn_plan(args: argparse.Namespace) -> str:
    if args.turn_plan_file:
        LOGGER.info("Loading turn plan from %s", args.turn_plan_file)
        return args.turn_plan_file.read_text(encoding="utf-8").strip()
    return DEFAULT_TURN_PLAN


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.snippet.exists():
        raise SystemExit(f"Snippet file not found: {args.snippet}")

    turn_plan = load_turn_plan(args)
    snippet_text = args.snippet.read_text(encoding="utf-8").rstrip()
    snippet_lines = snippet_text.splitlines()
    size_bytes = args.snippet.stat().st_size
    preview_lines = max(args.preview_lines, 1)
    size_threshold = max(args.size_threshold, 1)

    reference_threshold = args.reference_threshold
    if reference_threshold <= args.embed_threshold:
        reference_threshold = args.embed_threshold + 1
        LOGGER.warning(
            "reference_threshold (%d) must exceed embed_threshold (%d); adjusted to %d.",
            args.reference_threshold,
            args.embed_threshold,
            reference_threshold,
        )

    strategy = determine_inclusion_strategy(
        line_count=len(snippet_lines),
        size_bytes=size_bytes,
        embed_threshold=args.embed_threshold,
        reference_threshold=reference_threshold,
        size_threshold=size_threshold,
    )
    LOGGER.info(
        "Using %s strategy for %s (lines=%d, bytes=%d)",
        strategy.value,
        _format_display_path(args.snippet),
        len(snippet_lines),
        size_bytes,
    )

    claude = build_controller(
        name="claude",
        session_name=args.claude_session,
        executable=args.claude_executable,
        working_dir=args.claude_working_dir,
        auto_start=args.auto_start,
        startup_timeout=args.claude_startup_timeout,
        init_wait=args.claude_init_wait,
        bootstrap=args.claude_bootstrap,
        kill_existing=args.kill_existing,
    )

    gemini = build_controller(
        name="gemini",
        session_name=args.gemini_session,
        executable=args.gemini_executable,
        working_dir=args.gemini_working_dir,
        auto_start=args.auto_start,
        startup_timeout=args.gemini_startup_timeout,
        init_wait=args.gemini_init_wait,
        bootstrap=args.gemini_bootstrap,
        kill_existing=args.kill_existing,
    )

    topic = build_topic(
        args.snippet,
        turn_plan,
        snippet_lines,
        strategy=strategy,
        preview_lines=preview_lines,
    )
    review_context = ReviewContextManager(topic, history_size=args.history_size)

    if args.debug_prompts:
        LOGGER.info("Prompt preview enabled (first %d characters)", args.prompt_preview_chars)

    outcome: Dict[str, object] = run_discussion(
        claude=claude,
        gemini=gemini,
        topic=topic,
        max_turns=args.max_turns,
        history_size=args.history_size,
        start_with="claude",
        debug_prompts=args.debug_prompts,
        debug_prompt_chars=args.prompt_preview_chars,
        include_history=args.include_history,
        context_manager=review_context,
    )

    conversation = outcome["conversation"]
    log_path = args.log_file

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as handle:
            handle.write("=== CODE REVIEW SUMMARY ===\n")
            for turn in conversation:
                speaker = turn.get("speaker", "unknown")
                handle.write(f"\n[{turn.get('turn', '?')}] {speaker.title()} says:\n")
                handle.write(textwrap.indent((turn.get("response") or "(no response)").strip(), "    "))
                handle.write("\n")

    print("\n=== CODE REVIEW SUMMARY ===")
    for turn in conversation:
        speaker = turn.get("speaker", "unknown")
        print(f"\n[{turn.get('turn', '?')}] {speaker.title()} says:")
        print(textwrap.indent((turn.get("response") or "(no response)").strip(), "    "))

    if log_path:
        print(f"\nRun complete. Transcript saved to {log_path}.")
    else:
        print("\nRun complete. Inspect logs/ or tmux panes for raw transcripts if needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
