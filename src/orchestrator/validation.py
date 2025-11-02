"""Post-completion validation helpers for orchestrated discussions."""

from __future__ import annotations

import glob
import logging
import subprocess
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..utils.config_loader import get_config

logger = logging.getLogger(__name__)


class PostCompletionValidator:
    """Inspect completed discussions for testing evidence and optional automated checks."""

    def __init__(self, settings: Optional[Dict[str, object]] = None) -> None:
        cfg = settings or get_config().get_section("post_completion_validation") or {}
        self.enabled: bool = bool(cfg.get("enabled", False))
        self.require_mentions: bool = bool(cfg.get("require_test_mentions", False))
        raw_keywords = cfg.get("mention_keywords") or []
        self.keywords: List[str] = [
            str(word).strip().lower()
            for word in raw_keywords
            if isinstance(word, str) and word.strip()
        ]
        raw_globs = cfg.get("test_file_globs") or []
        self.test_globs: List[str] = [
            str(pattern).strip()
            for pattern in raw_globs
            if isinstance(pattern, str) and pattern.strip()
        ]
        self.execute_tests: bool = bool(cfg.get("execute_tests", False))
        self.test_command: str = str(cfg.get("test_command") or "python -m pytest")
        try:
            self.command_timeout: int = int(cfg.get("command_timeout", 120))
        except (TypeError, ValueError):
            self.command_timeout = 120

    def validate(
        self,
        conversation: Sequence[Dict[str, object]],
        agent_dirs: Dict[str, Optional[str]],
        *,
        context_manager=None,
    ) -> Optional[Dict[str, object]]:
        """Run validation checks against the conversation and project directories."""
        if not self.enabled:
            return None

        if not conversation:
            return None

        consensus_turn = self._find_consensus_turn(conversation)
        if consensus_turn is None:
            return None

        result = {
            "details": {},
            "warnings": [],
            "issues": [],
        }

        mention_info = self._check_test_mentions(conversation)
        result["details"].update(mention_info)
        if self.require_mentions and not mention_info["test_mentions_found"]:
            result["warnings"].append("No test-related language found after consensus.")

        discovery = self._discover_tests(agent_dirs.values())
        result["details"].update(discovery)
        if not discovery["test_files_found"]:
            result["warnings"].append("No test files matching configured patterns were found.")

        if self.execute_tests and discovery["test_directories"]:
            execution = self._run_tests(discovery["test_directories"])
            result["details"]["test_execution"] = execution
            if execution["return_code"] != 0:
                result["issues"].append(
                    f"Automated tests failed (exit code {execution['return_code']})."
                )
        else:
            result["details"]["test_execution"] = {
                "skipped": True,
                "reason": "Execution disabled or no test directories discovered.",
            }

        if context_manager is not None:
            recorder = getattr(context_manager, "record_validation", None)
            if callable(recorder):
                try:
                    recorder(
                        {
                            "consensus_turn": consensus_turn,
                            "warnings": list(result["warnings"]),
                            "issues": list(result["issues"]),
                            "details": result["details"],
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to record validation with context manager: %s", exc)

        if result["warnings"] or result["issues"]:
            report_lines = ["Post-completion validation findings:"]
            for warning in result["warnings"]:
                report_lines.append(f"- WARNING: {warning}")
            for issue in result["issues"]:
                report_lines.append(f"- ISSUE: {issue}")
            logger.warning("\n%s", "\n".join(report_lines))
        else:
            logger.info("Post-completion validation passed with no findings.")

        return result

    def _check_test_mentions(self, conversation: Sequence[Dict[str, object]]) -> Dict[str, object]:
        if not self.keywords:
            return {"test_mentions_found": False, "mentions": []}

        mentions: List[Dict[str, object]] = []
        for turn in conversation:
            response = str(turn.get("response") or "").lower()
            if not response:
                continue

            for keyword in self.keywords:
                if keyword in response:
                    mentions.append(
                        {
                            "turn": turn.get("turn"),
                            "speaker": turn.get("speaker"),
                            "keyword": keyword,
                            "excerpt": self._excerpt(turn.get("response") or "", keyword),
                        }
                    )
                    break

        return {"test_mentions_found": bool(mentions), "mentions": mentions}

    def _discover_tests(self, directories: Iterable[Optional[str]]) -> Dict[str, object]:
        test_dirs: List[str] = []
        test_files: List[str] = []
        for directory in directories:
            if not directory:
                continue

            path = Path(directory).expanduser()
            if not path.exists():
                continue

            dir_matches: List[str] = []
            for pattern in self.test_globs:
                matches = list(glob.glob(pattern, root_dir=path))
                for match in matches:
                    absolute = str(path / match)
                    test_files.append(absolute)
                    dir_matches.append(str(path))

            if dir_matches:
                test_dirs.append(str(path))

        return {
            "test_files_found": bool(test_files),
            "test_files": sorted(set(test_files)),
            "test_directories": sorted(set(test_dirs)),
        }

    def _run_tests(self, directories: Sequence[str]) -> Dict[str, object]:
        directories = list(dict.fromkeys(directories))  # Preserve order, remove duplicates
        command = self.test_command

        for directory in directories:
            try:
                completed = subprocess.run(  # noqa: PLW1510
                    command,
                    shell=True,
                    cwd=directory,
                    timeout=self.command_timeout,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return {
                    "directory": directory,
                    "command": command,
                    "return_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            except subprocess.TimeoutExpired as exc:
                return {
                    "directory": directory,
                    "command": command,
                    "return_code": None,
                    "stdout": exc.stdout,
                    "stderr": exc.stderr or "Timeout expired",
                    "timeout": True,
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "directory": directory,
                    "command": command,
                    "return_code": None,
                    "stdout": "",
                    "stderr": f"Execution failed: {exc}",
                    "error": True,
                }

        return {
            "directory": None,
            "command": command,
            "return_code": None,
            "stdout": "",
            "stderr": "No directories available for execution.",
            "skipped": True,
        }

    @staticmethod
    def _find_consensus_turn(conversation: Sequence[Dict[str, object]]) -> Optional[int]:
        for turn in conversation:
            metadata = turn.get("metadata") or {}
            if isinstance(metadata, dict) and metadata.get("consensus"):
                turn_number = turn.get("turn")
                if isinstance(turn_number, int):
                    return turn_number
                return 0
        return None

    @staticmethod
    def _excerpt(text: str, keyword: str, *, radius: int = 40) -> str:
        """Return a short excerpt around the keyword for clarity."""
        lower_text = text.lower()
        idx = lower_text.find(keyword)
        if idx == -1:
            return textwrap.shorten(text, width=2 * radius, placeholder="…")

        start = max(0, idx - radius)
        end = min(len(text), idx + len(keyword) + radius)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(text) else ""
        return f"{prefix}{text[start:end]}{suffix}"
