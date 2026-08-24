"""Reads real files from the real target repo. No simulation."""
from pathlib import Path


def read_file(repo_path: str, filename: str) -> str:
    full_path = Path(repo_path) / filename
    return full_path.read_text()


def list_python_files(repo_path: str) -> list[str]:
    return sorted(p.name for p in Path(repo_path).glob("*.py"))
