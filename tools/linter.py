"""
Runs REAL pyflakes against a real target repo via subprocess. Returns
real pass/fail based on real output — not a scripted boolean.

Also includes a small, deliberately narrow auto-fix: if pyflakes reports
an unused import, remove that exact import line. This is the same class
of safe, deterministic fix a real linting agent applies — it does not
touch anything pyflakes didn't flag.
"""
import subprocess
import re
from pathlib import Path


def run_lint(repo_path: str, filename: str) -> tuple[bool, str]:
    """Returns (passed, raw_output). Genuinely runs pyflakes."""
    target = str(Path(repo_path) / filename)
    result = subprocess.run(
        ["python3", "-m", "pyflakes", target],
        capture_output=True, text=True,
    )
    passed = result.returncode == 0
    output = result.stdout.strip() or result.stderr.strip() or "(no issues)"
    return passed, output


def auto_fix_unused_imports(repo_path: str, filename: str, lint_output: str) -> bool:
    """
    Parses real pyflakes output for 'X imported but unused' and removes
    that exact import line from the real file. Returns True if a fix
    was applied.

    Deliberately narrow: only handles this one, safe, unambiguous case.
    Anything else pyflakes reports is left alone — this is not a general
    code-fixing agent, just a demonstration of one safe automated fix.
    """
    match = re.search(r"'(\w+)' imported but unused", lint_output)
    if not match:
        return False

    unused_name = match.group(1)
    target = Path(repo_path) / filename
    lines = target.read_text().splitlines(keepends=True)

    new_lines = [
        line for line in lines
        if not re.match(rf"^\s*import {re.escape(unused_name)}\s*(#.*)?$", line)
    ]

    if len(new_lines) == len(lines):
        return False  # nothing matched, don't pretend we fixed it

    target.write_text("".join(new_lines))
    return True
