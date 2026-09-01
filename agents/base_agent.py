"""
Shared base for the specialist sub-agents (Code, Unit Test, Security).

Factors out ONLY what is genuinely identical across all three: building
a trace_back, writing to the shared dashboard log, and the one real
reasoning-loop demonstration around the model-confidence call. Each
specialist still implements its own PLAN/ACT sequence in its own file —
this is not a framework, just shared plumbing.
"""
from __future__ import annotations
from decimal import Decimal
from dataclasses import dataclass, field
import json
import time
from pathlib import Path

from dewa_observability.harness_guard import HarnessGuard, PolicyViolation
from dewa_observability.sdk import ObservabilityClient
from tools.model_confidence import get_model_confidence

RUN_LOG_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "run_log.json"


@dataclass
class SpecialistState:
    tokens_used: int = 0
    cost_incurred: Decimal = field(default_factory=lambda: Decimal("0"))
    confidence: float | None = None
    confidence_mode: str | None = None
    reasoning_loops_used: int = 0
    decision: str | None = None  # "approved" | "escalated" | "blocked"


class SpecialistAgent:
    """Not used directly — CodeAgent / UnitTestAgent / SecurityAgent extend this."""

    agent_id: str
    agent_version: str
    skill_id: str

    def __init__(self, guard: HarnessGuard, obs: ObservabilityClient, *,
                 model_id: str, work_item: dict, requesting_user_id: str,
                 repo_path: str):
        self.guard = guard
        self.obs = obs
        self.model_id = model_id
        self.work_item = work_item
        self.requesting_user_id = requesting_user_id
        self.repo_path = repo_path
        self.state = SpecialistState()

    def _log(self, msg: str):
        print(f"    [{self.agent_id}] {msg}")

    def _write_status(self, node: str, status: str, detail: str = ""):
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        if RUN_LOG_PATH.exists():
            try:
                entries = json.loads(RUN_LOG_PATH.read_text())
            except (json.JSONDecodeError, FileNotFoundError):
                entries = []
        entries.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "node": f"{self.agent_id}:{node}",
            "status": status,
            "detail": detail,
        })
        RUN_LOG_PATH.write_text(json.dumps(entries, indent=2))

    def _trace_back(self, **overrides) -> dict:
        base = {
            "user_id": self.requesting_user_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "skill_id": self.skill_id,
            "model_id": self.model_id,
            **self.work_item,
            "outcome_ref": f"outcome-{self.work_item['work_item_id']}-{self.agent_id}",
            "tokens": self.state.tokens_used,
            "cost": str(self.state.cost_incurred),
            "transaction_id": f"txn-{self.work_item['work_item_id']}-{self.agent_id}",
        }
        base.update(overrides)
        return base

    def check_tools(self, tool_names: list[str]) -> list[str]:
        """Shared PLAN step — every specialist checks its own tools the same way."""
        approved = []
        for tool in tool_names:
            tb = self._trace_back()
            try:
                self.guard.check_tool_access(tb, tool_name=tool)
                approved.append(tool)
                self._write_status(tool, "passed", "tool access approved")
            except PolicyViolation as e:
                self._log(f"tool '{tool}': harness BLOCKED — {e}")
                self._write_status(tool, "blocked", str(e))
        return approved

    def reflect_with_possible_loop(self, evidence_a: str, evidence_b: str,
                                    loop_reason: str) -> None:
        """
        Calls the shared LLM brain once. If confidence comes back below
        0.85 — uncertain, but not yet escalation-level — this genuinely
        calls guard.check_reasoning_loop() and asks the model again. A
        REAL second call, not a retry of a tool: exactly the distinction
        check_reasoning_loop() exists to police, separate from
        check_retry() which caps tool retries.

        tokens_used accumulates the REAL token count returned by the API
        for each call made — 0 in offline mode, since there's no real call
        to measure. This is the only place tokens_used is ever set; lint,
        tests, and the security scan are not model calls and have no real
        token cost, so they no longer add a fake one.
        """
        confidence, mode, tokens = get_model_confidence(evidence_a, evidence_b)
        self.state.confidence = confidence
        self.state.confidence_mode = mode
        self.state.tokens_used += tokens

        if confidence < 0.85:
            tb = self._trace_back()
            try:
                self.guard.check_reasoning_loop(
                    tb, work_item_id=self.work_item["work_item_id"],
                    agent_name=self.agent_id, loop_reason=loop_reason,
                )
                self.state.reasoning_loops_used += 1
                self._log(f"confidence {confidence} uncertain — reasoning loop "
                          f"#{self.state.reasoning_loops_used}, asking again")
                confidence, mode, tokens = get_model_confidence(evidence_a, evidence_b)
                self.state.confidence = confidence
                self.state.confidence_mode = mode
                self.state.tokens_used += tokens
            except PolicyViolation as e:
                self._log(f"reasoning-loop cap hit — proceeding with first answer: {e}")

        labels = {"claude": "REAL Claude API call", "azure": "REAL Azure OpenAI call",
                  "offline": "OFFLINE fallback (no API key set)"}
        self._log(f"confidence: {confidence}  [{labels.get(mode, mode)}]  "
                  f"tokens so far: {self.state.tokens_used}")
        self._write_status("reflect", "passed",
                          f"confidence={confidence} [{mode}] loops={self.state.reasoning_loops_used} "
                          f"tokens={self.state.tokens_used}")

    def decide(self) -> None:
        """Shared DECIDE step — same shape as the original single-agent build."""
        self._log(f"WANTS to: auto-approve (confidence={self.state.confidence})")
        tb = self._trace_back()
        try:
            self.guard.check_confidence(tb, confidence=self.state.confidence)
            self.state.decision = "approved"
            self._write_status("decide", "passed", "harness agrees — approved")
            self._log("harness agrees — approved")
        except PolicyViolation as e:
            self.state.decision = "escalated"
            self._write_status("decide", "escalated", str(e))
            self._log(f"harness OVERRULES — {e}")

    def emit_final_telemetry(self):
        tb = self._trace_back()
        self.obs.emit_quality(tb, accuracy=self.state.confidence or 0.0,
                               first_time_right=(self.state.reasoning_loops_used == 0))
        self.obs.emit_cost(
            tb,
            tokens_per_successful_outcome=self.state.tokens_used,
            cost_per_successful_outcome=self.state.cost_incurred,
            retry_token_ratio=Decimal("0.00"),
            wasted_token_ratio=Decimal("0.00"),
            budget_variance=(self.guard.policy.cost_budget - self.state.cost_incurred),
        )
        self.obs.emit_outcome(
            tb,
            successful_outcome=(self.state.decision == "approved"),
            value_contribution=Decimal("100.00") if self.state.decision == "approved" else Decimal("0.00"),
        )

    def run(self) -> SpecialistState:
        raise NotImplementedError("Each specialist implements its own PLAN/ACT sequence")
