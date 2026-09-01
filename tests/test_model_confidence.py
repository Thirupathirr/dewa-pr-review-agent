"""Verifies get_model_confidence() extracts REAL token counts from the
API response, rather than discarding them — the bug fixed on 2026-09-01."""
from unittest.mock import MagicMock, patch


def test_offline_mode_reports_zero_tokens_honestly():
    from tools.model_confidence import get_model_confidence
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("AZURE_OPENAI_API_KEY", None)
    confidence, mode, tokens = get_model_confidence("lint", "test")
    assert mode == "offline"
    assert tokens == 0  # no real call happened — 0 is honest, not a guess


def test_claude_call_extracts_real_input_plus_output_tokens():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="0.82")]
    mock_response.usage.input_tokens = 145
    mock_response.usage.output_tokens = 3

    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = mock_response
        from tools.model_confidence import _claude_call
        confidence, tokens = _claude_call("lint output", "test output")
        assert confidence == 0.82
        assert tokens == 148  # 145 + 3, not discarded
