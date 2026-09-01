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


def auto_fix_duplicate_imports(repo_path: str, filename: str, lint_output: str) -> bool:
    """
    Parses real pyflakes output for 'redefinition of unused X from line N'
    — e.g. the same module imported twice — and removes ONLY the
    duplicate line, using the exact line number pyflakes itself reported.
    The original (first) import is kept untouched.

    Same philosophy as auto_fix_unused_imports(): narrow, safe,
    deterministic. Removes the line by its reported number, not by
    pattern-guessing which occurrence is the duplicate — precise even
    if the same module were imported 3+ times.
    """
    match = re.search(
        r"^.+?:(\d+):\d+: redefinition of unused '(\w+)' from line \d+",
        lint_output, re.MULTILINE,
    )
    if not match:
        return False

    duplicate_line_num = int(match.group(1))
    target = Path(repo_path) / filename
    lines = target.read_text().splitlines(keepends=True)

    if not (1 <= duplicate_line_num <= len(lines)):
        return False  # line number out of range — don't guess, don't crash

    flagged_line = lines[duplicate_line_num - 1]
    if not re.match(r"^\s*import \w+\s*(#.*)?$", flagged_line):
        return False  # safety check: only remove a genuine plain import line

    del lines[duplicate_line_num - 1]
    target.write_text("".join(lines))
    return True
