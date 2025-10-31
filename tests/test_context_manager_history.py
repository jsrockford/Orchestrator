from src.orchestrator.context_manager import ContextManager


def test_build_prompt_uses_sanitized_history():
    manager = ContextManager()
    manager.record_turn(
        {
            "turn": 0,
            "speaker": "qwen",
            "response": "Agenda is prepared and shared.",
            "response_prompt": "qwen, draft a short agenda for the sync.",
            "response_transcript": "> qwen, draft a short agenda for the sync.\n\n✦ Agenda is prepared and shared.",
        }
    )

    prompt = manager.build_prompt("claude", "Review agenda")

    assert "Recent context: qwen: Agenda is prepared and shared." in prompt
    assert "draft a short agenda" not in prompt


def test_build_prompt_excludes_speakers_own_prior_turns():
    manager = ContextManager()
    manager.record_turn({"turn": 0, "speaker": "claude", "response": "Initial plan drafted."})
    manager.record_turn({"turn": 1, "speaker": "qwen", "response": "Proposed refinements sent."})

    prompt_for_claude = manager.build_prompt("claude", "Continue refinement")

    assert "qwen: Proposed refinements sent." in prompt_for_claude
    assert "claude: Initial plan drafted." not in prompt_for_claude


def test_build_prompt_includes_history_for_first_time_speaker():
    manager = ContextManager()
    manager.record_turn({"turn": 0, "speaker": "claude", "response": "Kickoff summary."})

    prompt_for_gemini = manager.build_prompt("gemini", "Pick up next steps")

    assert "claude: Kickoff summary." in prompt_for_gemini
