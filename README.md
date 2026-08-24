# dewa-pr-review-agent

A real agentic system that touches a real repo — depends on
`dewa-observability` as an installed package, not a copied folder.

## What's real here

- `tools/linter.py` — genuinely runs `pyflakes` via subprocess against
  `target_repo/calculator.py`. The first run genuinely fails (unused
  `import os`). The agent applies a real, narrow auto-fix that actually
  edits the file on disk, then genuinely re-runs lint and passes.
- `tools/test_runner.py` — genuinely runs `pytest` against `target_repo/`.
- `tools/model_confidence.py` — the ONE place a model is used. Calls real
  Azure OpenAI if `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` are
  set; otherwise falls back to an honestly-labeled offline value so the
  demo still runs without credentials.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../dewa-observability
pip install pyflakes pytest openai
```

## Run it

```
python examples/run_pr_review_agent.py
```

Each run: real lint failure → real auto-fix → real lint pass → real
tests → confidence check → harness decides approve or escalate.

**Note:** `target_repo/calculator.py` gets modified when the agent fixes
it. Reset it before re-running if you want to see the failure→fix cycle
again — re-add `import os` as the first import line.

## To use a real Azure OpenAI model instead of the offline fallback

```
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
```

Then run the same command — `tools/model_confidence.py` automatically
switches to the real call, and the run summary will say `[real]` instead
of `[offline]`.
