# Exposure Policy

This document records the documented exposure policy implemented in the project on March 28, 2026 and its first built-environment update.

## Purpose

The project should not treat raw crash counts as reusable risk scores without an explicit exposure view.

The current policy does not claim to be traffic flow. It is a documented proxy that makes the modeling assumptions inspectable and versioned while real traffic inputs are still missing.

## Current Policy

- policy version: `segment_exposure_v2_static_context_built_env`
- code entry point:
  - [exposure_policy.py](../src/road_risk_modeling/exposure_policy.py)
- file application command:
  - [cli.py](../src/road_risk_modeling/cli.py)

## Inputs

The policy is designed to work on whatever segment context is already available.

Primary inputs:

- segment length
- lane count
- max speed
- width
- road class rank
- node degree / connector status
- dead-end status
- segment-name presence
- POI context counts when available
- land-use context counts when available
- office and selected built-environment counts when available

## Policy Components

The policy decomposes exposure into five inspectable pieces plus a backward-compatible alias.

### Movement

`exposure_movement_index`

This approximates how much through movement a segment can plausibly carry using:

- length
- lanes
- speed
- width
- road class

### Activity

`exposure_activity_index`

This approximates nearby trip generation and stopping activity using a weighted POI score:

- education
- healthcare
- transit
- retail
- hospitality
- leisure
- total nearby POIs

### Built Environment

`exposure_built_environment_index`

This approximates built-up intensity and a first population or demand proxy using:

- residential land-use counts
- commercial land-use counts
- industrial land-use counts
- office context
- selected built-environment counts when available

The policy also writes:

- `exposure_population_proxy_index`

This is a narrower residential-weighted proxy extracted from the same context surface.

### Network

`exposure_network_index`

This approximates how much the segment participates in the surrounding circulation structure using:

- endpoint degree
- intersection-connector status
- dead-end status
- segment-name presence

### Completeness

`exposure_data_completeness`

This measures how much of the policy input surface is actually available for a segment. It does not represent exposure itself; it down-weights confidence in the proxy where coverage is sparse.

## Output Columns

The policy writes:

- `exposure_policy_version`
- `exposure_policy_index`
- `exposure_movement_index`
- `exposure_activity_index`
- `exposure_network_index`
- `exposure_built_environment_index`
- `exposure_population_proxy_index`
- `exposure_weighted_poi_score`
- `exposure_data_completeness`

For backward compatibility, it also writes:

- `exposure_proxy_index`

This is now an alias for `exposure_policy_index`.

## Training Label Alignment

The project now aligns training outputs with the documented policy by writing:

- `crashes_per_exposure_policy`
- `fatalities_per_exposure_policy`
- `injuries_per_exposure_policy`

These sit alongside the older proxy-rate columns for compatibility.

## Current Evidence

On the Bari v2 context pilot:

- mean exposure policy index: `0.9133`
- mean built-environment index: `1.4249`
- mean population-proxy index: `1.2517`
- mean completeness: `0.6674`
- `10,524` context features were retrieved, with `7,230` segments receiving at least one built-environment hit
- frequency random-forest Poisson deviance improved from the prior v1 policy rerun’s `0.3684` to `0.3673`
- frequency random-forest RMSE improved from `0.6046` to `0.6013`
- frequency random-forest top-5% crash capture slipped from `44.81%` to `43.96%`
- severity random-forest ROC AUC fell from the prior context band of `0.7242-0.7254` to `0.7017`
- severity random-forest average precision stayed near-flat at `0.0195`
- severity top-10% fatal recall recovered to `40%`, while top-20% fatal recall settled back to `50%`

Interpretation:

- the built-environment update helps Bari frequency fit more than it helps Bari ranking concentration
- the same update does not yet improve Bari severity, which suggests the current land-use and demand proxy is more useful for occurrence than for fatal-outcome discrimination

## Limitations

- It is still a proxy, not observed traffic exposure.
- It still does not use observed traffic flow or external population rasters.
- The cleaned Puglia legacy CSV is only year-resolved, so daylight and finer time-of-day exposure need a richer crash source.
- It does not yet distinguish weekday versus weekend traffic patterns.
- The municipality-scale transfer rerun with the v2 built-environment update is now available, but the results are mixed rather than uniformly better.

## Next Step

1. add weather, daylight, and population context to the exposure stack
2. decide whether municipality-scale transferability should use only the composite policy index or the decomposed component features as well
3. replace the proxy with true traffic or stronger demand indicators when available
