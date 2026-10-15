# Rural & Secondary Two-Lane Road Capability

More than half of EU road fatalities occur in rural areas, largely on primary
and secondary rural roads, including **single-carriageway / two-lane two-way**
roads. The segmentation, exposure proxies, and crash tasks were originally tuned
for urban networks; this module adds the rural capability.

Implementation: `src/road_risk_modeling/rural_sectioning.py`. End-to-end pilot:
`tools/rural_pilot_demo.py`.

## 1. 200 m sectioning (the NWRSA working resolution)

Rural OSM edges are long and heterogeneous, so assessing a whole edge as one
unit is too coarse for the Directive. `section_road_segment` splits each segment
into fixed **~200 m sections** — the NWRSA two-lane convention — and
`section_network` assembles the whole network. Crash counts are **apportioned by
length share** across a segment's sections; design attributes are inherited.
Sectioning is length-based and pure-Python (geometry cutting is applied too when
a real LineString and shapely are present).

This is what lets the [NWRSA assessment](nwrsa-methodology.md) and crash density
be computed at the resolution the Directive expects rather than on whole edges.

## 2. Rural feature set

`derive_rural_features` attaches rural-specific attributes to each section:

| Feature | Meaning |
| --- | --- |
| `curvature_class` | straight / gentle / winding / sharp, from `sinuosity` |
| `is_single_carriageway` | two-way road with ≤2 lanes (undivided) |
| `narrow_carriageway` | carriageway width < 6 m |
| `run_off_road_exposure` | geometry-derived single-vehicle run-off-road risk (curvature × speed) |
| `head_on_exposure` | geometry-derived head-on risk (speed on undivided single carriageways) |
| `rural_exposure_index` | low-AADT exposure proxy from road class |
| `sparse_cell` | section has < 1 crash (the rural norm) |

**Rural crash mechanisms.** Run-off-road and head-on are the dominant rural
crash mechanisms (vs. the junction/turning conflicts that dominate urban
crashes). The platform has **no per-crash mechanism field**, so these are
**geometry-derived exposures**, not crash-typed classifications — an honest
proxy that flags where those mechanisms are physically likely, documented as
such rather than overstated.

## 3. Rural exposure handling

Rural crash data is **sparse**: in the pilot, ~95% of 200 m sections are
zero-crash. Naive crash counts are therefore misleading at this resolution. Two
controls address it:

- `rural_exposure_index` — a low-AADT exposure proxy from road class (absent an
  AADT feed, the defensible stand-in; reconciles with the exposure backbone,
  Issue 16).
- `sparse_cell` flag — marks the zero/low-crash sections so downstream scoring
  leans on the **proactive in-built-safety** signal (which does not need crash
  history) rather than on noise. This is exactly why the NWRSA combines reactive
  **and** proactive: on sparse rural cells, proactive carries the assessment.

## 4. End-to-end rural pilot

`tools/rural_pilot_demo.py` runs the full chain on a rural two-lane sample:

```
variable-length rural edges
        │  rural_sectioning  (200 m sections + rural features)
        ▼
184 × 200 m sections  (sparse-cell share ≈ 0.95)
        │  nwrsa  (reactive + proactive, ≥3 categories)
        ▼
Directive-compliant safety classification (e.g. 69 / 55 / 60)
```

Outputs are written under `data/reporting/rural_pilot/`, demonstrating the
rural sections feeding the [NWRSA classification](nwrsa-methodology.md)
end-to-end.

## Honest scope

- Sectioning is **length-based**; true geometry cutting needs the geospatial
  stack and real LineStrings (the pure-Python path is exact for apportioning
  attributes and crashes, which is what the downstream tasks consume).
- Rural mechanism exposures and the exposure index are **geometry/class-derived
  proxies**, pending crash-mechanism coding and a real AADT feed.
- The committed extract is a **structurally-faithful rural sample**; the
  sectioning and feature logic carry over unchanged to production segment tables
  and a real rural pilot network.

## CLI

```bash
road-risk rural-section --segments path/to/segments.csv --output-dir data/reporting/rural_sectioning
```
