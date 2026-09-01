"""
Entry point for the multi-agent squad — Orchestrator + Code/Unit
Test/Security agents, all against the SAME real repo, all governed by
the SAME harness as the original single-agent build.

Run:
    export ANTHROPIC_API_KEY="..."   # optional — offline fallback works without it
    python examples/run_squad.py
"""
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dewa_observability.sdk import ObservabilityClient
from dewa_observability.harness_guard import HarnessGuard, HarnessPolicy
from dewa_observability.tokenomics import classify_big_t

from orchestrator import Orchestrator


def main():
    harness_version = "code-agent-harness-v0.3.0"

    obs = ObservabilityClient(harness_version=harness_version)
    policy = HarnessPolicy(
        harness_version=harness_version,
        max_retries=3,
        cost_budget=Decimal("2.00"),
        token_budget=50_000,
        allowed_tools={"read_repo", "run_lint", "run_tests", "run_security_scan"},
        confidence_threshold=0.70,
        max_reasoning_loops=2,
    )
    guard = HarnessGuard(policy, obs)

    repo_root = os.path.dirname(os.path.abspath(__file__))
    target_repo = os.path.join(os.path.dirname(repo_root), "target_repo")

    work_item = {
        "work_item_id": "wi-9110-squad",
        "process_id": "proc-pr-review",
        "initiative_id": "init-2026-021",
        "division_id": "div-innovation",
    }

    orchestrator = Orchestrator(
        guard=guard, obs=obs,
        model_id="model-claude-sonnet-5",
        work_item=work_item,
        requesting_user_id="dev-alfaraj-2211",
        repo_path=target_repo,
        target_file="calculator.py",
    )

    result = orchestrator.run()

    print(f"\n{'─' * 60}")
    print("SQUAD RUN SUMMARY")
    print(f"{'─' * 60}")
    print(f"  Final decision:  {result['decision']}")
    for name, state in result["results"].items():
        print(f"  {name:16s} decision={str(state.decision):10s} "
              f"confidence={state.confidence} loops={state.reasoning_loops_used} "
              f"tokens={state.tokens_used} cost={state.cost_incurred} AED")
    print(f"  Fast path events:    {len(obs.fast_path.events)}")
    print(f"  Durable path events: {len(obs.durable_path.events)}")

    # Tokenomics classification — reads the SAME events this run just
    # emitted. With 3 agents on one work item, this should classify as
    # T(n·k·a): agent-multiplicative.
    all_events = obs.durable_path.events
    classification = classify_big_t(all_events, work_item["work_item_id"],
                                     max_reasoning_loops=policy.max_reasoning_loops)
    print(f"\n  Tokenomics class: {classification['class']} — {classification['reason']}")
    if classification["at_risk"]:
        print(f"  ⚠ at risk of hitting the reasoning-loop cap")


if __name__ == "__main__":
    main()
