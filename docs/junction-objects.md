# Junction And Node Objects

This document records the first non-segment road-object layers in the project.

## Scope

The current implementation now includes three Bari object families, one derived conflict layer, and one strengthened movement layer:

- official traffic signals from the municipal `Semafori` open-data feed
- a derived mixed node layer built from OSM crossing features, the Bari segment network, and the current signal layer
- network-derived unsignalized junction and roundabout objects snapped to the Bari segment graph
- explicit conflict-zone polygons built from crossings, approaches, unsignalized junctions, and roundabout entries
- movement/control-state labels on those conflict zones, including crossing protection state, turn-path class, and priority-rule hints
- point-based movement objects keyed by incoming arm and outgoing-arm candidate, with movement-resolution and signal-priority variants
- a first signal-phase-enriched movement layer where normalized phase records can be joined onto explicit Bari movements
It still does not cover lane-level movements or real controller timing in every case, and it does not resolve unique outgoing arms everywhere.

## Commands

Build the Bari signal-node layer:

```bash
PYTHONPATH=src python3 -m road_risk_modeling build-bari-signal-nodes \
  --output-dir data/processed/node_objects/bari_signals \
  --segments-path data/processed/segments/bari/road_segments.geojson \
  --raw-dir data/raw/bari_signal_nodes
```

Match the official Bari crash feed onto those node objects:

```bash
PYTHONPATH=src python3 -m road_risk_modeling match-node-objects \
  data/staging/bari_open_data/bari_open_data_canonical.curated.jsonl \
  data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson \
  --output-dir data/processed/node_matches/bari_open_data_signals \
  --max-distance-m 35
```

Aggregate the matched crashes into node-year metrics:

```bash
PYTHONPATH=src python3 -m road_risk_modeling aggregate-node-objects \
  data/processed/node_matches/bari_open_data_signals/matched_node_records.jsonl \
  data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson \
  --output-dir data/processed/node_aggregates/bari_open_data_signals
```

Build the expanded Bari crossing, junction-approach, unsignalized-junction, and roundabout layer:

```bash
PYTHONPATH=src python3 -m road_risk_modeling build-bari-crossing-and-approach-objects \
  --output-dir data/processed/node_objects/bari_crossing_approaches \
  --signal-nodes-path data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson \
  --segments-path data/processed/segments/bari/road_segments.geojson \
  --boundary-path data/processed/segments/bari/boundary.geojson \
  --raw-dir data/raw/bari_crossing_objects \
  --approach-distance-m 25 \
  --junction-buffer-m 35 \
  --signal-link-m 50 \
  --unsignalized-min-degree 4 \
  --unsignalized-major-edge-min 2
```

Match the official Bari crash feed onto that expanded node layer:

```bash
PYTHONPATH=src python3 -m road_risk_modeling match-node-objects \
  data/staging/bari_open_data/bari_open_data_canonical.curated.jsonl \
  data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson \
  --output-dir data/processed/node_matches/bari_open_data_crossing_approaches \
  --max-distance-m 30
```

Aggregate the matched crashes into the expanded node-year table:

```bash
PYTHONPATH=src python3 -m road_risk_modeling aggregate-node-objects \
  data/processed/node_matches/bari_open_data_crossing_approaches/matched_node_records.jsonl \
  data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson \
  --output-dir data/processed/node_aggregates/bari_open_data_crossing_approaches
```

Build the first Bari conflict-zone layer on top of those node objects:

```bash
PYTHONPATH=src python3 -m road_risk_modeling build-bari-conflict-zones \
  --output-dir data/processed/conflict_zones/bari \
  --node-objects-path data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson \
  --segments-path data/processed/segments/bari/road_segments.geojson
```

Match the official Bari crash feed onto those conflict zones using inside-zone matching:

```bash
PYTHONPATH=src python3 -m road_risk_modeling match-node-objects \
  data/staging/bari_open_data/bari_open_data_canonical.curated.jsonl \
  data/processed/conflict_zones/bari/road_conflict_zones.geojson \
  --output-dir data/processed/node_matches/bari_open_data_conflict_zones \
  --max-distance-m 0
```

