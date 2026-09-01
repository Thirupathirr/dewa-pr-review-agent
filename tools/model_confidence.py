"""
The ONE place a model gets called in this whole agent — everything else
(lint, tests) is a real tool producing a real fact. This is the only
genuine reasoning question: "given these real results, how confident
are you this is safe to merge?"

Checks in order: real Claude API -> real Azure OpenAI -> honest offline
fallback. Whichever one actually ran is labeled in the output, so a demo
run is never mistaken for a real judgment.
"""
import os
import random


def get_model_confidence(lint_output: str, test_output: str) -> tuple[float, str, int]:
    """Returns (confidence, mode, tokens_used).
    tokens_used is the REAL input+output token count from the API response
    for 'claude'/'azure' modes, or 0 for 'offline' — there is no real call
    to measure in offline mode, so reporting anything else would be another
    invented number."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        confidence, tokens = _claude_call(lint_output, test_output)
        return confidence, "claude", tokens

    if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
        confidence, tokens = _azure_call(lint_output, test_output)
        return confidence, "azure", tokens

    return _offline_fallback(), "offline", 0


def _prompt(lint_output: str, test_output: str) -> str:
    return (
        "You are reviewing a pull request. Based on the real lint and test "
        "output below, respond with ONLY a number between 0 and 1 "
        "representing your confidence this PR is safe to merge. No other "
        f"text.\n\nLint output:\n{lint_output}\n\nTest output:\n{test_output}"
    )


def _claude_call(lint_output: str, test_output: str) -> tuple[float, int]:
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from environment
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=10,
        messages=[{"role": "user", "content": _prompt(lint_output, test_output)}],
    )
    raw = response.content[0].text.strip()
    # response.usage is REAL data from Anthropic's own API — this was being
    # discarded before; input + output is the true token cost of this call.
    real_tokens = response.usage.input_tokens + response.usage.output_tokens
    return _parse_confidence(raw), real_tokens


def _azure_call(lint_output: str, test_output: str) -> tuple[float, int]:
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version="2024-06-01",
    )
    response = client.chat.completions.create(
        model="claude-sonnet-5",
        messages=[{"role": "user", "content": _prompt(lint_output, test_output)}],
        max_tokens=10,
    )
    raw = response.choices[0].message.content.strip()
    real_tokens = response.usage.total_tokens if response.usage else 0
    return _parse_confidence(raw), real_tokens


def _parse_confidence(raw: str) -> float:
    import re
    match = re.search(r"0?\.\d+|[01](?:\.0+)?", raw)
    if not match:
        raise ValueError(f"Could not parse a confidence value from model output: {raw!r}")
    return max(0.0, min(1.0, float(match.group())))


def _offline_fallback() -> float:
    return round(random.uniform(0.55, 0.95), 2)
