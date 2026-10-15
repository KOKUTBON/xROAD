#!/usr/bin/env python3
"""Security release checks that do not require cloud credentials."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[opsu]_[A-Za-z0-9_]{20,}\b"),
    "generic_password_assignment": re.compile(r"(?i)\b(password|secret|token)\s*=\s*['\"](?!\$)[^'\"]{12,}['\"]"),
}
TEXT_SUFFIXES = {
    ".env",
    ".example",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".tf",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


def _is_text_candidate(path: Path) -> bool:
    if path.suffix in TEXT_SUFFIXES:
        return True
    return path.name in {"Dockerfile", "LICENSE", "Makefile"}


def check_no_plain_env_files(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if (path.name == ".env" or path.name.startswith(".env.") or path.suffix == ".env") and not path.name.endswith(".example"):
            failures.append(f"plain environment file is tracked: {path.relative_to(REPO_ROOT)}")
    return failures


def check_secret_patterns(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if not _is_text_candidate(path) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{name} pattern found in {path.relative_to(REPO_ROOT)}")
    return failures


def check_required_hardening_assets() -> list[str]:
    required = [
        "apps/api/middleware/operational_hardening.py",
        "apps/api/services/error_tracking.py",
        "infra/scripts/backup_postgres.sh",
        "infra/scripts/backup_minio.sh",
        "infra/scripts/restore_postgres.sh",
        "infra/scripts/restore_minio.sh",
        "docs/incident-response.md",
        ".github/workflows/security-scan.yml",
    ]
    return [
        f"missing required hardening asset: {relative}"
        for relative in required
        if not (REPO_ROOT / relative).is_file()
    ]


def check_bash_syntax() -> list[str]:
    failures: list[str] = []
    for relative in (
        "infra/scripts/backup_postgres.sh",
        "infra/scripts/backup_minio.sh",
        "infra/scripts/restore_postgres.sh",
        "infra/scripts/restore_minio.sh",
    ):
        result = subprocess.run(
            ["bash", "-n", str(REPO_ROOT / relative)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failures.append(f"bash syntax failed for {relative}: {result.stderr.strip()}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local security release checks.")
    parser.add_argument("--summary", action="store_true", help="Print a compact success summary.")
    args = parser.parse_args(argv)

    paths = _tracked_files()
    failures: list[str] = []
    failures.extend(check_no_plain_env_files(paths))
    failures.extend(check_secret_patterns(paths))
    failures.extend(check_required_hardening_assets())
    failures.extend(check_bash_syntax())

    if failures:
        for failure in failures:
            print(f"[security-release-checks] FAIL: {failure}", file=sys.stderr)
        return 1
    if args.summary:
        print("[security-release-checks] PASS: tracked env, secret-pattern, hardening-asset, and bash syntax checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
