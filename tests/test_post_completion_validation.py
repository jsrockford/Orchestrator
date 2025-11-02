from __future__ import annotations

import tempfile
from pathlib import Path

from src.orchestrator.context_manager import ContextManager
from src.orchestrator.validation import PostCompletionValidator
from src.utils.config_loader import reload_config


def _sample_conversation(include_tests: bool = False, consensus: bool = True):
    conversation = [
        {"turn": 0, "speaker": "gemini", "response": "Initial plan."},
        {"turn": 1, "speaker": "qwen", "response": "Implementation draft ready."},
    ]
    if include_tests:
        conversation.append(
            {
                "turn": 2,
                "speaker": "gemini",
                "response": "I ran pytest and all tests passed.",
            }
        )
    if consensus:
        conversation.append(
            {
                "turn": 3,
                "speaker": "gemini",
                "response": "[[PROJECT_COMPLETE]] Work complete.",
                "metadata": {"consensus": True},
            }
        )
    return conversation


def test_validator_warns_when_no_tests_found():
    reload_config()
    validator = PostCompletionValidator(
        {
            "enabled": True,
            "require_test_mentions": True,
            "mention_keywords": ["test"],
            "test_file_globs": ["test_*.py"],
            "execute_tests": False,
        }
    )

    conversation = _sample_conversation(include_tests=False)
    result = validator.validate(conversation, {"qwen": None})

    assert result is not None
    assert result["warnings"]
    assert any("No test-related language" in warning for warning in result["warnings"])
    assert result["details"]["test_files_found"] is False


def test_validator_passes_with_mentions_and_files():
    reload_config()
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "test_example.py").write_text("def test_example():\n    assert True\n", encoding="utf-8")

        validator = PostCompletionValidator(
            {
                "enabled": True,
                "require_test_mentions": True,
                "mention_keywords": ["pytest"],
                "test_file_globs": ["test_*.py"],
                "execute_tests": False,
            }
        )

        conversation = _sample_conversation(include_tests=True)
        result = validator.validate(conversation, {"qwen": tmpdir})

        assert result is not None
        assert not result["warnings"]
        assert not result["issues"]
        assert result["details"]["test_mentions_found"] is True
        assert result["details"]["test_files_found"] is True


def test_validator_records_with_context_manager():
    reload_config()
    validator = PostCompletionValidator(
        {
            "enabled": True,
            "require_test_mentions": False,
            "mention_keywords": ["test"],
            "test_file_globs": ["test_*.py"],
            "execute_tests": False,
        }
    )
    conversation = _sample_conversation(include_tests=False)
    context_manager = ContextManager()

    validator.validate(conversation, {"gemini": None}, context_manager=context_manager)

    assert context_manager.validations
    latest = context_manager.validations[-1]
    assert latest["consensus_turn"] == 3
    assert "details" in latest
