"""
A small, REAL security pattern scanner — regex-based, deliberately
narrow. See agents/security_agent.skills.md for what this covers and
what it explicitly does not.
"""
import re
from pathlib import Path

RISKY_PATTERNS = [
    (r"\beval\(", "use of eval()"),
    (r"\bexec\(", "use of exec()"),
    (r"os\.system\(", "use of os.system()"),
    (r"shell\s*=\s*True", "subprocess call with shell=True"),
    (r"(password|secret|api_key)\s*=\s*['\"]", "hardcoded credential-like assignment"),
]


def run_security_scan(repo_path: str, filename: str) -> tuple[bool, str]:
    """Returns (passed, output). Genuinely scans the real file's text
    line by line — not a scripted pass/fail."""
    target = Path(repo_path) / filename
    text = target.read_text()
    findings = []
    for i, line in enumerate(text.splitlines(), start=1):
        for pattern, label in RISKY_PATTERNS:
            if re.search(pattern, line):
                findings.append(f"line {i}: {label}")
    if findings:
        return False, "; ".join(findings)
    return True, "(no known-risky patterns found)"