Aggregate the conflict-zone matches into a zone-year table:

```bash
PYTHONPATH=src python3 -m road_risk_modeling aggregate-node-objects \
  data/processed/node_matches/bari_open_data_conflict_zones/matched_node_records.jsonl \
  data/processed/conflict_zones/bari/road_conflict_zones.geojson \
  --output-dir data/processed/node_aggregates/bari_open_data_conflict_zones
```

Build Bari movement objects from the conflict-zone layer:

```bash
PYTHONPATH=src python3 -m road_risk_modeling build-bari-movement-objects \
  --output-dir data/processed/movement_objects/bari \
  --conflict-zones-path data/processed/conflict_zones/bari/road_conflict_zones.geojson \
  --segments-path data/processed/segments/bari/road_segments.geojson \
  --movement-offset-m 8
```

Match the official Bari crash feed onto those movement objects:

```bash
PYTHONPATH=src python3 -m road_risk_modeling match-node-objects \
  data/staging/bari_open_data/bari_open_data_canonical.curated.jsonl \
  data/processed/movement_objects/bari/road_movement_objects.geojson \
  --output-dir data/processed/node_matches/bari_open_data_movements \
  --max-distance-m 15
```

Aggregate the matched crashes into a movement-year table:

```bash
PYTHONPATH=src python3 -m road_risk_modeling aggregate-node-objects \
  data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl \
  data/processed/movement_objects/bari/road_movement_objects.geojson \
  --output-dir data/processed/node_aggregates/bari_open_data_movements
```

Build the Bari movement review pack for unresolved targets and signal-phase readiness:

```bash
PYTHONPATH=src python3 -m road_risk_modeling build-bari-movement-review-pack \
  --output-dir data/reporting/movement_review/bari \
  --movement-objects-path data/processed/movement_objects/bari/road_movement_objects.geojson \
  --matched-records-path data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl \
  --aggregate-path data/processed/node_aggregates/bari_open_data_movements/node_year_metrics.csv \
  --signal-nodes-path data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson \
  --top-n 20

PYTHONPATH=src python3 -m road_risk_modeling build-bari-signal-phase-intake-pack \
  --output-dir data/planning/signal_phase_intake/bari \
  --movement-review-path data/reporting/movement_review/bari/movement_review_pack.json \
  --signal-nodes-path data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson \
  --movement-objects-path data/processed/movement_objects/bari/road_movement_objects.geojson \
  --top-n 20
```

Run the first sample phase-data path and apply it onto Bari movement objects:

```bash
PYTHONPATH=src python3 -m road_risk_modeling ingest-signal-phase-extract \
  data/planning/signal_phase_intake/bari/sample_templates/signal_stage_plan_export_template.csv \
  data/planning/signal_phase_intake/bari/mapping_stubs/signal_stage_plan_export_mapping_stub.json \
  --output-dir data/processed/signal_phase_records/bari_stage_plan_sample

PYTHONPATH=src python3 -m road_risk_modeling ingest-signal-phase-extract \
  data/planning/signal_phase_intake/bari/sample_templates/controller_event_log_export_template.csv \
  data/planning/signal_phase_intake/bari/mapping_stubs/controller_event_log_export_mapping_stub.json \
  --output-dir data/processed/signal_phase_records/bari_controller_event_sample

PYTHONPATH=src python3 -m road_risk_modeling ingest-signal-phase-extract \
  data/planning/signal_phase_intake/bari/sample_templates/arm_phase_mapping_sheet_template.csv \
  data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json \
  --output-dir data/processed/signal_phase_records/bari_arm_phase_mapping_sample

PYTHONPATH=src python3 -m road_risk_modeling apply-signal-phase-to-movements \
  data/processed/movement_objects/bari/road_movement_objects.geojson \
  data/processed/signal_phase_records/bari_stage_plan_sample/signal_phase_records.manifest.json \
  data/processed/signal_phase_records/bari_controller_event_sample/signal_phase_records.manifest.json \
  data/processed/signal_phase_records/bari_arm_phase_mapping_sample/signal_phase_records.manifest.json \
  --output-dir data/processed/movement_objects/bari_signal_phase_sample

PYTHONPATH=src python3 -m road_risk_modeling aggregate-node-objects \
  data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl \
  data/processed/movement_objects/bari_signal_phase_sample/road_movement_objects_signal_phase.geojson \
  --output-dir data/processed/node_aggregates/bari_open_data_movements_signal_phase_sample
```

