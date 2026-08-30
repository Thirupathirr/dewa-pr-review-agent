"""
SecurityAgent — scans for known-risky code patterns.

Uses a NEW tool, tools/security_scanner.py — the one genuinely new piece
of tooling this squad build required. See security_agent.skills.md for
what this covers (a narrow pattern scan) and what it explicitly does not
cover (a real security audit).
"""
from __future__ import annotations
from decimal import Decimal

from agents.base_agent import SpecialistAgent
from tools.security_scanner import run_security_scan


class SecurityAgent(SpecialistAgent):
    agent_id = "security-agent"
    agent_version = "security-agent-v1.0.0"
    skill_id = "skill-security-scan"

    def __init__(self, *args, target_file: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_file = target_file

    def run(self):
        self._log("── SECURITY AGENT ──")
        approved = self.check_tools(["read_repo", "run_security_scan"])
        if "run_security_scan" not in approved:
            self.state.decision = "blocked"
            return self.state

        passed, output = run_security_scan(self.repo_path, self.target_file)
        self._log(f"security scan: {'CLEAN' if passed else 'FLAGGED'} — {output}")

        self.state.tokens_used += 500
        self.state.cost_incurred += Decimal("0.09")

        if not passed:
            self._write_status("run_security_scan", "blocked", output)
            self.state.decision = "blocked"
            return self.state
        self._write_status("run_security_scan", "passed", output)

        self.reflect_with_possible_loop(
            output, "(security scan — pattern match only, no lint/test evidence)",
            loop_reason="a clean pattern scan alone is narrow evidence",
        )
        self.decide()
        self.emit_final_telemetry()
        return self.state
