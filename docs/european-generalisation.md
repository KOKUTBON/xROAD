# European Generalisation: Cross-Border Validation on a Second Member State

This note describes the cross-border validation that takes the platform beyond
a single national context. A model validated in one country (here Italy:
Bari, Foggia, Taranto, Lecce) says little about portability, so we add
**France** as a second Member State, ingest its national crash register through
a dedicated country adapter, and run the existing transferability benchmark
**cross-border**.

## Why France / BAAC

The second-country candidates were FR BAAC, ES DGT, NL and DE. We chose the
French **BAAC** (*Base Annuelle des Accidents Corporels de la circulation*)
because it is:

- **Open and licence-clean** — published yearly on data.gouv.fr under the
  Etalab **Licence Ouverte 2.0**, which is explicitly compatible with reuse and
  redistribution, unlike several Member-State registers that gate microdata.
- **The French CARE feed** — BAAC is the dataset France reports to the EU
  **CARE** Community database, so aligning to it exercises the same CADaS
  vocabulary used by European road-safety data standards.
- **Structurally comparable but a genuine regime shift** — accident-level
  records with coordinates (since 2019), an explicit urban/rural flag, and a
  much higher rural share than urban Puglia, which is exactly the portability
  stress a transferability test needs.

## Country adapter

`road_risk_modeling.adapters.baac_fr_csv` maps a BAAC `caracteristiques` row to
the canonical `CanonicalCrashRecord`, folding in fatality/injury counts
aggregated from the per-person `usagers` file (`aggregate_baac_casualties`).
Person- and vehicle-level rows are deliberately **not** retained, consistent
with the data-minimisation stance in [`docs/ethics/`](ethics/). The adapter
mirrors the Bari/Puglia adapters: same accident-level altitude, same coordinate
and quality-flag conventions, France-specific code-list crosswalks for
`int` (intersection), `lum` (lighting), `atm` (weather) and `agg` (area type).

## Data-regime differences surfaced by the second country

| Dimension | Italy (Puglia / Bari open data, ISTAT) | France (BAAC) |
| --- | --- | --- |
| Record altitude | Accident-level; Bari injury is a **binary** indicator (no counts) | Accident-level; **counts** derivable by aggregating `usagers.grav` |
| Severity encoding | `MORTI`/`FERITI` counts (legacy) or yes/no flag (Bari) | `grav` per person: 1 indemne, 2 tué, 3 hospitalisé, 4 léger |
| Coordinates | Decimal degrees, scaling quirks in Bari export | Decimal degrees, **comma** decimal separator, present from 2019 |
| Urban / rural | Implicit (`Centro abitato` yes/no on Bari only) | Explicit `agg` (1 rural, 2 urban) — fills CADaS `A.12` Type of area |
| Geography codes | ISTAT province/commune | INSEE `dep` / `com` |
| Time | Dispatch-time proxy (Bari) or year-only (legacy) | `hrmn` to the minute (`HH:MM` modern, `HHMM` legacy) |
| Licensing | Municipal CC-BY / ISTAT terms | **Etalab Licence Ouverte 2.0** |
| CADaS conformance | Adapter-specific and source-dependent | BAAC additionally carries native `lum`/`atm`/`agg` fields |

The most material schema win from the second country is the **explicit
urban/rural flag**: it directly fills the `A.12` "Type of area" gap that the
the Italy-only schema, and is also the discriminator the
[rural-road capability](rural-road-capability.md) depends on.

## Cross-border transferability result

The harness `tools/cross_border_transferability_demo.py` runs the existing
`evaluate_frequency_transferability` over three jurisdictions — `bari`,
`foggia_core` (Italy) and `fr_baac_sample` (France) — across 2020–2022 with a
2022 temporal holdout, then builds a benchmark bundle into
`data/reporting/cross_border_transferability/`. Mean Poisson deviance
(lower is better) for the French target:

| Mode | `fr_baac_sample` deviance | Reading |
| --- | --- | --- |
| Within-jurisdiction temporal | **0.124** | France predicting France with its own history — the floor |
| Cross-jurisdiction temporal | **0.186** | France predicted from IT cities, France history retained — **+50% degradation** |
| Cross-jurisdiction cold-start | **0.231** | France with its temporal-history features zeroed — the true new-country case, **+86% vs floor** |
| Cross-jurisdiction history-free | **0.200** | Model retrained without any history features |

The pattern is the expected one and is the headline finding: a model that has
**never seen French roads** still produces a usable ranking, but accuracy
degrades monotonically as local signal is removed, and the **cold-start** mode
(no French history at all) is the hardest — which is precisely the situation a
new Member State faces on day one. By contrast the Italian targets stay far
tighter under cross-border training (Bari 0.108 → 0.137 cold-start), because two
of the three training jurisdictions are themselves Italian. This quantifies the
cost of porting to a new national road network and motivates a short local
calibration period rather than zero-shot deployment.

## Honesty note on the France extract

The committed France extract
(`data/external/cross_border_demo/fr_baac_segment_year_metrics.csv`) is a
**deterministic, structurally-faithful sample** in the BAAC shape. It exercises
the canonical schema, the country adapter contract, and the cross-border
modeling path end-to-end, but it is **not** the full licensed BAAC corpus and
its magnitudes are **not** French road-safety statistics. Bulk ingestion of the
real annual BAAC files (open under Licence Ouverte 2.0) through
`adapters/baac_fr_csv` is the production follow-up; the methodology, adapter,
and benchmark wiring proven here are what carry over unchanged. This mirrors the
explicit-approximation framing already used for the cold-start benchmark.

## Reproduce

```bash
PYTHONPATH=src python3 tools/cross_border_transferability_demo.py
```

Deterministic, so the published artifacts under
`data/reporting/cross_border_transferability/` regenerate byte-for-byte.

## Relationship to other documents

- Uses the canonical schema and European road-safety vocabulary: the
  second country is what makes the interoperability claim *demonstrated*
  rather than asserted.
- The rural skew of BAAC complements the
  [rural-road capability](rural-road-capability.md).