## Live Artifacts

- [traffic_signal_nodes.manifest.json](../data/processed/node_objects/bari_signals/traffic_signal_nodes.manifest.json)
- [matched_node_records.manifest.json](../data/processed/node_matches/bari_open_data_signals/matched_node_records.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_signals/node_year_metrics.manifest.json)
- [road_node_objects.manifest.json](../data/processed/node_objects/bari_crossing_approaches/road_node_objects.manifest.json)
- [matched_node_records.manifest.json](../data/processed/node_matches/bari_open_data_crossing_approaches/matched_node_records.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_crossing_approaches/node_year_metrics.manifest.json)
- [road_conflict_zones.manifest.json](../data/processed/conflict_zones/bari/road_conflict_zones.manifest.json)
- [matched_node_records.manifest.json](../data/processed/node_matches/bari_open_data_conflict_zones/matched_node_records.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_conflict_zones/node_year_metrics.manifest.json)
- [road_movement_objects.manifest.json](../data/processed/movement_objects/bari/road_movement_objects.manifest.json)
- [matched_node_records.manifest.json](../data/processed/node_matches/bari_open_data_movements/matched_node_records.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_movements/node_year_metrics.manifest.json)
- [movement_review_pack.manifest.json](../data/reporting/movement_review/bari/movement_review_pack.manifest.json)
- [signal_phase_intake_pack.manifest.json](../data/planning/signal_phase_intake/bari/signal_phase_intake_pack.manifest.json)
- [signal_phase_records.manifest.json](../data/processed/signal_phase_records/bari_stage_plan_sample/signal_phase_records.manifest.json)
- [signal_phase_records.manifest.json](../data/processed/signal_phase_records/bari_controller_event_sample/signal_phase_records.manifest.json)
- [signal_phase_records.manifest.json](../data/processed/signal_phase_records/bari_arm_phase_mapping_sample/signal_phase_records.manifest.json)
- [road_movement_objects_signal_phase.manifest.json](../data/processed/movement_objects/bari_signal_phase_sample/road_movement_objects_signal_phase.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_movements_signal_phase_sample/node_year_metrics.manifest.json)
- [signal_phase_request_pack.manifest.json](../data/planning/signal_phase_requests/bari/signal_phase_request_pack.manifest.json)
- [signal_phase_acquisition_plan.manifest.json](../data/planning/signal_phase_acquisition/bari/signal_phase_acquisition_plan.manifest.json)
- [signal_phase_outreach_bundle.manifest.json](../data/planning/signal_phase_outreach/bari/signal_phase_outreach_bundle.manifest.json)
- [signal_phase_delivery_validation.manifest.json](../data/quality/signal_phase_delivery_validation/bari_controller_event_sample/signal_phase_delivery_validation.manifest.json)
- [signal_phase_delivery_session.manifest.json](../data/processed/signal_phase_delivery_sessions/bari_sample/signal_phase_delivery_session.manifest.json)

## Current Bari Signal-Node Stats

Signal layer:

- raw source rows: `419`
- coordinate-complete assets: `173`
- node objects built: `173`
- snapped to Bari segments: `173`
- mean nearest-segment distance: `1.87 m`

Crash-to-node matching with a `35 m` cutoff:

- coordinate-complete curated Bari official crashes: `13,859`
- matched to signal nodes: `1,800`
- unmatched at node level: `12,059`
- mean accepted node distance: `13.38 m`
- max accepted node distance: `34.96 m`

Node-year table:

