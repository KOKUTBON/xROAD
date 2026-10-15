# Reproducibility And Run Registry

The project now includes a first reproducibility layer built around a run registry.

## Purpose

The registry gives the project a machine-readable inventory of the artifacts already produced under `data/`. It is not a scheduler or full experiment tracker yet. Its current job is to make the existing pipeline outputs traceable enough to answer basic lineage questions:

- which manifests and metrics exist
- which stage produced them
- which input paths they reference
- which output artifact is the primary product of each run
- which model/evaluation runs carry an explicit training configuration and publication-facing lineage contract

## Command

Build or refresh the registry with:

```bash
road-risk build-run-registry --data-root data --output-dir data/registry
```

This writes:

- `data/registry/run_registry.jsonl`
- `data/registry/run_registry.csv`
- `data/registry/run_registry.manifest.json`

## Published Refresh

Refresh the registry-backed published outputs with:

```bash
road-risk build-published-refresh-bundle \
  --data-root data \
  --registry-output-dir data/registry \
  --published-index-output-dir data/published_index \
  --dashboard-output-dir data/dashboard \
  --output-dir data/reporting/published_refresh/latest
```

This orchestration now:

- rebuilds the registry snapshot used for latest-resource selection
- rebuilds the published-resource index with explicit latest-vs-stale flags per lookup scope
- propagates stable lineage traces from published outputs back to source metrics and training configs
- auto-selects dashboard transferability inputs from the latest benchmark recommendation when available
- rebuilds the dashboard summary without manual artifact relinking
- emits an operator refresh bundle plus a recurring schedule template under `data/reporting/published_refresh/latest`

## Current Registry Snapshot

From the current manifest at `data/registry/run_registry.manifest.json`:

- registry version: `run_registry_v1`
- scanned documents: `434`
- excluded output directory: `data/registry`

Current top-level stage counts:

- aggregation: `26`
- enrichment: `25`
- evaluation: `14`
- ingestion: `21`
- matching: `13`
- modeling: `22`
- object modeling: `4`
- quality: `37`
- reporting: `243`
- segmentation: `16`
- serving: `10`

Current high-signal artifact counts:

- frequency model: `16`
- transferability: `14`
- transferability benchmark: `1`
- prediction store: `4`
- public score tiles: `4`
- published resource index: `1`
- published refresh bundle: `1`
- vru exposure bundle: `1`
- dashboard summary: `1`

For the full current artifact-kind inventory, use:

- [run_registry.manifest.json](../data/registry/run_registry.manifest.json)
- [run_registry.csv](../data/registry/run_registry.csv)
- [run_registry.jsonl](../data/registry/run_registry.jsonl)

## Output Structure

`run_registry.jsonl` is the full machine-readable export. Each line contains:

- `entry_id`
- `artifact_kind`
- `stage`
- `run_label`
- `document_path`
- `document_sha256`
- `document_mtime_utc`
- `summary`
- `policy`
- `input_references`
- `output_references`
- `primary_output_path`

`run_registry.csv` is the compact analyst-oriented summary. It currently surfaces:

- holdout year
- exposure policy version
- training task and split strategy where present
- lineage contract version plus upstream and publishable output counts where present
- random-forest tree count where relevant
- frequency deviance and top-5% crash share where relevant
- severity ROC AUC and average precision where relevant

## Captured Training Config And Lineage

Refreshed modeling and evaluation metrics now persist two additional top-level blocks:

- `training_config`
- `lineage`

`training_config` captures the stable run definition:

- task name
- split strategy
- target or label definition
- estimator settings
- feature inventory
- referenced input artifacts with paths and checksums

`lineage` captures the downstream traceability contract:

- the run-record metrics file
- upstream input artifacts
- publishable outputs such as holdout predictions
- supporting artifacts such as model bundles

Current refreshed examples:

