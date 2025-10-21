from pathlib import Path

import pytest

from examples.run_code_review_simulation import (
    InclusionStrategy,
    _format_display_path,
    build_topic,
    determine_inclusion_strategy,
)


def test_determine_strategy_small_file_embeds():
    strategy = determine_inclusion_strategy(
        line_count=10,
        size_bytes=200,
        embed_threshold=50,
        reference_threshold=100,
        size_threshold=5000,
    )
    assert strategy is InclusionStrategy.EMBED_FULL


def test_determine_strategy_medium_file_hybrid():
    strategy = determine_inclusion_strategy(
        line_count=75,
        size_bytes=3200,
        embed_threshold=50,
        reference_threshold=100,
        size_threshold=5000,
    )
    assert strategy is InclusionStrategy.HYBRID


def test_determine_strategy_large_file_reference_only():
    strategy = determine_inclusion_strategy(
        line_count=150,
        size_bytes=4100,
        embed_threshold=50,
        reference_threshold=100,
        size_threshold=5000,
    )
    assert strategy is InclusionStrategy.REFERENCE_ONLY


def test_determine_strategy_respects_size_threshold():
    strategy = determine_inclusion_strategy(
        line_count=40,
        size_bytes=6000,
        embed_threshold=50,
        reference_threshold=100,
        size_threshold=5000,
    )
    assert strategy is InclusionStrategy.REFERENCE_ONLY


@pytest.fixture()
def snippet_path(tmp_path: Path) -> Path:
    path = tmp_path / "example.py"
    path.write_text("print('hello')\nprint('world')\nprint('!')\n", encoding="utf-8")
    return path


def test_build_topic_embed_includes_code(snippet_path: Path):
    lines = ["print('hello')", "print('world')", "print('!')"]
    topic = build_topic(
        snippet_path,
        "TURN PLAN",
        lines,
        strategy=InclusionStrategy.EMBED_FULL,
        preview_lines=5,
    )
    display_path = _format_display_path(snippet_path)
    assert "```python" in topic
    assert "print('hello')" in topic
    assert f"@{display_path}" in topic


def test_build_topic_hybrid_shows_preview(snippet_path: Path):
    lines = [f"line_{idx}" for idx in range(10)]
    topic = build_topic(
        snippet_path,
        "TURN PLAN",
        lines,
        strategy=InclusionStrategy.HYBRID,
        preview_lines=3,
    )
    assert "Preview (first 3 of 10 lines shown)" in topic
    assert "(Preview truncated after 3 of 10 lines.)" in topic
    assert "```python" in topic


def test_build_topic_reference_only_has_no_code_block(snippet_path: Path):
    lines = [f"line_{idx}" for idx in range(5)]
    topic = build_topic(
        snippet_path,
        "TURN PLAN",
        lines,
        strategy=InclusionStrategy.REFERENCE_ONLY,
        preview_lines=3,
    )
    assert "```python" not in topic
    assert f"@{_format_display_path(snippet_path)}" in topic
