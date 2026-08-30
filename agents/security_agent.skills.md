# SecurityAgent — skills.md

## Does
- Scans the changed file's real text for a small, fixed list of known-risky
  patterns: eval(), exec(), os.system(), shell=True, hardcoded
  password/secret/api_key assignments
- Forms a confidence judgment based on scan evidence only

## Does not
- Does not perform a full security audit, dependency scan, or
  vulnerability assessment
- Does not review business logic or test coverage
- Does not decide the final squad outcome alone
- A clean scan means "none of these five patterns were found" — not
  "this code is secure"

## "Done" means
Scan is clean of the known patterns AND a confidence score has cleared
the harness's threshold.