- [frequency_baseline.metrics.json](../data/models/bari_frequency_baseline_context_v2/frequency_baseline.metrics.json)
- [severity_baseline.metrics.json](../data/models/bari_severity_baseline_context_v2/severity_baseline.metrics.json)
- [frequency_transferability.metrics.json](../data/models/frequency_transferability_bari_foggia_taranto_lecce_municipalities_context_v2_temporal_rf25/frequency_transferability.metrics.json)
- [road_node_objects.manifest.json](../data/processed/node_objects/bari_crossing_approaches/road_node_objects.manifest.json)
- [road_conflict_zones.manifest.json](../data/processed/conflict_zones/bari/road_conflict_zones.manifest.json)
- [road_movement_objects.manifest.json](../data/processed/movement_objects/bari/road_movement_objects.manifest.json)
- [road_movement_objects_signal_phase.manifest.json](../data/processed/movement_objects/bari_signal_phase_sample/road_movement_objects_signal_phase.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_crossing_approaches/node_year_metrics.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_conflict_zones/node_year_metrics.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_movements/node_year_metrics.manifest.json)
- [node_year_metrics.manifest.json](../data/processed/node_aggregates/bari_open_data_movements_signal_phase_sample/node_year_metrics.manifest.json)
- [signal_phase_records.manifest.json](../data/processed/signal_phase_records/bari_stage_plan_sample/signal_phase_records.manifest.json)
- [signal_phase_records.manifest.json](../data/processed/signal_phase_records/bari_controller_event_sample/signal_phase_records.manifest.json)
- [signal_phase_records.manifest.json](../data/processed/signal_phase_records/bari_arm_phase_mapping_sample/signal_phase_records.manifest.json)
- [signal_phase_request_pack.manifest.json](../data/planning/signal_phase_requests/bari/signal_phase_request_pack.manifest.json)
- [signal_phase_acquisition_plan.manifest.json](../data/planning/signal_phase_acquisition/bari/signal_phase_acquisition_plan.manifest.json)
- [signal_phase_outreach_bundle.manifest.json](../data/planning/signal_phase_outreach/bari/signal_phase_outreach_bundle.manifest.json)
- [signal_phase_request_scope_bundle.manifest.json](../data/reporting/signal_phase_request_scope/bari/signal_phase_request_scope_bundle.manifest.json)
- [signal_phase_contact_bundle.manifest.json](../data/planning/signal_phase_contact/bari/signal_phase_contact_bundle.manifest.json)
- [signal_phase_contact_resolution_bundle.manifest.json](../data/planning/signal_phase_contact_resolution/bari/signal_phase_contact_resolution_bundle.manifest.json)
- [signal_phase_dispatch_bundle.manifest.json](../data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.manifest.json)
- [signal_phase_delivery_intake_bundle.manifest.json](../data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.manifest.json)
- [signal_phase_delivery_monitor_bundle.manifest.json](../data/reporting/signal_phase_delivery_monitor/bari/signal_phase_delivery_monitor_bundle.manifest.json)
- [signal_phase_action_queue.manifest.json](../data/reporting/signal_phase_action_queue/bari/signal_phase_action_queue.manifest.json)
- [signal_phase_action_execution_bundle.manifest.json](../data/reporting/signal_phase_action_execution/bari/signal_phase_action_execution_bundle.manifest.json)
- [signal_phase_action_handoff_bundle.manifest.json](../data/reporting/signal_phase_action_handoff/bari/signal_phase_action_handoff_bundle.manifest.json)
- [signal_phase_operator_board_bundle.manifest.json](../data/reporting/signal_phase_operator_board/bari/signal_phase_operator_board_bundle.manifest.json)
- [signal_phase_dispatch_execution_bundle.manifest.json](../data/reporting/signal_phase_dispatch_execution/bari/signal_phase_dispatch_execution_bundle.manifest.json)
- [signal_phase_dispatch_recording_bundle.manifest.json](../data/reporting/signal_phase_dispatch_recording/bari/signal_phase_dispatch_recording_bundle.manifest.json)
- [signal_phase_dispatch_repair_bundle.manifest.json](../data/reporting/signal_phase_dispatch_repair/bari/signal_phase_dispatch_repair_bundle.manifest.json)
- [signal_phase_dispatch_repair_execution_bundle.manifest.json](../data/reporting/signal_phase_dispatch_repair_execution/bari/signal_phase_dispatch_repair_execution_bundle.manifest.json)
- [signal_phase_dispatch_repair_recording_bundle.manifest.json](../data/reporting/signal_phase_dispatch_repair_recording/bari/signal_phase_dispatch_repair_recording_bundle.manifest.json)
- [signal_phase_dispatch_repair_status_bundle.manifest.json](../data/reporting/signal_phase_dispatch_repair_status/bari/signal_phase_dispatch_repair_status_bundle.manifest.json)
- [signal_phase_dispatch_validation_bundle.manifest.json](../data/quality/signal_phase_dispatch_validation/bari/signal_phase_dispatch_validation_bundle.manifest.json)
- [signal_phase_dispatch_writeback_bundle.manifest.json](../data/reporting/signal_phase_dispatch_writeback/bari/signal_phase_dispatch_writeback_bundle.manifest.json)
- [signal_phase_dispatch_cycle.manifest.json](../data/processed/signal_phase_dispatch_cycles/bari/signal_phase_dispatch_cycle.manifest.json)
- [signal_phase_runtime_cycle.manifest.json](../data/processed/signal_phase_runtime_cycles/bari/signal_phase_runtime_cycle.manifest.json)
- [signal_phase_runtime_rehearsal.manifest.json](../data/reporting/signal_phase_runtime_rehearsal/bari/signal_phase_runtime_rehearsal.manifest.json)
- [signal_phase_delivery_validation.manifest.json](../data/quality/signal_phase_delivery_validation/bari_controller_event_sample/signal_phase_delivery_validation.manifest.json)
- [signal_phase_delivery_validation.manifest.json](../data/quality/signal_phase_delivery_validation/bari_stage_plan_sample/signal_phase_delivery_validation.manifest.json)
- [signal_phase_delivery_validation.manifest.json](../data/quality/signal_phase_delivery_validation/bari_arm_phase_mapping_sample/signal_phase_delivery_validation.manifest.json)
- [signal_phase_delivery_validation.manifest.json](../data/quality/signal_phase_delivery_validation/bari_support_diagram_sample/signal_phase_delivery_validation.manifest.json)
- [signal_phase_support_resolution_bundle.manifest.json](../data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.manifest.json)
- [signal_phase_support_status_bundle.manifest.json](../data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.manifest.json)
- [signal_phase_support_action_queue.manifest.json](../data/reporting/signal_phase_support_action_queue/bari/signal_phase_support_action_queue.manifest.json)
- [signal_phase_support_writeback_bundle.manifest.json](../data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.manifest.json)
- [signal_phase_support_workbook_completion_bundle.manifest.json](../data/reporting/signal_phase_support_workbook_completion/bari/signal_phase_support_workbook_completion_bundle.manifest.json)
- [signal_phase_support_validation_batch.manifest.json](../data/quality/signal_phase_support_validation_batches/bari/signal_phase_support_validation_batch.manifest.json)
- [signal_phase_support_apply_cycle.manifest.json](../data/processed/signal_phase_support_apply_cycles/bari/signal_phase_support_apply_cycle.manifest.json)
- [signal_phase_delivery_session.manifest.json](../data/processed/signal_phase_delivery_sessions/bari_sample/signal_phase_delivery_session.manifest.json)
- [segment_scores.manifest.json](../data/prediction_store/bari_frequency_baseline_context_v2/segment_scores.manifest.json)
- [score_tiles.manifest.json](../data/prediction_store/bari_frequency_baseline_context_v2_tiles_500m/score_tiles.manifest.json)

## Current Constraints

This is intentionally a first step, not a full MLOps stack.

- It indexes artifacts after they exist; it does not orchestrate runs.
- It does not yet capture the full training configuration beyond what is already present in metric files.
- It now emits formal lineage contracts for published segment-score and tile artifacts, and a static published-resource index can now be built from the registry for downstream consumers.
- It does not yet schedule refreshes or model retraining.

## Next Extension

The next useful extension is to turn the registry and published-resource index into explicit refresh workflows, then bind dashboard or API snapshots to those same lineage contracts.
