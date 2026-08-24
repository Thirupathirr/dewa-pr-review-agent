"""
Starts one PRReviewAgent run against the REAL target_repo/ folder.

Run it:
    python examples/run_pr_review_agent.py
"""
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dewa_observability.sdk import ObservabilityClient
from dewa_observability.harness_guard import HarnessGuard, HarnessPolicy
from agents.pr_review_agent import PRReviewAgent


def main():
    harness_version = "code-agent-harness-v0.2.0"

    obs = ObservabilityClient(harness_version=harness_version)
    policy = HarnessPolicy(
        harness_version=harness_version,
        max_retries=3,
        cost_budget=Decimal("2.00"),
        token_budget=50_000,
        allowed_tools={"read_repo", "run_lint", "run_tests"},
        confidence_threshold=0.70,
    )
    guard = HarnessGuard(policy, obs)

    repo_root = os.path.dirname(os.path.abspath(__file__))
    target_repo = os.path.join(os.path.dirname(repo_root), "target_repo")

    agent = PRReviewAgent(
        guard=guard, obs=obs,
        agent_id="agent-code-pool-01",
        skill_id="skill-pr-review",
        model_id="model-claude-sonnet-5",
        work_item={
            "work_item_id": "wi-9110",
            "process_id": "proc-pr-review",
            "initiative_id": "init-2026-021",
            "division_id": "div-innovation",
        },
        requesting_user_id="dev-alfaraj-2211",
        repo_path=target_repo,
        target_file="calculator.py",
    )

    final_state = agent.run()

    print(f"\n{'─' * 60}")
    print("RUN SUMMARY")
    print(f"{'─' * 60}")
    print(f"  Decision:        {final_state.decision}")
    print(f"  Retries used:    {final_state.retry_attempts - 1} of {policy.max_retries}")
    print(f"  Confidence:      {final_state.confidence} [{final_state.confidence_mode}]")
    print(f"  Cost incurred:   {final_state.cost_incurred} AED of {policy.cost_budget} AED budget")
    print(f"  Fast path events:    {len(obs.fast_path.events)}")
    print(f"  Durable path events: {len(obs.durable_path.events)}")


if __name__ == "__main__":
    main()
