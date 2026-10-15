# Research inputs

The operational research workspaces accept JSON objects. Import a local file or paste an object, run the analysis, and download the response. Inputs are sent to the configured API; imports are not automatically published or stored in a catalog.

## Collision reconstruction

`POST /v1/forensics/analyze` accepts `case_id`, `hazard_emergence_time_s`, `primary_agent`, and `secondary_agent`. Agent traces include characteristics and a `samples` array. See `agent_trace_from_mapping` and `build_forensic_case_from_payload` in `src/road_risk_modeling/forensic_reconstruction_engine.py` for the precise trace contract. Invalid inputs produce a validation error. Outputs are research estimates.

## Fleet advisories

`POST /v1/cits/ivi/compile` accepts incident, threat, corridor, location, coordinates, speed limits, precipitation, and lane restrictions. The result is a compiled message and transport envelopes, not a delivery receipt.

`POST /v1/cits/fleets/analyze` accepts a `message` object using that contract and a `vehicles` array. Each vehicle reports `vehicle_id`, `latitude`, `longitude`, and `speed_kmh`. Optional fields include `fleet_category`, `make_model`, and `heading_deg`.

## Traffic-response planning

`POST /v1/tmc/evaluate-trigger` accepts an organization identifier and observed threat parameters with corridor and location fields. The response is an advisory plan. No field transport adapter is included; the actuation endpoint rejects delivery requests rather than fabricating receipts.

## Incident coordination

`POST /v1/tmc/multi-incident/evaluate-conflicts` and `POST /v1/tmc/multi-incident/optimize-mitigation` accept `scenario_id`, `upstream_distance_km`, and `incidents`. Optimization also needs `alternative_corridors`.

Each incident includes `incident_id`, `corridor_id`, `location_name`, `latitude`, `longitude`, `severity`, `capacity_reduction_pct`, `incoming_flow_vph`, `residual_capacity_vph`, `nominal_capacity_vph`, and `candidate_detour_corridors`. Flow and capacity units are vehicles per hour. Consult `corridor_from_mapping` in `src/road_risk_modeling/incident_coordination_engine.py` for corridor inputs. Empty requests are rejected.

## Optional local catalogs

Operators may create JSON arrays under `data/operations/`, relative to `ROAD_RISK_API_ROOT_DIR`:

- `forensic_cases.json`: reconstruction input objects.
- `incident_scenarios.json`: coordination input objects.
- `tmc_incidents.json`: arguments accepted by `open_tmc_incident`.
- `ivi_messages.json`: advisory input objects.
- `fleet_telemetry.json`: reported vehicle positions.

Missing files mean no observations. Invalid files are configuration errors. Catalog files are ignored by Git. Only release data you are authorized to redistribute, with appropriate provenance and licensing.