- observed years: `2022-2025`
- node objects: `173`
- node-year rows: `692`
- crash-positive node-years: `526`
- zero-crash node-years: `166`
- total matched crashes: `1,800`
- total injuries: `776`

Signal type crash totals:

- `IMP. SEMAF`: `1,219`
- `ITS 2 MONKEY IMP. SEMAF`: `214`
- `ITS 2 MONKEY TELEC`: `347`
- `SOTTOPASSO`: `20`

## Early Hotspots

The highest crash-count node-years in the current table are concentrated on major Bari signalized corridors:

- `VIE ESTRAMURALE CAPRUZZI - B. CROCE` in `2024`: `21` crashes
- `VIE ESTRAMURALE CAPRUZZI - B. CROCE` in `2023`: `18` crashes
- `VIE ESTRAMURALE CAPRUZZI - G.PETRONI` in `2025`: `14` crashes
- `VIA EINAUDI-FANELLI` in `2025`: `12` crashes

## Mixed Bari Node Layer

Expanded object layer:

- crossing objects: `6,146`
- junction-approach objects: `1,180`
- unsignalized junction objects: `1,219`
- roundabout objects: `575`
- total objects: `9,120`
- crossings linked to a segment: `6,146`
- crossings linked to a signal anchor: `1,064`

Crash-to-node matching with a `30 m` cutoff:

- coordinate-complete curated Bari official crashes: `13,859`
- matched to mixed node objects: `8,761`
- unmatched at node level on this expanded surface: `5,098`
- mean accepted node distance: `9.75 m`
- max accepted node distance: `29.99 m`

Object-type split in the matched crashes:

- crossings: `4,709`
- unsignalized junctions: `2,478`
- junction approaches: `1,179`
- roundabouts: `395`

Expanded node-year table:

- observed years: `2022-2025`
- node objects: `9,120`
- node-year rows: `36,480`
- crash-positive node-years: `5,671`
- zero-crash node-years: `30,809`
- total matched crashes: `8,761`
- total injuries: `3,961`

Leading hotspots in the expanded table:

- Bari crossing `it-bari-crossing-node-2070` in `2024`: `18` crashes
- Bari unsignalized junction `it-bari-junction-329994343` in `2024`: `18` crashes
- Bari unsignalized junction `it-bari-junction-298917418` in `2024`: `15` crashes
- Bari approach `it-bari-signal-146::approach::drive_13227700650_13227700655_0` in `2025`: `12` crashes
- Bari roundabout `it-bari-roundabout-1481364124` in `2024`: `4` crashes

Crash-positive node-year rows by object family:

- crossings: `3,212`
- unsignalized junctions: `1,358`
- junction approaches: `788`
- roundabouts: `313`

## Conflict-Zone Layer

Conflict-zone layer:

- crossing conflict zones: `6,146`
- junction-approach conflict zones: `1,180`
- unsignalized-junction conflict zones: `1,219`
- roundabout-entry conflict zones: `653`
- roundabout fallback zones: `9`
- total conflict zones: `9,207`

Crash-to-zone matching with a strict inside-zone rule (`max_distance_m = 0`):

- coordinate-complete curated Bari official crashes: `13,859`
- matched to conflict zones: `6,286`
- unmatched outside conflict zones: `7,573`

Matched crash split by conflict-zone family:

- crossing conflict zones: `4,483`
- unsignalized-junction conflict zones: `1,257`
- junction-approach conflict zones: `389`
- roundabout-entry conflict zones: `148`
- roundabout fallback zones: `9`

Current conflict-zone control-state mix:

- signalized zones: `2,500`
- marked unsignalized zones: `2,582`
- uncontrolled zones: `2,244`
- unsignalized multi-arm zones: `1,219`
- yield-controlled roundabout-entry zones: `653`
- roundabout-core fallback zones: `9`

Current maneuver-complexity mix:

- crossing-only zones: `6,146`
- multi-choice zones: `2,111`
- limited-choice zones: `899`
- single-choice zones: `49`
- single-path zones: `2`

