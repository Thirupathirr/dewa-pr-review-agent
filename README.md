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
  Claude if `ANTHROPIC_API_KEY` is set; otherwise falls back to an
  honestly-labeled offline value so the demo still runs without
  credentials. (Azure OpenAI is also supported as a fallback path if you
  ever need it — see below — but Claude is what this repo is built for.)

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../dewa-observability
pip install -r requirements.txt
```

## Run it

```
export ANTHROPIC_API_KEY="your-key"
python examples/run_pr_review_agent.py
```

Each run: real lint failure → real auto-fix → real lint pass → real
tests → confidence check → harness decides approve or escalate.

**Note:** `target_repo/calculator.py` gets modified when the agent fixes
it. Reset it before re-running if you want to see the failure→fix cycle
again — re-add `import os` as the first import line.

## To run without an API key (offline demo mode)

Just skip the `export` line above. `tools/model_confidence.py`
automatically falls back to a labeled offline value — the run summary
will say `[offline]` instead of `[claude]`, so it's never mistaken for a
real judgment.

## To use Azure OpenAI instead of Claude

Only relevant if you're not using an Anthropic key:

```
pip install openai
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
```

`tools/model_confidence.py` checks for `ANTHROPIC_API_KEY` first — Azure
is only used if that's unset. Not in `requirements.txt` by default,
since Claude is the primary path.
