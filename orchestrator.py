"""
Orchestrator — decides which specialist sub-agents a change needs, runs
them, and combines their verdicts into one final decision.

Its own planning step is DETERMINISTIC — a real directory listing, not a
repeated LLM judgment — so it has nothing to loop on and never calls
guard.check_reasoning_loop() on itself. That control exists for agents
that ask the model the same question again; this one never does. It IS
still wrapped by guard.check_tool_access() for its one real action
(reading the repo) — no agent in this system, including this one, skips
the harness. See orchestrator.skills.md for scope.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from dewa_observability.harness_guard import HarnessGuard, PolicyViolation
from dewa_observability.sdk import ObservabilityClient

from agents.code_agent import CodeAgent
from agents.unit_test_agent import UnitTestAgent
from agents.security_agent import SecurityAgent

RUN_LOG_PATH = Path(__file__).resolve().parent / "dashboard" / "run_log.json"


class Orchestrator:
    agent_id = "orchestrator"
    agent_version = "orchestrator-v1.0.0"
    skill_id = "skill-squad-routing"

    def __init__(self, guard: HarnessGuard, obs: ObservabilityClient, *,
                 model_id: str, work_item: dict, requesting_user_id: str,
                 repo_path: str, target_file: str):
        self.guard = guard
        self.obs = obs
        self.model_id = model_id
        self.work_item = work_item
        self.requesting_user_id = requesting_user_id
        self.repo_path = repo_path
        self.target_file = target_file

    def _log(self, msg: str):
        print(f"  [{self.agent_id}] {msg}")

    def _reset_run_log(self):
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUN_LOG_PATH.write_text("[]")

    def _write_status(self, node: str, status: str, detail: str = ""):
        entries = []
        if RUN_LOG_PATH.exists():
            try:
                entries = json.loads(RUN_LOG_PATH.read_text())
            except (json.JSONDecodeError, FileNotFoundError):
                entries = []
        entries.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "skill_id": self.skill_id,
            "node": f"{self.agent_id}:{node}",
            "step": node,
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
            "outcome_ref": f"outcome-{self.work_item['work_item_id']}-orchestrator",
            "tokens": 0,
            "cost": "0.00",
            "transaction_id": f"txn-{self.work_item['work_item_id']}-orchestrator",
        }
        base.update(overrides)
        return base

    def plan(self) -> list[str]:
        """DETERMINISTIC routing — a real directory listing, not a guess."""
        self._log("── PLAN (routing) ──")
        tb = self._trace_back()
        try:
            self.guard.check_tool_access(tb, tool_name="read_repo")
        except PolicyViolation as e:
            self._log(f"harness BLOCKED even reading the repo — {e}")
            self._write_status("plan", "blocked", str(e))
            return []

        files = [f.name for f in Path(self.repo_path).iterdir() if f.is_file()]
        needed = ["code_agent", "security_agent"]
        if any(f.startswith("test_") for f in files):
            needed.append("unit_test_agent")
        self._log(f"repo has {len(files)} file(s) — routing to: {needed}")
        self._write_status("plan", "passed", f"routed to: {needed}")
        return needed

    def run(self):
        self._reset_run_log()
        self._log(f"Orchestrator starting on {self.work_item['work_item_id']} "
                  f"— real repo: {self.repo_path}")

        needed = self.plan()
        if not needed:
            return {"decision": "blocked", "results": {}}

        common_kwargs = dict(
            guard=self.guard, obs=self.obs, model_id=self.model_id,
            work_item=self.work_item, requesting_user_id=self.requesting_user_id,
            repo_path=self.repo_path,
        )

        results = {}
        if "code_agent" in needed:
            results["code_agent"] = CodeAgent(target_file=self.target_file, **common_kwargs).run()
        if "unit_test_agent" in needed:
            results["unit_test_agent"] = UnitTestAgent(**common_kwargs).run()
        if "security_agent" in needed:
            results["security_agent"] = SecurityAgent(target_file=self.target_file, **common_kwargs).run()

        decisions = {name: state.decision for name, state in results.items()}
        if all(d == "approved" for d in decisions.values()):
            final = "approved"
        elif any(d == "blocked" for d in decisions.values()):
            final = "blocked"
        else:
            final = "escalated"

        self._log(f"── SQUAD FINAL: {final} ── {decisions}")
        self._write_status("squad_final", final, str(decisions))
        return {"decision": final, "results": results}