Matched crash split by conflict-zone control state:

- signalized: `2,038`
- uncontrolled: `1,506`
- marked unsignalized: `1,328`
- unsignalized multi-arm: `1,257`
- yield controlled: `148`
- roundabout core: `9`

Matched crash split by maneuver complexity:

- crossing only: `4,483`
- multi choice: `1,466`
- limited choice: `317`
- single choice: `19`
- single path: `1`

Largest turn-option catalogs in the current conflict-zone layer:

- `pedestrian_crossing`: `6,146` zones, `4,483` matched crashes
- `left | straight | right | u_turn`: `1,224` zones, `1,170` matched crashes
- `left | straight | right`: `415` zones, `187` matched crashes
- `straight | u_turn`: `350` zones, `155` matched crashes

## Movement-Object Layer

Movement-object layer:

- movement objects: `40,718`
- pedestrian-crossing movements: `6,146`
- signalized turn movements: `5,495`
- unsignalized turn movements: `27,428`
- roundabout-entry movements: `1,640`
- roundabout circulatory fallbacks: `9`
- explicit-target movements: `10,939`
- heuristic target resolutions: `469`
- ambiguous-target variants: `23,155`
- crossing-zone equivalents: `6,146`

Movement matching with a `15 m` nearest-object rule:

- coordinate-complete curated Bari official crashes: `13,859`
- matched to movement objects: `7,020`
- unmatched at movement level: `6,839`

Matched crash split by movement role:

- pedestrian crossing: `2,940`
- unsignalized turn movement: `2,231`
- signalized turn movement: `1,471`
- roundabout-entry movement: `373`
- roundabout circulatory fallback: `5`

Matched crash split by movement turn:

- cross: `2,940`
- straight: `1,783`
- right: `782`
- u turn: `769`
- left: `741`
- circulate: `5`

Matched crash split by movement resolution:

- crossing-zone equivalent: `2,941`
- explicit target: `2,132`
- ambiguous-target variant: `1,858`
- heuristic target resolution: `84`
- circulatory fallback: `5`

Matched crash split by signal-priority variant:

- major-minor priority: `2,231`
- signal phase unknown: `1,471`
- pedestrian uncontrolled: `1,409`
- pedestrian marked unsignalized: `1,029`
- pedestrian signalized: `503`
- yield entry: `372`
- circulating priority: `5`

Matched crash split by phase-priority group:

- uncontrolled crossing gap acceptance: `1,409`
- major-minor priority aligned turn: `1,258`
- signalized aligned turn phase unknown: `1,067`
- marked crossing priority: `1,029`
- major-minor priority crossing turn: `973`
- signalized pedestrian stage: `503`
- signalized crossing turn phase unknown: `404`
- roundabout yield entry: `372`
- roundabout circulatory priority: `5`

Movement-year table:

- movement objects: `40,718`
- movement-year rows: `162,872`
- crash-positive rows: `5,148`
- zero-crash rows: `157,724`
- total matched crashes: `7,020`
- total injuries: `3,219`

Leading movement hotspots:

- signalized movement `it-bari-signal-93::approach::drive_11003032474_278899643_0::zone::approach::movement::278899643_drive_11003032474_278899643_0_end::u_turn::drive_11003032474_278899643_0_end` in `2024`: `18` crashes
- pedestrian crossing movement `it-bari-crossing-node-2971::zone::crossing::movement::crossing` in `2024`: `17` crashes
- pedestrian crossing movement `it-bari-crossing-node-3690::zone::crossing::movement::crossing` in `2024`: `15` crashes
- pedestrian crossing movement `it-bari-crossing-node-3690::zone::crossing::movement::crossing` in `2023`: `15` crashes
- pedestrian crossing movement `it-bari-crossing-node-3648::zone::crossing::movement::crossing` in `2024`: `14` crashes

Signal-phase sample enrichment:

- normalized signal-phase records: `3`
- provider observations: `2`
- movement-phase mapping rows: `1`
- junctions with provider data: `1`
- movements with phase mapping: `1`
- movements with phase timing: `1`
- signalized movements with phase timing: `1`
- refreshed movement-year rows after sample join: `162,872`
- refreshed matched crashes in the sample movement-year table: `7,020`

