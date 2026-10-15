"""Multi-region comparative pilots for the rural-road-safety call.

The D6-09 call's **eligibility** requires work in *"at least three diverse
regions covering primary and secondary rural roads"*, selected for diverse
geography/climate/design/safety-culture, with **at least two regions exceeding
the EU-average rural fatality rate**. This module runs a consistent **NWRSA**
assessment across regions, validates those eligibility constraints, and produces
a comparative result with the European-dimension checks for the rural,
multi-region setting.

Each region is scored with the same `nwrsa.assess_network` engine, so the
comparison is methodologically consistent; the only per-region inputs are the
section table and the region's rural-fatality context.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .nwrsa import assess_network

REGIONAL_COMPARISON_VERSION = "regional_comparison_v1"
REGIONAL_COMPARISON_CONTRACT_VERSION = "regional_comparison_public_v1"

# Eligibility thresholds from the call text.
MIN_REGIONS = 3
MIN_HIGH_FATALITY_REGIONS = 2


@dataclass(frozen=True)
class RegionPilot:
    region_id: str
    country: str
    rural_fatality_rate: float  # rural road deaths per million inhabitants
    sections: Sequence[Mapping[str, Any]] = field(default_factory=list)


def _mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 2) if present else None


def assess_region(region: RegionPilot, *, categories: int = 3) -> dict[str, Any]:
    """Run the NWRSA on one region and summarise it for comparison."""
    results = assess_network(region.sections, categories=categories)
    distribution = {str(c): 0 for c in range(1, categories + 1)}
    for result in results:
        band = result.get("safety_category")
        if band is not None:
            distribution[str(band)] += 1
    combined = [r["combined_nwrsa_score"] for r in results]
    highest_category = max((int(k) for k, v in distribution.items() if v > 0), default=0)
    return {
        "region_id": region.region_id,
        "country": region.country,
        "rural_fatality_rate": region.rural_fatality_rate,
        "section_count": len(results),
        "category_distribution": distribution,
        "mean_nwrsa_score": _mean(combined),
        "highest_populated_category": highest_category,
    }


def compare_regions(
    regions: Sequence[RegionPilot],
    *,
    eu_average_rural_fatality_rate: float,
    categories: int = 3,
) -> dict[str, Any]:
    """Compare regions and check the call's eligibility constraints."""
    region_summaries = [assess_region(region, categories=categories) for region in regions]
    countries = sorted({region.country for region in regions})
    high_fatality = [
        summary["region_id"]
        for summary in region_summaries
        if summary["rural_fatality_rate"] > eu_average_rural_fatality_rate
    ]

    eligibility = {
        "eu_average_rural_fatality_rate": eu_average_rural_fatality_rate,
        "region_count": len(regions),
        "country_count": len(countries),
        "countries": countries,
        "high_fatality_regions": high_fatality,
        "high_fatality_region_count": len(high_fatality),
        "meets_min_regions": len(regions) >= MIN_REGIONS,
        "meets_min_high_fatality": len(high_fatality) >= MIN_HIGH_FATALITY_REGIONS,
        "is_cross_border": len(countries) >= 2,
    }
    eligibility["eligible"] = (
        eligibility["meets_min_regions"]
        and eligibility["meets_min_high_fatality"]
        and eligibility["is_cross_border"]
    )
    return {
        "regions": region_summaries,
        "eligibility": eligibility,
    }


def _load_region(spec: Mapping[str, Any]) -> RegionPilot:
    path = Path(spec["path"])
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return RegionPilot(
        region_id=str(spec["region_id"]),
        country=str(spec["country"]),
        rural_fatality_rate=float(spec["rural_fatality_rate"]),
        sections=rows,
    )


def run_regional_comparison(
    *,
    region_specs: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    eu_average_rural_fatality_rate: float,
    categories: int = 3,
) -> dict[str, Any]:
    """Read per-region section tables, run the comparative NWRSA, and write the
    comparison + eligibility result with a lineage manifest.

    ``region_specs`` items: ``{"region_id", "country", "rural_fatality_rate", "path"}``.
    """
    if not region_specs:
        raise RuntimeError("At least one region spec is required.")
    regions = [_load_region(spec) for spec in region_specs]
    comparison = compare_regions(
        regions,
        eu_average_rural_fatality_rate=eu_average_rural_fatality_rate,
        categories=categories,
    )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "regional_comparison.csv"
    json_path = output_root / "regional_comparison.json"
    manifest_path = output_root / "regional_comparison.manifest.json"

    fieldnames = [
        "region_id",
        "country",
        "rural_fatality_rate",
        "section_count",
        "mean_nwrsa_score",
        "highest_populated_category",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(comparison["regions"])

    payload = {
        "regional_comparison_version": REGIONAL_COMPARISON_VERSION,
        "categories": categories,
        **comparison,
        "lineage": _build_lineage_contract(
            run_record_path=json_path,
            upstream_inputs=[
                _artifact_reference(f"region_{spec['region_id']}", Path(spec["path"]), _sha256(Path(spec["path"])))
                for spec in region_specs
            ],
            publishable_outputs=[_artifact_reference("regional_comparison_csv", csv_path, None)],
        ),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "regional_comparison_version": REGIONAL_COMPARISON_VERSION,
        "contract": {
            "resource_name": "regional_comparison",
            "public_contract_version": REGIONAL_COMPARISON_CONTRACT_VERSION,
        },
        "outputs": {
            "comparison_csv_path": str(csv_path),
            "comparison_csv_sha256": _sha256(csv_path),
            "summary_json_path": str(json_path),
            "summary_json_sha256": _sha256(json_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "comparison_csv_path": str(csv_path),
        "summary_json_path": str(json_path),
        "manifest_path": str(manifest_path),
        "eligibility": comparison["eligibility"],
    }
