"""
PRReviewAgent v2 — touches a real repo now.

lint and tests are REAL subprocess calls against REAL files in
target_repo/. Only the confidence step is model-based, and even that is
honestly labeled real vs. offline depending on whether Azure credentials
are configured.

PLAN   -> which tools does it need, checked against the harness
ACT    -> really run pyflakes, really apply a fix, really run pytest
REFLECT -> get a real (or honestly-labeled offline) confidence score
DECIDE -> the agent wants to approve; the harness has the final say
"""
from __future__ import annotations
from decimal import Decimal
from dataclasses import dataclass, field

from dewa_observability.sdk import ObservabilityClient
from dewa_observability.harness_guard import HarnessGuard, PolicyViolation

from tools.linter import run_lint, auto_fix_unused_imports
from tools.test_runner import run_tests
from tools.model_confidence import get_model_confidence


@dataclass
class AgentState:
    retry_attempts: int = 0
    lint_passed: bool = False
    lint_output: str = ""
    test_output: str = ""
    tokens_used: int = 0
    cost_incurred: Decimal = field(default_factory=lambda: Decimal("0"))
    confidence: float | None = None
    confidence_mode: str | None = None  # "real" or "offline"
    decision: str | None = None


class PRReviewAgent:
    def __init__(self, guard: HarnessGuard, obs: ObservabilityClient, *,
                 agent_id: str, skill_id: str, model_id: str,
                 work_item: dict, requesting_user_id: str, repo_path: str,
                 target_file: str):
        self.guard = guard
        self.obs = obs
        self.agent_id = agent_id
        self.skill_id = skill_id
        self.model_id = model_id
        self.work_item = work_item
        self.requesting_user_id = requesting_user_id
        self.repo_path = repo_path
        self.target_file = target_file
        self.state = AgentState()

    def _log(self, msg: str):
        print(f"  {msg}")

    def _trace_back(self, **overrides) -> dict:
        base = {
            "user_id": self.requesting_user_id,
            "agent_id": self.agent_id,
            "skill_id": self.skill_id,
            "model_id": self.model_id,
            **self.work_item,
            "outcome_ref": f"outcome-{self.work_item['work_item_id']}",
            "tokens": self.state.tokens_used,
            "cost": str(self.state.cost_incurred),
            "transaction_id": f"txn-{self.work_item['work_item_id']}",
        }
        base.update(overrides)
        return base

    # ================= PLAN =================
    def plan(self) -> list[str]:
        self._log("── PLAN ──")
        needed_tools = ["read_repo", "run_lint", "run_tests"]
        approved = []
        for tool in needed_tools:
            tb = self._trace_back()
            try:
                self.guard.check_tool_access(tb, tool_name=tool)
                self._log(f"tool '{tool}': harness approved")
                approved.append(tool)
            except PolicyViolation as e:
                self._log(f"tool '{tool}': harness BLOCKED — {e}")
        return approved

    # ================= ACT: real lint, real fix, real retry =================
    def act_lint(self) -> bool:
        self._log("── ACT: lint (real pyflakes) ──")
        while not self.state.lint_passed:
            self.state.retry_attempts += 1
            passed, output = run_lint(self.repo_path, self.target_file)
            self.state.lint_output = output
            self._log(f"attempt {self.state.retry_attempts}: "
                      f"{'PASSED' if passed else 'FAILED'} — {output}")

            if passed:
                self.state.lint_passed = True
                break

            tb = self._trace_back()
            try:
                self.guard.check_retry(tb, work_item_id=self.work_item["work_item_id"],
                                        retry_reason=f"lint_failed: {output}")
            except PolicyViolation as e:
                self._log(f"harness BLOCKED further retries — {e}")
                self.state.decision = "blocked"
                return False

            fixed = auto_fix_unused_imports(self.repo_path, self.target_file, output)
            if fixed:
                self._log("applied real auto-fix (removed unused import) to the real file")
            else:
                self._log("no automated fix available for this issue")
                self.state.decision = "blocked"
                return False
        return True

    # ================= ACT: real tests =================
    def act_run_tests(self) -> bool:
        self._log("── ACT: tests (real pytest) ──")
        all_passed, output, passed_count, failed_count = run_tests(self.repo_path)
        self.state.test_output = output
        self._log(f"pytest result: {passed_count} passed, {failed_count} failed")

        # illustrative cost — real token accounting would come from the
        # actual model call in reflect(); this represents tool-call overhead
        tokens, cost = 1800, Decimal("0.32")
        self.state.tokens_used += tokens
        self.state.cost_incurred += cost

        tb = self._trace_back()
        try:
            self.guard.check_budget(tb, work_item_id=self.work_item["work_item_id"],
                                     additional_cost=cost)
        except PolicyViolation as e:
            self._log(f"harness BLOCKED — {e}")
            self.state.decision = "blocked"
            return False

        if not all_passed:
            self._log("real test failures — stopping, not escalating a broken PR")
            self.state.decision = "blocked"
            return False
        return True

    # ================= REFLECT: the one real/offline model spot =================
    def reflect(self):
        self._log("── REFLECT ──")
        confidence, mode = get_model_confidence(self.state.lint_output, self.state.test_output)
        self.state.confidence = confidence
        self.state.confidence_mode = mode
        labels = {
            "claude": "REAL Claude API call",
            "azure": "REAL Azure OpenAI call",
            "offline": "OFFLINE fallback (no API key set)",
        }
        label = labels.get(mode, mode)
        self._log(f"confidence: {confidence}  [{label}]")

    # ================= DECIDE =================
    def decide(self):
        self._log("── DECIDE ──")
        self._log(f"agent WANTS to: auto-approve (confidence={self.state.confidence})")
        tb = self._trace_back()
        try:
            self.guard.check_confidence(tb, confidence=self.state.confidence)
            self._log("harness agrees — confidence clears threshold")
            self.state.decision = "approved"
        except PolicyViolation as e:
            self._log(f"harness OVERRULES the agent — {e}")
            self.state.decision = "escalated"

    def _emit_final_telemetry(self):
        tb = self._trace_back()
        self.obs.emit_quality(tb, accuracy=self.state.confidence,
                               first_time_right=(self.state.retry_attempts == 1))
        self.obs.emit_productivity(tb, response_time_ms=1500,
                                    cycle_time_ms=self.state.retry_attempts * 30000)
        self.obs.emit_cost(
            tb,
            tokens_per_successful_outcome=self.state.tokens_used,
            cost_per_successful_outcome=self.state.cost_incurred,
            retry_token_ratio=round(
                (self.state.retry_attempts - 1) / max(self.state.retry_attempts, 1), 2),
            wasted_token_ratio=Decimal("0.00"),
            budget_variance=(self.guard.policy.cost_budget - self.state.cost_incurred),
        )
        self.obs.emit_outcome(
            tb,
            successful_outcome=(self.state.decision == "approved"),
            value_contribution=Decimal("300.00") if self.state.decision == "approved" else Decimal("0.00"),
        )

    def run(self) -> AgentState:
        self._log(f"Agent {self.agent_id} starting on "
                  f"{self.work_item['work_item_id']} — real repo: {self.repo_path}")

        tb = self._trace_back()
        self.obs.emit_compliance(
            tb, compliance_score=1.0, quality_procedure_id="QP-CODE-007",
            compliance_checkpoint="pre-review-gate",
            audit_evidence_ref=f"audit://run/{self.work_item['work_item_id']}",
        )

        tools = self.plan()
        if "run_lint" not in tools:
            self.state.decision = "blocked"
            return self.state

        if not self.act_lint():
            return self.state
        if not self.act_run_tests():
            return self.state

        self.reflect()
        self.decide()
        self._emit_final_telemetry()

        self._log(f"── FINAL: {self.state.decision} ──")
        return self.state
