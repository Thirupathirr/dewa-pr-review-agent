"""
CI entry point for the multi-agent squad — same Orchestrator, same 3
agents, same harness as examples/run_squad.py. The ONLY difference:
this version posts the result as a real GitHub PR comment when it's
running inside GitHub Actions. Run it locally and it just prints,
exactly like run_squad.py always has.

v1 scope: reviews the whole file(s) in target_repo/, same as the local
version. Does not yet parse the PR diff to review only changed lines.
"""
import sys
import os
import json
import urllib.request
import urllib.error
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dewa_observability.sdk import ObservabilityClient
from dewa_observability.harness_guard import HarnessGuard, HarnessPolicy
from dewa_observability.tokenomics import classify_big_t

from orchestrator import Orchestrator


def build_markdown_summary(result: dict, obs: ObservabilityClient,
                            classification: dict) -> str:
    """Same information the terminal summary always printed, as a PR comment."""
    decision = result["decision"]
    emoji = {"approved": "✅", "escalated": "⚠️", "blocked": "🚫"}.get(decision, "•")

    lines = [
        f"## {emoji} DEWA Agentic Squad — {decision.upper()}",
        "",
        "| Agent | Decision | Confidence | Loops | Cost |",
        "|---|---|---|---|---|",
    ]
    for name, state in result["results"].items():
        lines.append(
            f"| {name} | {state.decision} | {state.confidence} | "
            f"{state.reasoning_loops_used} | {state.cost_incurred} AED |"
        )
    lines += [
        "",
        f"**Tokenomics class:** `{classification['class']}` — {classification['reason']}",
    ]
    if classification["at_risk"]:
        lines.append("⚠️ At risk of hitting the reasoning-loop cap")
    lines += [
        "",
        f"Fast path events: {len(obs.fast_path.events)} · "
        f"Durable path events: {len(obs.durable_path.events)}",
        "",
        "*v1 — reviews the whole file, not yet the PR diff.*",
    ]
    return "\n".join(lines)


def post_pr_comment(body: str) -> None:
    """Posts `body` as a comment on the PR that triggered this run.
    Silently does nothing if the required GitHub Actions env vars aren't
    present — so this script still works fine when run locally."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    event_path = os.environ.get("GITHUB_EVENT_PATH")

    if not (token and repo and event_path):
        print("\n[not running in GitHub Actions — skipping PR comment]")
        return

    with open(event_path) as f:
        event = json.load(f)
    pr_number = event.get("pull_request", {}).get("number") or event.get("number")
    if not pr_number:
        print("\n[no pull_request number found in event payload — skipping comment]")
        return

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    req = urllib.request.Request(
        url,
        data=json.dumps({"body": body}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"\n[posted PR comment — status {resp.status}]")
    except urllib.error.HTTPError as e:
        print(f"\n[FAILED to post PR comment — {e.code}: {e.read().decode()}]")


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
        "work_item_id": "wi-ci-" + os.environ.get("GITHUB_RUN_ID", "local"),
        "process_id": "proc-pr-review",
        "initiative_id": "init-2026-021",
        "division_id": "div-innovation",
    }

    orchestrator = Orchestrator(
        guard=guard, obs=obs,
        model_id="model-claude-sonnet-5",
        work_item=work_item,
        requesting_user_id="github-actions",
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
              f"cost={state.cost_incurred} AED")
    print(f"  Fast path events:    {len(obs.fast_path.events)}")
    print(f"  Durable path events: {len(obs.durable_path.events)}")

    all_events = obs.durable_path.events
    classification = classify_big_t(all_events, work_item["work_item_id"],
                                     max_reasoning_loops=policy.max_reasoning_loops)
    print(f"\n  Tokenomics class: {classification['class']} — {classification['reason']}")
    if classification["at_risk"]:
        print(f"  ⚠ at risk of hitting the reasoning-loop cap")

    summary_md = build_markdown_summary(result, obs, classification)
    post_pr_comment(summary_md)

    # Fail the CI check if the squad didn't approve — this is what makes
    # it a real gate, not just an informational comment.
    if result["decision"] != "approved":
        sys.exit(1)


if __name__ == "__main__":
    main()
