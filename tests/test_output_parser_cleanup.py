import pytest

from src.utils.output_parser import OutputParser


RAW_SNIPPET = """
⎿  total 96
    … +12 lines (ctrl+o to expand)
⎿  Read 1014 lines (ctrl+o to expand)
· Assessing current implementation status… (esc to interrupt · ctrl+t to show todos)
⏵⏵ bypass permissions on (shift+tab to cycle)
╭────────────────────╮
│  > What is 2 + 2?  │
╰────────────────────╯
│  > Type your message or @path/to/file  │
╰────────────────────╯
> [Pasted text #1 +56 lines]
Using: 2 GEMINI.md files
YOLO mode (ctrl + y to toggle)
/mnt/path (session*) no sandbox (see /docs)  gemini-2.5-pro (99% context left)
● Answer begins
  This is the payload line.
"""

CODEX_SNIPPET = """
› In two sentences, explain the testing plan.

• Capture raw transcripts for ground truth integrity.
  Compare the cleaned parser output to ensure we only transformed UI chrome.

› Summarize recent commits
  100% context left · ? for shortcuts
"""

CODE_BLOCK_SNIPPET = """
> Provide a tiny Python helper.

● Here's a quick function:
  def add(a, b):
      return a + b
"""


@pytest.fixture
def parser():
    return OutputParser()


def test_clean_output_removes_known_ui_noise(parser):
    cleaned = parser.clean_output(RAW_SNIPPET)

    assert 'Assessing current implementation status' not in cleaned
    assert 'bypass permissions' not in cleaned
    assert 'YOLO mode' not in cleaned
    assert 'no sandbox' not in cleaned
    assert 'Type your message' not in cleaned
    assert '[Pasted text' not in cleaned
    assert '… +12 lines' not in cleaned
    assert '⎿' not in cleaned


def test_clean_output_preserves_payload_lines(parser):
    cleaned = parser.clean_output(RAW_SNIPPET)

    assert 'total 96' in cleaned
    assert 'Read 1014 lines' in cleaned
    assert '> What is 2 + 2?' in cleaned
    assert 'Answer begins' in cleaned
    assert 'This is the payload line.' in cleaned


def test_clean_output_can_strip_trailing_prompts(parser):
    default_cleaned = parser.clean_output(CODEX_SNIPPET)
    trimmed_cleaned = parser.clean_output(CODEX_SNIPPET, strip_trailing_prompts=True)

    assert '› Summarize recent commits' in default_cleaned
    assert '› Summarize recent commits' not in trimmed_cleaned
    assert '› In two sentences, explain the testing plan.' in trimmed_cleaned


def test_extract_responses_handles_codex_prompt_and_bullet(parser):
    pairs = parser.extract_responses(CODEX_SNIPPET)

    assert len(pairs) == 1
    assert pairs[0]['question'] == 'In two sentences, explain the testing plan.'
    assert 'Capture raw transcripts' in pairs[0]['response']


def test_clean_output_preserves_indentation(parser):
    cleaned = parser.clean_output(CODE_BLOCK_SNIPPET)

    assert '  def add(a, b):' in cleaned
    assert '      return a + b' in cleaned


def test_split_prompt_and_response_returns_last_pair(parser):
    snippet = """
> Summarize the Fibonacci sequence in one sentence.

● The Fibonacci sequence starts with 0 and 1, and each subsequent number is the sum of the previous two.
"""
    parsed = parser.split_prompt_and_response(snippet)

    assert parsed.prompt == 'Summarize the Fibonacci sequence in one sentence.'
    assert 'Fibonacci sequence starts with 0 and 1' in parsed.response
    assert 'Summarize the Fibonacci sequence' in parsed.cleaned_output


def test_split_prompt_and_response_handles_fallback(parser):
    snippet = """
> Provide a quick status update.

The deployment succeeded and all services are healthy.
"""
    parsed = parser.split_prompt_and_response(snippet)

    assert parsed.prompt == 'Provide a quick status update.'
    assert parsed.response == 'The deployment succeeded and all services are healthy.'


def test_split_prompt_and_response_keeps_multiline_response(parser):
    snippet = """
> qwen, draft a short agenda for the sync.

✦ Here's a quick agenda:
  1. Review open blockers
  2. Confirm deployment timeline
  3. Assign follow-up owners
"""
    parsed = parser.split_prompt_and_response(snippet)

    assert parsed.prompt == 'qwen, draft a short agenda for the sync.'
    assert parsed.response.splitlines()[0] == "Here's a quick agenda:"
    assert '2. Confirm deployment timeline' in parsed.response
