"""
UnitTestAgent — checks whether the change's tests actually pass.

Reuses the SAME test tool the original single-agent build used
(tools/test_runner.py). See unit_test_agent.skills.md for scope.
"""
from __future__ import annotations
from decimal import Decimal

from agents.base_agent import SpecialistAgent
from tools.test_runner import run_tests


class UnitTestAgent(SpecialistAgent):
    agent_id = "unit-test-agent"
    agent_version = "unit-test-agent-v1.0.0"
    skill_id = "skill-test-coverage"

    def run(self):
        self._log("── UNIT TEST AGENT ──")
        approved = self.check_tools(["read_repo", "run_tests"])
        if "run_tests" not in approved:
            self.state.decision = "blocked"
            return self.state

        all_passed, output, passed_count, failed_count = run_tests(self.repo_path)
        self._log(f"pytest result: {passed_count} passed, {failed_count} failed")

        # tokens_used is tracked for real inside reflect_with_possible_loop().
        # cost_incurred below is still a placeholder — see code_agent.py's
        # comment for why it's deliberately not computed here yet.
        self.state.cost_incurred += Decimal("0.12")

        if not all_passed:
            self._write_status("run_tests", "blocked", f"{failed_count} test(s) failed")
            self._log("real test failures — stopping, not escalating a broken change")
            self.state.decision = "blocked"
            return self.state
        self._write_status("run_tests", "passed", f"{passed_count} passed, {failed_count} failed")

        self.reflect_with_possible_loop(
            output, "(unit test run — no lint evidence available to this agent)",
            loop_reason="a passing test run alone doesn't confirm coverage quality",
        )
        self.decide()
        self.emit_final_telemetry()
        return self.state
