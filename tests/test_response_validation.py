import pytest

from src.utils.output_parser import OutputParser, ParsedOutput


@pytest.fixture
def parser():
    return OutputParser()


def test_validate_response_strips_noise_and_stays_valid(parser):
    response_body = "Here is a sufficiently long response body that exceeds twenty characters."
    parsed = ParsedOutput(
        prompt="Provide status",
        response=response_body,
        cleaned_output="Gemini CLI update available! 0.11.0 → 0.11.2\n"
        "Installed with npm. Attempting to automatically update now...\n"
        f"{response_body}",
        raw_output=None,
    )

    result = parser.validate_response(parsed, "gemini")

    assert result.valid is True
    assert result.should_retry is False
    assert "CLI update available" in result.ignored_patterns
    assert "Installed with npm" in result.ignored_patterns
    assert "Attempting to automatically update" in result.ignored_patterns
    # Cleaned output should no longer include the noise snippets.
    assert "CLI update available" not in result.cleaned_output
    assert "Attempting to automatically update" not in result.cleaned_output
    assert response_body in result.cleaned_output
    assert result.response_text == response_body


def test_validate_response_flags_configured_errors(parser):
    parsed = ParsedOutput(
        prompt="Check status",
        response="Rate limit exceeded while calling API.",
        cleaned_output="Rate limit exceeded while calling API.",
        raw_output="Rate limit exceeded while calling API.",
    )

    result = parser.validate_response(parsed, "claude")

    assert result.valid is False
    assert result.should_retry is True
    assert any(issue.startswith("error_pattern:") for issue in result.issues)


def test_validate_response_detects_missing_body(parser):
    parsed = ParsedOutput(
        prompt="Summarize findings",
        response=None,
        cleaned_output="Summarize findings\n\n",
        raw_output=None,
    )

    result = parser.validate_response(parsed, "codex")

    assert result.valid is False
    assert result.should_retry is True
    assert "response_marker_missing" in result.issues
    assert "empty_output" in result.issues
