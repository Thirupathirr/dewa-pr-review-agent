# CodeAgent — skills.md

## Does
- Reviews the implementation of a code change using real pyflakes lint output
- Applies ONE narrow, safe auto-fix: removing an unused import pyflakes
  explicitly flagged — nothing else
- Forms a confidence judgment based on lint evidence only

## Does not
- Does not check test coverage or test correctness (see UnitTestAgent)
- Does not scan for security patterns (see SecurityAgent)
- Does not rewrite logic, refactor, or fix anything pyflakes didn't
  explicitly name
- Does not decide the final squad outcome alone — the Orchestrator
  combines this agent's verdict with the other specialists'

## "Done" means
Lint passes clean AND a confidence score has cleared the harness's
threshold — not just "no errors."
