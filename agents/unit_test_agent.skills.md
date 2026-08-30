# UnitTestAgent — skills.md

## Does
- Runs the real test suite via pytest against the repo under review
- Forms a confidence judgment based on test-run evidence only

## Does not
- Does not review implementation code or lint anything (see CodeAgent)
- Does not scan for security patterns (see SecurityAgent)
- Does not write new tests — checks what already exists
- Does not decide the final squad outcome alone

## "Done" means
All tests pass AND a confidence score has cleared the harness's
threshold — a green run alone is not sufficient on its own.
