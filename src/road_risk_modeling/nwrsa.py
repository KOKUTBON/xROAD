"""Network-Wide Road Safety Assessment (NWRSA) per RISM Directive (EU) 2019/1936.

The Road Infrastructure Safety Management Directive 2008/96/EC, **as amended by
(EU) 2019/1936**, introduced the **Network-Wide Road Safety Assessment**. It
requires Member States to assess the whole network with **two complementary
approaches** and to **classify every section into at least three safety
categories** by its in-built safety level (Art. 5):

- **reactive** — based on observed crash occurrence;
- **proactive** — based on the **in-built safety** of the road inferred from its
  design characteristics (alignment, cross-section, roadside, junctions, …).

The platform was previously **crash-based only** (the reactive half). This
module adds the **proactive in-built-safety scoring**, **combines** the two into
an NWRSA score, and produces the mandated **≥3-category classification** that
prioritises sections for targeted inspections and remedial action — the
Directive's stated purpose.

Scoring is **transparent and rule-based** (not a learned model): every criterion
is documented, bounded, and auditable, which is what a road authority and a
Horizon evaluator need to trust an infrastructure-safety classification. See
``docs/nwrsa-methodology.md`` for the criteria-to-Directive mapping.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .modeling import _artifact_reference, _build_lineage_contract, _sha256

NWRSA_VERSION = "nwrsa_v1"
NWRSA_CONTRACT_VERSION = "nwrsa_public_v1"

# All scores are on a 0..100 risk scale where **higher = less safe** (more in
# need of inspection), so reactive and proactive are directly comparable.
RISK_SCALE_MAX = 100.0


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class InBuiltCriterion:
    """One proactive in-built-safety criterion.

    ``score`` maps a segment row to a normalised risk fraction in ``[0, 1]``
    (0 = safest, 1 = least safe). ``weight`` sets its share of the proactive
    score. ``ec_reference`` notes the corresponding EC NWRSA / RSI criterion
    family so the matrix is auditable against the methodology.
    """

    key: str
    name: str
    ec_reference: str
    weight: float
    score: Callable[[Mapping[str, Any]], float | None]


def _speed_environment(row: Mapping[str, Any]) -> float | None:
    speed = _to_float(row.get("maxspeed_numeric"))
    if speed is None:
        return None
    # Rural two-lane risk rises sharply with operating speed. 50 km/h -> 0,
    # 100+ km/h -> 1.
    return _clamp((speed - 50.0) / 50.0)


def _carriageway_width(row: Mapping[str, Any]) -> float | None:
    width = _to_float(row.get("width_numeric"))
    if width is None:
        return None
    # Narrow carriageways drive run-off-road and head-on risk. >=7.5 m -> 0,
    # <=5.0 m -> 1.
    return _clamp((7.5 - width) / 2.5)


def _horizontal_alignment(row: Mapping[str, Any]) -> float | None:
    sinuosity = _to_float(row.get("sinuosity"))
    if sinuosity is None:
        return None
    # Sinuosity 1.0 = straight (0 risk); 1.3+ = sharp/curvy alignment (1).
    return _clamp((sinuosity - 1.0) / 0.3)


def _junction_exposure(row: Mapping[str, Any]) -> float | None:
    degree = _to_float(row.get("node_degree_max"))
    connector = _to_float(row.get("is_intersection_connector"))
    if degree is None and connector is None:
        return None
    base = 0.0 if degree is None else _clamp((degree - 2.0) / 3.0)
    if connector:
        base = max(base, 0.5)
    return _clamp(base)


def _lane_provision(row: Mapping[str, Any]) -> float | None:
    lanes = _to_float(row.get("lanes_numeric"))
    if lanes is None:
        return None
    # Single-lane-each-way (2 total) two-way roads carry head-on/overtaking risk;
    # more lanes (separation) reduces in-built risk on the rural network.
    if lanes <= 2:
        return 1.0
    if lanes >= 4:
        return 0.0
    return 0.5


def _road_class(row: Mapping[str, Any]) -> float | None:
    rank = _to_float(row.get("road_class_rank"))
    if rank is None:
        return None
    # Lower-class secondary roads (higher rank index) tend to have weaker
    # in-built safety provision. Normalised over a 1..5 class scale.
    return _clamp((rank - 1.0) / 4.0)


def _roadside_structures(row: Mapping[str, Any]) -> float | None:
    # Treat absence of both keys as "unknown" (drop + renormalise) rather than
    # "no structure", so a section with no attributes yields no score at all.
    if "bridge" not in row and "tunnel" not in row:
        return None
    has_bridge = str(row.get("bridge") or "").strip().lower() in {"yes", "true", "1"}
    has_tunnel = str(row.get("tunnel") or "").strip().lower() in {"yes", "true", "1"}
    if not has_bridge and not has_tunnel:
        return 0.0
    # Structures introduce fixed roadside hazards / constrained cross-sections.
    return 0.6 if (has_bridge ^ has_tunnel) else 1.0


# The proactive in-built-safety matrix. A representative, auditable subset of the
# EC NWRSA two-lane methodology (~18 field criteria); criteria requiring on-site
# survey data not yet held (e.g. roadside clear-zone, line marking quality) are
# documented as gaps in docs/nwrsa-methodology.md rather than silently omitted.
IN_BUILT_CRITERIA: tuple[InBuiltCriterion, ...] = (
    InBuiltCriterion("speed_environment", "Speed environment", "Operating speed", 0.22, _speed_environment),
    InBuiltCriterion("carriageway_width", "Carriageway width", "Cross-section", 0.20, _carriageway_width),
    InBuiltCriterion("horizontal_alignment", "Horizontal alignment", "Alignment / curvature", 0.18, _horizontal_alignment),
    InBuiltCriterion("lane_provision", "Lane provision / separation", "Cross-section", 0.12, _lane_provision),
    InBuiltCriterion("junction_exposure", "Junction & access density", "Junctions", 0.14, _junction_exposure),
    InBuiltCriterion("road_class", "Road class provision", "Road function/class", 0.08, _road_class),
    InBuiltCriterion("roadside_structures", "Roadside structures", "Roadside hazards", 0.06, _roadside_structures),
)


def score_in_built_safety(row: Mapping[str, Any]) -> dict[str, Any]:
    """Proactive in-built-safety score for one section (0..100, higher = worse).

    Criteria with missing inputs are dropped and the weights of the present
    criteria are renormalised, so a partially-attributed section still yields a
    score with an explicit ``coverage`` figure.
    """
    contributions: dict[str, float] = {}
    total_weight = 0.0
    weighted = 0.0
    for criterion in IN_BUILT_CRITERIA:
        fraction = criterion.score(row)
        if fraction is None:
            continue
        contributions[criterion.key] = round(fraction, 4)
        weighted += criterion.weight * fraction
        total_weight += criterion.weight
    if total_weight == 0.0:
        return {"score": None, "coverage": 0.0, "contributions": {}}
    score = (weighted / total_weight) * RISK_SCALE_MAX
    coverage = total_weight / sum(c.weight for c in IN_BUILT_CRITERIA)
    return {
        "score": round(score, 2),
        "coverage": round(coverage, 3),
        "contributions": contributions,
    }


def _reactive_raw(row: Mapping[str, Any]) -> float | None:
    """Crash-based risk density: severity-weighted crashes per km, before the
    network is normalised to the 0..100 scale."""
    length_m = _to_float(row.get("segment_length_m")) or 0.0
    crashes = _to_float(row.get("crash_count"))
    fatal = _to_float(row.get("fatal_crash_count")) or 0.0
    injury = _to_float(row.get("injury_crash_count")) or 0.0
    if crashes is None:
        # Fall back to severity-weighted components if no total is given.
        crashes = fatal + injury
    if length_m <= 0.0:
        length_km = 0.2  # default to the NWRSA 200 m section length
    else:
        length_km = length_m / 1000.0
    # Severity weighting: fatal crashes dominate the network screening.
    severity_weighted = crashes + 9.0 * fatal + 2.0 * injury
    return severity_weighted / length_km


def _normalise_to_scale(raw_values: Sequence[float | None]) -> list[float | None]:
    present = [value for value in raw_values if value is not None]
    if not present:
        return [None for _ in raw_values]
    lo = min(present)
    hi = max(present)
    if hi <= lo:
        return [0.0 if value is not None else None for value in raw_values]
    return [
        None if value is None else round((value - lo) / (hi - lo) * RISK_SCALE_MAX, 2)
        for value in raw_values
    ]


def classify_sections(
    combined_scores: Sequence[float | None],
    *,
    categories: int = 3,
) -> list[int | None]:
    """Assign each section a safety category 1..N by combined-score quantiles.

    Category **1 = safest**, **N = least safe / highest priority**. The Directive
    mandates **at least three** categories; ``categories`` defaults to 3.
    """
    if categories < 3:
        raise ValueError("RISM Directive 2019/1936 mandates at least 3 safety categories.")
    present = sorted(value for value in combined_scores if value is not None)
    if not present:
        return [None for _ in combined_scores]
    # Quantile thresholds over the observed score distribution.
    thresholds = [
        present[min(len(present) - 1, int(round(q / categories * len(present))))]
        for q in range(1, categories)
    ]

    def _category(value: float | None) -> int | None:
        if value is None:
            return None
        for index, threshold in enumerate(thresholds):
            if value <= threshold:
                return index + 1
        return categories

    return [_category(value) for value in combined_scores]


def assess_network(
    rows: Sequence[Mapping[str, Any]],
    *,
    reactive_weight: float = 0.5,
    proactive_weight: float = 0.5,
    categories: int = 3,
) -> list[dict[str, Any]]:
    """Run the full NWRSA on a sequence of section rows.

    Returns one result dict per input row with the reactive, proactive, and
    combined scores and the mandated safety category.
    """
    total = reactive_weight + proactive_weight
    if total <= 0:
        raise ValueError("reactive_weight + proactive_weight must be positive.")
    reactive_weight, proactive_weight = reactive_weight / total, proactive_weight / total

    proactive = [score_in_built_safety(row) for row in rows]
    reactive_norm = _normalise_to_scale([_reactive_raw(row) for row in rows])

    combined: list[float | None] = []
    for proactive_entry, reactive_value in zip(proactive, reactive_norm):
        proactive_value = proactive_entry["score"]
        if proactive_value is None and reactive_value is None:
            combined.append(None)
        elif proactive_value is None:
            combined.append(reactive_value)
        elif reactive_value is None:
            combined.append(proactive_value)
        else:
            combined.append(
                round(reactive_weight * reactive_value + proactive_weight * proactive_value, 2)
            )

    bands = classify_sections(combined, categories=categories)

    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        results.append(
            {
                "section_id": row.get("segment_id") or row.get("section_id") or f"row-{index}",
                "reactive_score": reactive_norm[index],
                "proactive_score": proactive[index]["score"],
                "proactive_coverage": proactive[index]["coverage"],
                "proactive_contributions": proactive[index]["contributions"],
                "combined_nwrsa_score": combined[index],
                "safety_category": bands[index],
            }
        )
    return results


def _category_distribution(results: Sequence[Mapping[str, Any]], categories: int) -> dict[str, int]:
    distribution = {str(category): 0 for category in range(1, categories + 1)}
    for result in results:
        band = result.get("safety_category")
        if band is not None:
            distribution[str(band)] += 1
    return distribution


def run_nwrsa_assessment(
    *,
    sections_path: str | Path,
    output_dir: str | Path,
    reactive_weight: float = 0.5,
    proactive_weight: float = 0.5,
    categories: int = 3,
) -> dict[str, Any]:
    """Read a section table, run the NWRSA, and write a Directive-compliant
    classification (CSV + JSON + markdown) with a lineage manifest."""
    sections_file = Path(sections_path)
    with sections_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Section table is empty.")

    results = assess_network(
        rows,
        reactive_weight=reactive_weight,
        proactive_weight=proactive_weight,
        categories=categories,
    )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "nwrsa_classification.csv"
    json_path = output_root / "nwrsa_assessment.json"
    report_path = output_root / "nwrsa_assessment.md"
    manifest_path = output_root / "nwrsa_assessment.manifest.json"

    fieldnames = [
        "section_id",
        "reactive_score",
        "proactive_score",
        "proactive_coverage",
        "combined_nwrsa_score",
        "safety_category",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    distribution = _category_distribution(results, categories)
    priority_sections = sorted(
        (result for result in results if result["combined_nwrsa_score"] is not None),
        key=lambda result: result["combined_nwrsa_score"],
        reverse=True,
    )[:10]

    payload = {
        "nwrsa_version": NWRSA_VERSION,
        "directive": "RISM Directive 2008/96/EC as amended by (EU) 2019/1936, Art. 5 (NWRSA)",
        "weights": {"reactive": reactive_weight, "proactive": proactive_weight},
        "categories": categories,
        "section_count": len(results),
        "category_distribution": distribution,
        "criteria": [
            {"key": c.key, "name": c.name, "ec_reference": c.ec_reference, "weight": c.weight}
            for c in IN_BUILT_CRITERIA
        ],
        "priority_sections": priority_sections,
        "results": results,
        "lineage": _build_lineage_contract(
            run_record_path=json_path,
            upstream_inputs=[_artifact_reference("nwrsa_sections", sections_file, _sha256(sections_file))],
            publishable_outputs=[
                _artifact_reference("nwrsa_classification_csv", csv_path, None),
                _artifact_reference("nwrsa_assessment_json", json_path, None),
            ],
        ),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_build_report(payload), encoding="utf-8")

    manifest = {
        "nwrsa_version": NWRSA_VERSION,
        "contract": {"resource_name": "nwrsa_assessment", "public_contract_version": NWRSA_CONTRACT_VERSION},
        "outputs": {
            "classification_csv_path": str(csv_path),
            "classification_csv_sha256": _sha256(csv_path),
            "assessment_json_path": str(json_path),
            "assessment_json_sha256": _sha256(json_path),
            "report_path": str(report_path),
            "report_sha256": _sha256(report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "classification_csv_path": str(csv_path),
        "assessment_json_path": str(json_path),
        "manifest_path": str(manifest_path),
        "category_distribution": distribution,
        "section_count": len(results),
    }


def _build_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# NWRSA Assessment — Network-Wide Road Safety Assessment",
        "",
        f"- basis: `{payload['directive']}`",
        f"- sections assessed: `{payload['section_count']}`",
        f"- safety categories: `{payload['categories']}` (1 = safest, "
        f"{payload['categories']} = highest priority)",
        f"- score weights: reactive `{payload['weights']['reactive']:.2f}` / "
        f"proactive `{payload['weights']['proactive']:.2f}`",
        "",
        "## Category distribution",
        "",
        "| Category | Sections |",
        "| --- | --- |",
    ]
    for category, count in sorted(payload["category_distribution"].items(), key=lambda item: int(item[0])):
        lines.append(f"| {category} | {count} |")
    lines.extend(
        [
            "",
            "## In-built-safety criteria (proactive)",
            "",
            "| Criterion | EC reference | Weight |",
            "| --- | --- | --- |",
        ]
    )
    for criterion in payload["criteria"]:
        lines.append(f"| {criterion['name']} | {criterion['ec_reference']} | {criterion['weight']:.2f} |")
    lines.extend(
        [
            "",
            "## Top priority sections for inspection",
            "",
            "| Section | Combined score | Category |",
            "| --- | --- | --- |",
        ]
    )
    for section in payload["priority_sections"]:
        lines.append(
            f"| `{section['section_id']}` | {section['combined_nwrsa_score']} | {section['safety_category']} |"
        )
    lines.append("")
    return "\n".join(lines).strip() + "\n"
