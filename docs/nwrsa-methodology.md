# NWRSA Methodology — Network-Wide Road Safety Assessment

This document maps the platform's **Network-Wide Road Safety Assessment**
implementation to the **Road Infrastructure Safety Management (RISM) Directive
2008/96/EC as amended by Directive (EU) 2019/1936**, which requires the NWRSA
methodology to combine crash-based and infrastructure safety assessments,
including on secondary rural roads.

Implementation: `src/road_risk_modeling/nwrsa.py`. Demo:
`tools/nwrsa_demo.py` → `data/reporting/nwrsa/`.

## What the Directive requires

Article 5 of the amended Directive introduced the NWRSA, requiring Member States
to:

1. assess the **entire network** with **two complementary approaches** — a
   **reactive** (crash-based) analysis **and** a **proactive** assessment of the
   road's **in-built safety** from its design characteristics; and
2. **classify all sections into at least three categories** according to their
   in-built safety level; then
3. use that classification to **prioritise targeted road-safety inspections and
   remedial action**.

## What the platform had, and the gap this closes

The platform was **crash-based only** — frequency and severity models on matched
crashes. That is the **reactive** half. It had **no proactive in-built-safety
assessment** and produced **no Directive-mandated category classification**.
This module adds both and combines them.

## The two approaches as implemented

### Reactive (crash-based)

`_reactive_raw` computes a **severity-weighted crash density per kilometre**
(fatal crashes weighted ×9, injury ×2 over the base count), defaulting to the
200 m NWRSA section length where geometry is missing. Densities are then
**min-max normalised across the network** to a 0–100 risk scale so they are
directly comparable with the proactive score.

### Proactive (in-built safety)

`score_in_built_safety` applies a **transparent, weighted criteria matrix** over
the road-design attributes the platform already enriches (geometry, topology,
OSM tags). Each criterion returns a bounded risk fraction `[0, 1]`; criteria with
missing inputs are dropped and remaining weights **renormalised**, with an
explicit `coverage` figure.

| Criterion | EC NWRSA / RSI family | Platform attribute | Weight |
| --- | --- | --- | --- |
| Speed environment | Operating speed | `maxspeed_numeric` | 0.22 |
| Carriageway width | Cross-section | `width_numeric` | 0.20 |
| Horizontal alignment | Alignment / curvature | `sinuosity` | 0.18 |
| Junction & access density | Junctions | `node_degree_max`, `is_intersection_connector` | 0.14 |
| Lane provision / separation | Cross-section | `lanes_numeric` | 0.12 |
| Road class provision | Road function / class | `road_class_rank` | 0.08 |
| Roadside structures | Roadside hazards | `bridge`, `tunnel` | 0.06 |

This is a **representative, auditable subset** of the ~18 criteria the EC
two-lane rural NWRSA methodology applies to 200 m sections. The deliberate
design choice is **transparency over completeness**: a rule-based, documented,
bounded matrix that a road authority and an external reviewer can inspect, rather
than an opaque score.

#### Documented criteria gaps (require field-survey data)

Several EC criteria need on-site inspection data the platform does not yet hold
and are **named rather than silently omitted**: roadside clear-zone / hazard
severity, line-marking and delineation quality, sight-distance measurement,
shoulder type/width, and pavement skid resistance. These are the natural
extension once an inspection campaign or richer asset data is available; the
`coverage` field already reports how complete each section's assessment is.

## Combination and classification

`assess_network` blends the two normalised scores
(`combined = w_reactive·reactive + w_proactive·proactive`, default 0.5/0.5) and
`classify_sections` assigns each section a category **1 (safest) … N (highest
priority)** by quantiles of the combined score. `categories` defaults to **3**
and the function **rejects fewer than 3**, enforcing the Directive's minimum.

The output (`run_nwrsa_assessment`) is a Directive-shaped package: a
per-section classification CSV, an assessment JSON (with the criteria matrix,
category distribution, and a top-priority inspection list), a markdown report,
and a lineage-hashed manifest.

## Honesty and limitations

- The criteria **weights and thresholds are an engineering default** calibrated
  to rural two-lane character, not a nationally-adopted scheme; a Member State
  deployment should calibrate them against its own RSI manual.
- The committed demo runs on a **structurally-faithful rural sample**; the
  method and wiring are what transfer to production segment tables.
- This is **decision support** prioritising inspections — not a substitute for
  the on-site Road Safety Inspection the Directive also requires.

## Relationship to other work

- Consumes the same segment enrichment as the
  [crash-frequency model](scientific-benchmark.md); the reactive half reuses the
  crash aggregates.
- The rural **200 m sectioning** and rural feature enrichment are the
  complementary data-capability item.
- Aligns with the Safe System framing and RISM Directive (EU) 2019/1936 guidelines.
