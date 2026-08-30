# Orchestrator — skills.md

## Does
- Reads the real repo directory to decide which specialists a change needs
- Runs CodeAgent + SecurityAgent always; adds UnitTestAgent only if a
  test_*.py file exists in the repo
- Combines the three specialists' individual verdicts into one final
  squad decision (approved / escalated / blocked)

## Does not
- Does not review code, run tests, or scan for security patterns itself
  — delegates all three to the specialists
- Does not call the LLM — its routing decision is a deterministic
  directory check, not a judgment call, so it never uses
  check_reasoning_loop()
- Does not override a specialist's individual decision — if any
  specialist is blocked, the whole squad is blocked

## "Done" means
Every needed specialist has run to completion and the combined decision
has been written to the audit trail.
