"""
Verifies the second auto-fix — duplicate imports — added alongside the
original unused-import fix, both tried in order via CodeAgent.FIXERS.
"""
from unittest.mock import patch
from decimal import Decimal
from dewa_observability.sdk import ObservabilityClient
from dewa_observability.harness_guard import HarnessGuard, HarnessPolicy
from agents.code_agent import CodeAgent
from tools.linter import auto_fix_duplicate_imports, run_lint


def _guard():
    obs = ObservabilityClient(harness_version="v1")
    policy = HarnessPolicy(harness_version="v1", max_retries=3, cost_budget=Decimal("2.00"),
        token_budget=50000, allowed_tools={"read_repo", "run_lint"},
        confidence_threshold=0.70, max_reasoning_loops=2)
    return HarnessGuard(policy, obs), obs


def test_duplicate_import_is_detected_and_only_the_duplicate_is_removed(tmp_path):
    calc = tmp_path / "calculator.py"
    calc.write_text('"""doc"""\nimport math\nimport math\n\n\ndef f(x):\n    return math.floor(x)\n')

    passed, output = run_lint(str(tmp_path), "calculator.py")
    assert not passed
    assert "redefinition of unused" in output

    fixed = auto_fix_duplicate_imports(str(tmp_path), "calculator.py", output)
    assert fixed is True

    content = calc.read_text()
    assert content.count("import math") == 1  # duplicate gone, original kept

    passed_after, _ = run_lint(str(tmp_path), "calculator.py")
    assert passed_after  # genuinely clean now, verified by a real second lint run


def test_duplicate_fixer_does_not_fire_on_unrelated_errors():
    from tools.linter import auto_fix_duplicate_imports
    fixed = auto_fix_duplicate_imports("irrelevant", "irrelevant.py",
                                        "'os' imported but unused")
    assert fixed is False  # wrong pattern — must not match a different issue type


def test_code_agent_labels_the_evidence_with_the_real_fixer_used(tmp_path):
    calc = tmp_path / "calculator.py"
    calc.write_text('"""doc"""\nimport math\nimport math\n\n\ndef f(x):\n    return math.floor(x)\n')

    guard, obs = _guard()
    captured = {}

    def fake_confidence(evidence_a, evidence_b):
        captured["evidence_a"] = evidence_a
        return (0.9, "offline", 0)

    with patch("agents.base_agent.get_model_confidence", side_effect=fake_confidence):
        agent = CodeAgent(guard=guard, obs=obs, model_id="m",
            work_item={"work_item_id": "wi-1", "process_id": "p", "initiative_id": "i", "division_id": "d"},
            requesting_user_id="test", repo_path=str(tmp_path), target_file="calculator.py")
        agent.run()

    assert "duplicate import" in captured["evidence_a"]
    assert "unused import" not in captured["evidence_a"]  # must name the RIGHT fixer, not the other one
