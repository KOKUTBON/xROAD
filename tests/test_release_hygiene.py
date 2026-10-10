"""Repository hygiene guards for the public open-source tree.

These tests keep data, secrets, and machine-specific details out of Git. They
run against `git ls-files`, so they check what would actually be published
rather than whatever happens to be on the local disk.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]

# The only paths allowed under data/: the layout README and empty placeholders.
ALLOWED_DATA_PATHS = {
    "data/README.md",
    "data/raw/.gitkeep",
    "data/staging/.gitkeep",
    "data/processed/.gitkeep",
    "data/external/.gitkeep",
}

TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".yml", ".yaml",
    ".toml", ".cfg", ".ini", ".txt", ".csv", ".html", ".css", ".sh", ".tf",
    ".ipynb", ".sql",
}


def _tracked_files() -> list[str]:
    completed = subprocess.run(  # noqa: S603 - fixed local git command
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [path for path in completed.stdout.split("\0") if path]


class ReleaseHygieneTests(unittest.TestCase):
    def test_no_data_is_tracked(self) -> None:
        tracked_data = {path for path in _tracked_files() if path.startswith("data/")}
        self.assertEqual(
            tracked_data - ALLOWED_DATA_PATHS,
            set(),
            "Data files must stay local; only the data/ layout is tracked.",
        )

    def test_no_environment_files_are_tracked(self) -> None:
        offenders = [
            path
            for path in _tracked_files()
            if Path(path).name.startswith(".env") and not Path(path).name.endswith(".example")
        ]
        self.assertEqual(offenders, [])

    def test_no_large_file_storage_filters(self) -> None:
        self.assertFalse(
            (REPO_ROOT / ".gitattributes").exists()
            and "filter=lfs" in (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8"),
            "Large binaries belong outside Git, not in LFS.",
        )

    def test_no_machine_specific_absolute_paths(self) -> None:
        offenders = []
        for path in _tracked_files():
            file_path = REPO_ROOT / path
            if file_path.suffix not in TEXT_SUFFIXES or not file_path.is_file():
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            if ("/" + "Users/") in text or ("C:" + chr(92) + "Users" + chr(92)) in text or ("/home/" + "runner/") in text:
                offenders.append(path)
        self.assertEqual(offenders, [], "Use repository-relative paths.")

    def test_gitignore_keeps_data_and_secrets_out(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("data/*", ".env", "*.joblib", "*.parquet", "*.pem", "artifacts/"):
            self.assertIn(pattern, gitignore)

    def test_web_dockerfile_uses_deterministic_lockfile_install(self) -> None:
        dockerfile = (REPO_ROOT / "infra" / "docker" / "Dockerfile.web").read_text(encoding="utf-8")
        self.assertIn("RUN npm ci", dockerfile)
        self.assertNotIn("RUN npm install", dockerfile)

    def test_tracked_file_size_guard_passes_current_tree(self) -> None:
        result = subprocess.run(  # noqa: S603 - fixed local tool
            [sys.executable, "tools/check_tracked_file_sizes.py"],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_python_ci_runs_tracked_file_size_guard(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "python-ci.yml").read_text(encoding="utf-8")
        self.assertIn("python tools/check_tracked_file_sizes.py", workflow)


if __name__ == "__main__":
    unittest.main()
