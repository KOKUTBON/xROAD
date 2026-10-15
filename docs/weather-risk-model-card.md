# Weather-Conditioned Risk Model Card

## Intended use

`weather_risk_model_v1` estimates crash rate per observed condition-hour for
road segments and nodes. It is intended for network screening, climate
resilience planning, and weather-relevant countermeasure triage. It is not a
real-time closure system or a substitute for engineering inspection.

## Training target and architecture

The training table is segment-condition-year grain. The target is crashes per
condition-hour (or severity-weighted crashes when supplied). A seeded gradient
boosting regressor learns log rate from road attributes, weather condition, and
explicit road-attribute × weather interactions. Condition-hours are sample
weights.

Segment and city residual effects are partially pooled: sparse segments and
cities shrink toward the network model, while supported groups retain more of
their observed deviation. Predictions include a residual-based interval and
cold-start status.

## Validation

The evaluator uses a temporal holdout: training through 2023 and testing from
2024. It reports crash-count MAE against the former network-wide heuristic,
predicted versus observed adverse-condition crash share, and per-city MAE for
Bari, Foggia, Taranto, and Lecce. Promotion requires lower holdout MAE than the
heuristic on a real weather-joined crash dataset.

The committed unit fixture deliberately contains known speed×rain and
bridge×wind interactions to verify that the model can recover signal and beat
the fixed baseline. It is a method test, not evidence of real-world skill.

## Climate integration

`model_derived_hazard_profile()` produces per-segment multipliers, confidence
intervals, and model-derived flood/snow-ice/wind/heat weights.
`climate_resilience.py` uses these values when present and labels the output
`trained_model`; otherwise it retains the old 25% adverse-share calculation and
fixed weights under the explicit label `heuristic_fallback`.

Weather-sensitive sites can surface drainage, anti-skid, adaptive-lighting, and
wind-control countermeasure prompts for the AI recommendation workflow.

## Limitations

- Reanalysis grid weather is not a street-level sensor observation.
- Sparse severe conditions produce wide intervals.
- Exposure completeness and timestamp precision directly constrain validity.
- Gradient, surface, lighting, and structure attributes may be proxies.
- Cross-city validation is descriptive until each city has comparable joined
  weather history.
- No municipal action should be automated from this model.
