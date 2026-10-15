#!/usr/bin/env python3
"""Apply an audited model-registry stage change."""

from __future__ import annotations

import argparse
import json

from road_risk_modeling.model_registry import MODEL_STAGES, ModelRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_name")
    parser.add_argument("stage", choices=MODEL_STAGES)
    parser.add_argument("--version", type=int)
    parser.add_argument("--registry-dir", default="data/model_registry")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--waive", help="Override failing gates with an audited reason.")
    args = parser.parse_args()

    registry = ModelRegistry(args.registry_dir)
    versions = registry.list_versions(args.model_name)
    if not versions:
        parser.error(f"no registered versions for {args.model_name!r}")
    version = args.version or max(record["version"] for record in versions)
    record = registry.set_stage(
        args.model_name,
        version=version,
        stage=args.stage,
        actor=args.actor,
        reason=args.reason,
        waive_reason=args.waive,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
