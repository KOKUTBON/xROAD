#!/usr/bin/env python3
"""Run the public synthetic demo twice and compare every generated artifact."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEMO_FILES = (
    ROOT / "data" / "external" / "nwrsa_demo",
    ROOT / "data" / "reporting" / "nwrsa",
    ROOT / "data" / "external" / "scientific_benchmark_demo",
    ROOT / "data" / "reporting" / "scientific_benchmark",
)


def snapshot() -> dict[str, str]:
    result: dict[str, str] = {}
    for directory in DEMO_FILES:
        if not directory.exists():
            continue
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[str(path.relative_to(ROOT))] = digest
    return result


def run_demo() -> None:
    subprocess.run(
        [sys.executable, "tools/nwrsa_demo.py"],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        check=True,
    )
    subprocess.run(
        [sys.executable, "tools/scientific_benchmark_demo.py"],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        check=True,
    )


def main() -> int:
    run_demo()
    first = snapshot()
    run_demo()
    second = snapshot()
    if first != second:
        print("reproducibility check failed: generated artifacts differ", file=sys.stderr)
        for path in sorted(set(first) | set(second)):
            if first.get(path) != second.get(path):
                print(f"  {path}", file=sys.stderr)
        return 1
    print(f"reproducibility check passed: {len(second)} deterministic artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
