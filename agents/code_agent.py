"""
CodeAgent — reviews the actual implementation.

Reuses the SAME lint tool the original single-agent build used
(tools/linter.py) — nothing about the tool changed, only who calls it
and what it's called alongside now. See code_agent.skills.md for scope.
"""
from __future__ import annotations
from decimal import Decimal

from dewa_observability.harness_guard import PolicyViolation
from agents.base_agent import SpecialistAgent
from tools.linter import run_lint, auto_fix_unused_imports, auto_fix_duplicate_imports

# Every known-safe fix this agent can apply, tried in order until one
# matches. Adding coverage for a new issue type means adding one more
# (name, function) pair here — nothing else about the loop changes.
FIXERS = [
    ("unused import", auto_fix_unused_imports),
    ("duplicate import", auto_fix_duplicate_imports),
]


class CodeAgent(SpecialistAgent):
    agent_id = "code-agent"
    agent_version = "code-agent-v1.0.0"
    skill_id = "skill-code-review"

    def __init__(self, *args, target_file: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_file = target_file
        self.lint_output = ""
        self.initial_failure = None  # set only if the FIRST lint attempt failed
        self.fixes_applied = []      # names of every fixer that actually ran, in order

    def run(self):
        self._log("── CODE AGENT ──")
        approved = self.check_tools(["read_repo", "run_lint"])
        if "run_lint" not in approved:
            self.state.decision = "blocked"
            return self.state

        attempts = 0
        passed = False
        while not passed:
            attempts += 1
            passed, output = run_lint(self.repo_path, self.target_file)
            self.lint_output = output
            self._log(f"lint attempt {attempts}: {'PASSED' if passed else 'FAILED'} — {output}")
            if passed:
                self._write_status("run_lint", "passed", output)
                break

            if attempts == 1:
                self.initial_failure = output  # remember the ORIGINAL problem,
                                                # before self.lint_output gets
                                                # overwritten by the fixed result

            tb = self._trace_back()
            try:
                self.guard.check_retry(tb, work_item_id=self.work_item["work_item_id"],
                                        retry_reason=f"lint_failed: {output}")
            except PolicyViolation as e:
                self._log(f"harness BLOCKED further retries — {e}")
                self.state.decision = "blocked"
                return self.state

            fixer_used = None
            for fixer_name, fixer_fn in FIXERS:
                if fixer_fn(self.repo_path, self.target_file, output):
                    fixer_used = fixer_name
                    break

            if fixer_used:
                self.fixes_applied.append(fixer_used)
                self._log(f"applied real auto-fix ({fixer_used}) to the real file")
            else:
                self._log("no automated fix available for this issue")
                self.state.decision = "blocked"
                return self.state

        # tokens_used is now tracked for real, inside reflect_with_possible_loop()
        # — it reads the actual token count back from the Claude API response.
        # No baseline added here: lint is not a model call, has no token cost.
        # cost_incurred below is STILL a placeholder (0.16 AED) — real cost
        # needs Anthropic's actual per-token price + a USD→AED rate, neither
        # wired up yet. Flagged here rather than silently left unexplained.
        self.state.cost_incurred += Decimal("0.16")

        # Build the REAL evidence to send to Claude. Before this fix, only
        # the final passing lint output ("(no issues)") was ever sent — a
        # file that failed and got fixed looked IDENTICAL to a file that
        # never had a problem. Now the fix history, if any, is included.
        if self.initial_failure:
            fixes_summary = ", ".join(self.fixes_applied) if self.fixes_applied else "unknown fix"
            evidence_a = (
                f"Initial lint FAILED: {self.initial_failure}\n"
                f"Auto-fix applied ({fixes_summary}).\n"
                f"Final lint after fix: {self.lint_output}"
            )
        else:
            evidence_a = self.lint_output  # unchanged path — nothing to fix, nothing to hide

        self.reflect_with_possible_loop(
            evidence_a, "(code review — no test evidence available to this agent)",
            loop_reason="lint result alone is thin evidence for a confidence judgment",
        )
        self.decide()
        self.emit_final_telemetry()
        return self.state