Conflict-zone year table:

- conflict zones: `9,207`
- zone-year rows: `36,828`
- crash-positive zone-years: `3,946`
- zero-crash zone-years: `32,882`
- total matched crashes: `6,286`
- total injuries: `2,917`

Leading conflict-zone hotspots:

- Bari crossing conflict zone `it-bari-crossing-node-1107::zone::crossing` in `2024`: `18` crashes
- Bari crossing conflict zone `it-bari-crossing-node-2070::zone::crossing` in `2024`: `18` crashes
- Bari crossing conflict zone `it-bari-crossing-node-3688::zone::crossing` in `2023`: `15` crashes
- Bari crossing conflict zone `it-bari-crossing-node-3688::zone::crossing` in `2024`: `15` crashes

Crash-positive zone-year rows by conflict-zone family:

- crossing conflict zones: `2,720`
- unsignalized-junction conflict zones: `823`
- junction-approach conflict zones: `270`
- roundabout-entry conflict zones: `127`
- roundabout fallback zones: `6`

## Interpretation

- The Bari node-object layer is now real, reproducible, and tied both to an official municipal asset register and to a network-derived junction model.
- The Bari official crash source can now be analyzed as segment outcomes, signalized-node outcomes, and a broader mixed node surface spanning crossings, approaches, unsignalized junctions, and roundabouts.
- The new conflict-zone layer now makes the first explicit shift from object presence to operational risk areas and also carries reproducible movement/control-state labels, arm references, and turn-option catalogs derived from the current Bari geometry and tags.
- The new movement-object layer pushes that one step further by materializing explicit incoming-arm x outgoing-arm-candidate objects, not just turn-option summaries.
- The layer now has a first heuristic target-resolution policy: `469` movement objects are resolved by bearing-and-continuity ranking, and `84` matched crashes now land on those resolved movements rather than on fully duplicated candidate variants.
- A large share of the current layer is still candidate-based rather than uniquely resolved: `23,155` of `40,718` movement objects remain ambiguous-target variants, and `1,858` matched crashes still land on those ambiguous variants.
- The new Bari movement review pack turns that remaining gap into an operational queue: Bari now has `426` signalized junction phase-readiness rows and a crash-ranked unresolved-target review list instead of only a descriptive ambiguity count.
- The new Bari signal-phase intake pack turns that queue into a real onboarding surface: `20` priority signals are exported with `6` tier-1 immediate junctions, `3` reusable templates, and `3` mapping stubs for control-data intake.
- The signal-phase path is now executable end to end: sample stage, controller, and mapping extracts normalize cleanly and can be joined back onto the Bari movement layer.
- The new Bari signal-phase coverage report makes the current gap explicit: `44` movements now have junction-level provider data, but only `1` movement has phase timing, only `1` has phase mapping, and `0` matched crashes currently land on a timed or mapped movement.
- Bari signal `93` is the only current tier-1 junction with any provider coverage, and it still carries the top uncovered hotspot at `Via Giuseppe Capruzzi [u_turn]` with `50` matched crashes.
- The new Bari signal-phase target bundle turns the coverage report into a delivery-ready queue: `6` tier-1 dossiers now point to the exact uncovered movements that should drive the first real controller exports.
- The next blocker is now explicit and evidenced against the official Bari portal on `2026-03-28`: public signal inventory exists, but public controller timing and phase-control datasets do not, so the project needs restricted-data acquisition rather than another public-source crawl.
- The phase-priority split is now explicit enough for first control-aware movement screening, but the platform still lacks real controller timing coverage, lane-level structure, and richer roundabout internal paths.

## Next Step

Use the Bari signal-phase target bundle plus the outreach bundle to target the first real controller exports at the highest uncovered tier-1 movements, then run the received files through signal-phase delivery validation and the validated-delivery session runner before normalized ingestion and movement-phase joins.
