#!/usr/bin/env python3
"""Fail when regular Git blobs exceed the repository release threshold."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


DEFAULT_MAX_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class TrackedBlob:
    oid: str
    path: str
    size_bytes: int

    @property
    def size_mib(self) -> float:
        return self.size_bytes / 1024 / 1024


def _run_git(args: list[str]) -> str:
    completed = subprocess.run(  # noqa: S603 - command is fixed to local git.
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def _tracked_oids() -> dict[str, str]:
    output = _run_git(["ls-files", "-s", "-z"])
    blobs: dict[str, str] = {}
    for entry in output.split("\0"):
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        _mode, oid, _stage = metadata.split()
        blobs[path] = oid
    return blobs


def _blob_size(oid: str) -> int:
    return int(_run_git(["cat-file", "-s", oid]).strip())


def oversized_blobs(max_bytes: int) -> list[TrackedBlob]:
    violations: list[TrackedBlob] = []
    for path, oid in _tracked_oids().items():
        size = _blob_size(oid)
        if size >= max_bytes:
            violations.append(TrackedBlob(oid=oid, path=path, size_bytes=size))
    return sorted(violations, key=lambda blob: (-blob.size_bytes, blob.path))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-mib",
        type=float,
        default=50.0,
        help="Maximum allowed regular Git blob size in MiB. Default: 50.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    max_bytes = int(args.max_mib * 1024 * 1024)
    violations = oversized_blobs(max_bytes)
    if not violations:
        print(f"No regular Git blobs are >= {args.max_mib:g} MiB.")
        return 0

    print(f"Regular Git blobs >= {args.max_mib:g} MiB are not allowed:", file=sys.stderr)
    for blob in violations:
        print(f"- {blob.size_mib:.1f} MiB {blob.path} ({blob.oid})", file=sys.stderr)
    print("Use Git LFS, release assets, or object storage; see docs/release-hygiene.md.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
