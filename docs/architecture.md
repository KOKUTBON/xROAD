# Target Architecture

This document describes the analytics and serving architecture for the core engine.

The accepted
[ML training and serving ADR](adr-ml-training-serving-architecture.md)
specializes this target for registry, feature, worker, tenancy, and inference
decisions.

For deployment and operations, see [MLOps workflow](mlops-workflow.md) and
the infrastructure examples under `infra/`.

## 1. Design Goal

Build a portable road-safety analytics platform that can be configured per jurisdiction without rewriting the core pipeline.

The architecture must support:

- different crash data schemas by country or city
- repeated yearly data refreshes
- multiple modeling tasks
- production-safe spatial querying
- restricted and public views of the same analytical outputs

## 2. Architecture Principles

- Separate source-specific ingestion from canonical modeling tables.
- Use road segments as the primary analysis unit for crash frequency and hotspot modeling.
- Keep crash-event modeling separate from severity modeling.
- Treat exposure as a first-class concept, not an optional enhancement.
- Calibrate by jurisdiction instead of assuming a single universal model.
- Make all feature generation reproducible and configuration-driven.

## 3. Proposed Layers

```mermaid
flowchart LR
    A["Source Adapters"] --> B["Canonical Crash Store"]
    B --> C["Road Network & Segmentation"]
    C --> D["Feature Enrichment"]
    D --> E["Model Training & Evaluation"]
    E --> F["Prediction Store"]
    F --> G["API Layer"]
    G --> H["Public Map & Analyst Dashboard"]
```

## 4. Source Adapters

Each jurisdiction should have an adapter that maps local fields to the canonical schema.

Examples:

- `istat_it`
- `aci_it`
- `city_open_data_generic`
- `country_police_feed_generic`

An adapter is responsible for:

- parsing input files
- normalizing column names
- converting local codes
- applying timezone and date rules
- flagging invalid or suspicious coordinates
- emitting canonical crash events plus row-level audit metadata

## 5. Canonical Entities

### `CrashEvent`

One record per crash, with normalized location, time, severity, and source identifiers.

### `RoadSegment`

One record per analysis segment, derived from a road graph. Segments should be stable enough to compare across time, but configurable by jurisdiction.

### `FeatureSnapshot`

One record per `RoadSegment` and time window, containing static and dynamic features.

### `PredictionRun`

Metadata for training data, feature set, model version, evaluation protocol, and output artifacts.

### `UserScope`

Access rules for public users, municipal officers, and administrators.

## 6. Storage Strategy

### Development and analytics

Use:

- Parquet for durable tables
- DuckDB for local joins, QA, and feature generation

Reasons:

- simple local workflow
- reproducible analytical snapshots
- easy SQL over tabular and geospatial outputs

### Production serving

Use:

- PostGIS for spatial API serving
- object storage or filesystem for Parquet model artifacts

Reasons:

- mature spatial indexing
- better fit for concurrent API traffic
- easy integration with server-side filtering

## 7. Feature Groups

### Static road-network features

- segment length
- number of lanes
- speed limit where available
- road class
- curvature proxies
- distance to intersections
- roundabout flag
- centrality / network role
- grade / slope

### Spatial context features

- population density
- land-use mix
- school proximity
- transit stop density
- pedestrian crossing context
- POI density

### Dynamic features

- hour and weekday
- seasonality
- daylight / night
- weather archive variables
- event calendar or holiday flags
- traffic exposure or proxy exposure

## 8. Modeling Modules

### Segment frequency module

Purpose:

- predict expected crash count or risk level by segment and time window

Candidates:

- Poisson / Negative Binomial style baselines
- tree-based regressors or rankers
- later hierarchical or graph-based models

### Severity module

Purpose:

- predict probability of severe outcomes once a crash context is defined

Candidates:

- Random Forest
- gradient boosting
- calibrated probabilistic classifiers

### Vulnerable-road-user module

Purpose:

- focused analytics for pedestrians and cyclists

This should be a dedicated workstream, not only a filtered view.

## 9. Evaluation Framework

Every model run should report:

- in-jurisdiction validation
- held-out year validation
- held-out city or municipality validation
- calibration metrics
- ranking metrics for hotspot prioritization
- fairness / subgroup diagnostics where feasible

Recommended minimum split rules:

- `TimeSeriesSplit` or rolling-year holdout for time
- `GroupKFold` by municipality, province, or country for geography

## 10. Serving Layer

The API should expose:

- aggregated public heatmaps
- segment-level risk surfaces
- analyst queries for authorized municipalities
- export endpoints for reports and intervention planning

The legacy diary already identifies the need for:

- server-side filtering
- municipality-scoped access
- anonymous vs authenticated views

That requirement should be preserved in the formal design.

## 11. Recommended Near-Term Build Order

1. Adapter framework and canonical schema
2. Legacy Puglia importer
3. Segment generator for one pilot area
4. Weather and population enrichment
5. Baseline crash-frequency model
6. Baseline severity model
7. Spatial API and simple dashboard
8. Authentication and authorization
