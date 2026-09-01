"""
Verifies CodeAgent sends Claude the REAL fix history when a lint failure
happened and was auto-fixed — not just the sanitized final passing
output, which used to make a fixed file indistinguishable from a file
that never had a problem.
"""
from unittest.mock import patch
from decimal import Decimal
from dewa_observability.sdk import ObservabilityClient
from dewa_observability.harness_guard import HarnessGuard, HarnessPolicy
from agents.code_agent import CodeAgent


def _guard():
    obs = ObservabilityClient(harness_version="v1")
    policy = HarnessPolicy(harness_version="v1", max_retries=3, cost_budget=Decimal("2.00"),
        token_budget=50000, allowed_tools={"read_repo", "run_lint"},
        confidence_threshold=0.70, max_reasoning_loops=2)
    return HarnessGuard(policy, obs), obs


def _agent(guard, obs, repo_path):
    return CodeAgent(guard=guard, obs=obs, model_id="m",
        work_item={"work_item_id": "wi-1", "process_id": "p", "initiative_id": "i", "division_id": "d"},
        requesting_user_id="test", repo_path=repo_path, target_file="calculator.py")


def test_evidence_includes_fix_history_when_a_bug_was_fixed(tmp_path):
    calc = tmp_path / "calculator.py"
    calc.write_text('"""doc"""\nimport os\nimport math\n\n\ndef add(a, b):\n    return a + b\n')

    guard, obs = _guard()
    captured = {}

    def fake_confidence(evidence_a, evidence_b):
        captured["evidence_a"] = evidence_a
        return (0.9, "offline", 0)

    with patch("agents.base_agent.get_model_confidence", side_effect=fake_confidence):
        _agent(guard, obs, str(tmp_path)).run()

    assert "Initial lint FAILED" in captured["evidence_a"]
    assert "Auto-fix applied" in captured["evidence_a"]
    assert "Final lint after fix" in captured["evidence_a"]


def test_evidence_is_unchanged_when_no_bug_existed(tmp_path):
    calc = tmp_path / "calculator.py"
    calc.write_text('"""doc"""\nimport math\n\n\ndef add(a, b):\n    return math.floor(a + b)\n')

    guard, obs = _guard()
    captured = {}

    def fake_confidence(evidence_a, evidence_b):
        captured["evidence_a"] = evidence_a
        return (0.9, "offline", 0)

    with patch("agents.base_agent.get_model_confidence", side_effect=fake_confidence):
        _agent(guard, obs, str(tmp_path)).run()

    assert captured["evidence_a"] == "(no issues)"
    assert "Initial lint FAILED" not in captured["evidence_a"]
