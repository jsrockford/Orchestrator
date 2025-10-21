"""
Output Parser

Utilities for parsing and cleaning Claude Code output captured from tmux.
"""

import re
from typing import List, Optional, Dict


class OutputParser:
    """Parse and clean Claude Code output."""

    # ANSI escape code pattern
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    # Unicode box drawing characters used by Claude Code
    BOX_CHARS = ['─', '│', '┌', '┐', '└', '┘', '├', '┤', '┬', '┴', '┼', '═', '║', '╔', '╗', '╚', '╝', '╠', '╣', '╦', '╩', '╬']

    # Additional UI noise patterns
    TOOL_PREFIX_PATTERN = re.compile(r'^\s*⎿\s*')
    COLLAPSED_LINE_PATTERN = re.compile(r'^\s*… \+\d+\s+lines(?:\s*\([^)]+\))?$', re.IGNORECASE)
    SHORTCUT_HINT_PATTERN = re.compile(r'\((?:ctrl|shift|esc)[^)]*\)', re.IGNORECASE)
    PERMISSION_PROMPT_PATTERN = re.compile(r'^\s*⏵⏵')
    STATUS_DOT_PATTERN = re.compile(r'^\s*·\s+')
    STATUS_STAR_PATTERN = re.compile(r'^\s*\*\s+.*esc to interrupt', re.IGNORECASE)
    GEMINI_BOX_BORDER_PATTERN = re.compile(r'^\s*[╭╰]')
    GEMINI_EMPTY_PIPE_PATTERN = re.compile(r'^\s*│\s*$')
    PROMPT_PASTED_PATTERN = re.compile(r'^>\s*\[Pasted text.*\]$', re.IGNORECASE)
    GEMINI_FOOTER_PATTERN = re.compile(r'.*\b(?:gemini|claude)-[\w\.\-]+\b.*', re.IGNORECASE)

    DROP_IF_CONTAINS = (
        'YOLO mode',
        'Type your message',
        'Tips for getting started',
        'Using:',
        'no sandbox',
        'context left',
        'screen reader-friendly view',
        'thinking off',
        'thinking on',
    )

    # Claude Code UI patterns
    PROMPT_PATTERN = r'^>\s'
    SEPARATOR_PATTERN = r'^─+$'
    STATUS_LINE_PATTERN = r'\? for shortcuts.*Thinking (on|off)'
    HEADER_PATTERN = r'▐▛███▜▌.*Claude Code'

    def __init__(self):
        """Initialize OutputParser."""
        pass

    def strip_ansi(self, text: str) -> str:
        """
        Remove ANSI escape codes from text.

        Args:
            text: Input text with ANSI codes

        Returns:
            Text without ANSI codes
        """
        return self.ANSI_ESCAPE.sub('', text)

    def clean_output(self, text: str, strip_ui: bool = True) -> str:
        """
        Clean Claude Code output by removing UI elements.

        Args:
            text: Raw output from tmux capture
            strip_ui: Whether to remove UI elements (header, separators, status)

        Returns:
            Cleaned output text
        """
        # Strip ANSI codes
        text = self.strip_ansi(text)

        if not strip_ui:
            return text

        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            normalized = self._normalize_line(line)
            if normalized is not None:
                cleaned_lines.append(normalized)

        return '\n'.join(cleaned_lines).strip()

    def _normalize_line(self, line: str) -> Optional[str]:
        """Normalize or drop a single line of CLI output."""
        line = line.replace('\u00a0', ' ')
        stripped = line.strip()

        if not stripped:
            return None

        if stripped == '>':
            return None

        # Remove Gemini boxed prompt markers while preserving inner text
        if stripped.startswith('│'):
            inner = stripped.strip('│').strip()
            if not inner:
                return None
            line = inner
            stripped = inner

        # Skip header lines (Claude and Gemini art/logos)
        if any(token in stripped for token in ['▐▛███▜▌', '▝▜█████▛▘', '▘▘ ▝▝', '███']):
            return None

        # Skip broad separator or border lines
        if re.match(self.SEPARATOR_PATTERN, stripped):
            return None
        if self.GEMINI_BOX_BORDER_PATTERN.match(stripped):
            return None
        if self.GEMINI_EMPTY_PIPE_PATTERN.match(stripped):
            return None

        # Skip prompt-only placeholders and pasted text markers
        if re.match(self.PROMPT_PATTERN, stripped) and len(stripped) <= 2:
            return None
        if self.PROMPT_PASTED_PATTERN.match(stripped):
            return None

        # Skip known status/permission lines
        if re.search(self.STATUS_LINE_PATTERN, stripped):
            return None
        if self.PERMISSION_PROMPT_PATTERN.match(stripped):
            return None
        if self.COLLAPSED_LINE_PATTERN.match(stripped):
            return None
        if self.STATUS_DOT_PATTERN.match(stripped):
            return None
        if self.STATUS_STAR_PATTERN.match(stripped):
            return None
        if 'esc to interrupt' in stripped.lower():
            return None

        # Drop lines with configured substrings or footer patterns
        lowered = stripped.lower()
        if any(token.lower() in lowered for token in self.DROP_IF_CONTAINS):
            return None
        if self.GEMINI_FOOTER_PATTERN.match(stripped):
            return None

        # Remove tool prefix indicators but keep the payload
        if stripped.startswith('⎿'):
            stripped = self.TOOL_PREFIX_PATTERN.sub('', stripped).strip()
            if not stripped:
                return None
            line = stripped

        # Remove inline shortcut/tool hints
        line = self.SHORTCUT_HINT_PATTERN.sub('', line).strip()
        stripped = line.strip()
        if not stripped:
            return None

        return line

    def extract_responses(self, text: str) -> List[Dict[str, str]]:
        """
        Extract question/response pairs from AI CLI output.

        Supports both Claude Code (●) and Gemini CLI (✦) response markers.

        Args:
            text: Raw or cleaned output

        Returns:
            List of dictionaries with 'question' and 'response' keys
        """
        text = self.strip_ansi(text)
        lines = text.split('\n')

        pairs = []
        current_question = None
        current_response = []
        in_response = False

        for line in lines:
            stripped = line.strip()

            # Skip box drawing characters
            if stripped.startswith('╭') or stripped.startswith('╰'):
                # Just skip box boundaries - don't save pairs here
                # Pairs will be saved when we encounter the next question
                continue

            # Detect boxed question (Gemini format): │  > Question  │
            if stripped.startswith('│') and '>' in stripped:
                # Extract question from box first
                question_text = stripped.replace('│', '').replace('>', '').strip()

                # Skip prompt line or empty questions
                if not question_text or len(question_text) <= 2 or 'Type your message' in question_text:
                    continue

                # Save previous pair if exists
                if current_question and current_response:
                    pairs.append({
                        'question': current_question,
                        'response': '\n'.join(current_response).strip()
                    })

                # Start new question
                current_question = question_text
                current_response = []
                in_response = False
                continue

            # Detect plain question (Claude format): > Question
            if stripped.startswith('>') and len(stripped) > 2 and not '│' in line:
                # Save previous pair if exists
                if current_question and current_response:
                    pairs.append({
                        'question': current_question,
                        'response': '\n'.join(current_response).strip()
                    })

                # Start new question
                current_question = stripped[1:].strip()
                current_response = []
                in_response = False
                continue

            # Detect response start (● for Claude or ✦ for Gemini)
            if stripped.startswith('●') or stripped.startswith('✦'):
                in_response = True
                # Add response text (without marker)
                response_text = stripped[1:].strip()
                if response_text:
                    current_response.append(response_text)
                continue

            # Skip UI elements
            if (not stripped or
                re.match(self.SEPARATOR_PATTERN, stripped) or
                re.search(self.STATUS_LINE_PATTERN, stripped) or
                any(char in line for char in ['▐▛███▜▌', '▝▜█████▛▘'])):
                # End of response
                if in_response:
                    in_response = False
                continue

            # Collect response continuation lines
            if in_response and stripped:
                current_response.append(stripped)

        # Save last pair if exists
        if current_question and current_response:
            pairs.append({
                'question': current_question,
                'response': '\n'.join(current_response).strip()
            })

        return pairs

    def get_last_response(self, text: str) -> Optional[str]:
        """
        Extract just the last response from output.

        Args:
            text: Raw or cleaned output

        Returns:
            Last response text or None
        """
        pairs = self.extract_responses(text)
        if pairs:
            return pairs[-1]['response']
        return None

    def get_last_question(self, text: str) -> Optional[str]:
        """
        Extract just the last question from output.

        Args:
            text: Raw or cleaned output

        Returns:
            Last question text or None
        """
        pairs = self.extract_responses(text)
        if pairs:
            return pairs[-1]['question']
        return None

    def is_error_response(self, text: str) -> bool:
        """
        Detect if response contains an error.

        Args:
            text: Response text

        Returns:
            True if error detected, False otherwise
        """
        error_patterns = [
            r'error',
            r'failed',
            r'cannot',
            r'unable to',
            r'not found',
            r'invalid',
        ]

        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in error_patterns)

    def format_conversation(self, text: str) -> str:
        """
        Format conversation in a readable way.

        Args:
            text: Raw output

        Returns:
            Formatted conversation
        """
        pairs = self.extract_responses(text)

        formatted = []
        for i, pair in enumerate(pairs, 1):
            formatted.append(f"Q{i}: {pair['question']}")
            formatted.append(f"A{i}: {pair['response']}")
            formatted.append("")  # Blank line between pairs

        return '\n'.join(formatted).strip()
