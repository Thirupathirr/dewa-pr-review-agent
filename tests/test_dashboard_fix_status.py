"""
Verifies CodeAgent writes a real, correctly-labeled dashboard entry for
the fix_applied step — the "Fuller" dashboard integration, distinct
from the reflect-evidence fix (a different consumer of the same data).
"""
import json
from unittest.mock import patch
from decimal import Decimal
from dewa_observability.sdk import ObservabilityClient
from dewa_observability.harness_guard import HarnessGuard, HarnessPolicy
from agents.code_agent import CodeAgent
import agents.base_agent as base_agent_module


def _guard():
    obs = ObservabilityClient(harness_version="v1")
    policy = HarnessPolicy(harness_version="v1", max_retries=3, cost_budget=Decimal("2.00"),
        token_budget=50000, allowed_tools={"read_repo", "run_lint"},
        confidence_threshold=0.70, max_reasoning_loops=2)
    return HarnessGuard(policy, obs), obs


def test_dashboard_shows_fixed_status_with_real_fixer_name(tmp_path, monkeypatch):
    run_log = tmp_path / "run_log.json"
    monkeypatch.setattr(base_agent_module, "RUN_LOG_PATH", run_log)

    calc = tmp_path / "calculator.py"
    calc.write_text('"""doc"""\nimport math\nimport math\n\n\ndef f(x):\n    return math.floor(x)\n')

    guard, obs = _guard()
    with patch("agents.base_agent.get_model_confidence", return_value=(0.9, "offline", 0)):
        agent = CodeAgent(guard=guard, obs=obs, model_id="m",
            work_item={"work_item_id": "wi-1", "process_id": "p", "initiative_id": "i", "division_id": "d"},
            requesting_user_id="test", repo_path=str(tmp_path), target_file="calculator.py")
        agent.run()

    entries = json.loads(run_log.read_text())
    fix_entries = [e for e in entries if e.get("step") == "fix_applied"]
    assert len(fix_entries) == 1
    assert fix_entries[0]["status"] == "fixed"
    assert "duplicate import" in fix_entries[0]["detail"]
    assert fix_entries[0]["agent_id"] == "code-agent"  # complete schema, not the old stripped-down one


def test_dashboard_shows_not_needed_when_file_was_already_clean(tmp_path, monkeypatch):
    run_log = tmp_path / "run_log.json"
    monkeypatch.setattr(base_agent_module, "RUN_LOG_PATH", run_log)

    calc = tmp_path / "calculator.py"
    calc.write_text('"""doc"""\nimport math\n\n\ndef f(x):\n    return math.floor(x)\n')

    guard, obs = _guard()
    with patch("agents.base_agent.get_model_confidence", return_value=(0.9, "offline", 0)):
        agent = CodeAgent(guard=guard, obs=obs, model_id="m",
            work_item={"work_item_id": "wi-1", "process_id": "p", "initiative_id": "i", "division_id": "d"},
            requesting_user_id="test", repo_path=str(tmp_path), target_file="calculator.py")
        agent.run()

    entries = json.loads(run_log.read_text())
    fix_entries = [e for e in entries if e.get("step") == "fix_applied"]
    assert len(fix_entries) == 1
    assert fix_entries[0]["status"] == "passed"  # not "fixed" — nothing was actually fixed
    assert "not needed" in fix_entries[0]["detail"]
