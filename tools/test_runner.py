"""Runs REAL pytest against the target repo via subprocess."""
import subprocess


def run_tests(repo_path: str) -> tuple[bool, str, int, int]:
    """Returns (all_passed, raw_output, passed_count, failed_count)."""
    result = subprocess.run(
        ["python3", "-m", "pytest", repo_path, "-v", "--tb=short"],
        capture_output=True, text=True,
    )
    output = result.stdout.strip()
    passed_count = output.count(" PASSED")
    failed_count = output.count(" FAILED")
    all_passed = result.returncode == 0
    return all_passed, output, passed_count, failed_count
