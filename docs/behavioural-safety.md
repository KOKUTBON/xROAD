# Behavioural-Safety Analytics Layer

Enforcement strategies work best when they are targeted by evidence. The
platform is primarily infrastructure- and place-focused; this module adds the
**behavioural and enforcement evidence layer** — **where and when**
behavioural-crash risk concentrates — so authorities can target enforcement and
incentives.

Implementation: `src/road_risk_modeling/behavioural_safety.py`. Demo:
`tools/behavioural_safety_demo.py` → `data/reporting/behavioural_safety/`.

## Privacy guardrail (the design constraint, stated first)

This layer is **aggregate-only** and provides **no person-level profiling or
targeting**. Consistent with the [DPIA](ethics/dpia.md) purpose-limitation and
**GDPR Art. 22** (no automated individual decisions):

- outputs are **corridor × time-of-day aggregates**, never individuals or
  vehicles;
- cells below an **anonymity floor** (`min_cell`, default 5 crashes) are
  **suppressed**;
- no driver/vehicle identifiers are ever emitted.

The "multi-offender" concern is addressed at the **population/
evidence** level (where risky-driving crashes cluster), not by tracking
individuals — which would be outside the platform's lawful basis.

## 1. Behaviour-related crash typing

`behavioural_crash_indicator` types each crash from the signals the platform
actually holds:

| Signal | Source | Behavioural KPI it proxies |
| --- | --- | --- |
| `speeding` | observed 85th-percentile speed vs limit (`observed_p85_speed_kph` vs `observed_speed_limit_kph`) | **Speed** |
| `night_or_weekend` | crash hour / weekday | **Sober driving** (proxy) |
| `vru_unprotected` | VRU involvement | **Protective equipment** (proxy) |

`speeding_pressure` normalises how far operating speed exceeds the limit
(0 at the limit, 1 at +20 km/h). Each crash gets a composite behavioural weight.

## 2. Enforcement prioritisation

`build_enforcement_priorities` aggregates behavioural-crash risk by
**corridor × time-of-day** (overnight / morning / afternoon / evening) and ranks
cells by a **concentration score** (behavioural crashes × mean behavioural
weight), after suppressing sub-floor cells. The output answers the operational
question directly: *which corridor, at which time of day, should enforcement and
incentives target?* In the demo, the high-speeding corridor surfaces across all
time buckets with `speeding` as the dominant signal.

## 3. EC behavioural-KPI evidence framework

`BEHAVIOURAL_KPIS` maps the four EC behavioural Safe-System KPIs to the platform
signal that evidences each — and is **explicit where a signal is not yet held**
rather than inventing it:

| EC KPI | Platform signal | Status |
| --- | --- | --- |
| Speed | observed p85 vs limit | **available** |
| Sober driving | night/weekend over-representation | proxy only |
| Protective equipment | VRU / unprotected-user share | proxy only |
| Distraction | requires crash-narrative coding | **not held** |

Closing the proxy/not-held gaps needs impairment and narrative coding on crash
records (a data-onboarding item), not new modelling.

## 4. Incentive-mechanism evaluation support (design note)

The same corridor × time aggregates provide the **before/after evaluation
baseline** for incentive schemes (e.g. a speed-reduction campaign or a
gamified-compliance pilot): take the behavioural concentration on the target
corridors before the intervention, re-run after, and read the change with the
platform's existing uncertainty discipline
([uncertainty reporting](trustworthy-ai/uncertainty-reporting.md)). Because the
layer is aggregate, incentive evaluation never requires individual tracking —
the evaluation unit is the corridor-period, not the driver.

## Honest scope

- Speeding is the one **directly observed** behavioural signal; sober-driving
  and protective-equipment are **proxies**, and distraction is **not held** —
  all flagged in the KPI framework.
- The committed extract is a **structurally-faithful sample**; the privacy
  controls (aggregate-only, cell suppression) and the corridor × time method
  carry over unchanged to real enforcement data.
- This is **decision support for enforcement targeting**, not an enforcement
  decision about any individual.

## CLI

```bash
road-risk behavioural-analysis \
  --crashes path/to/crashes.csv \
  --output-dir data/reporting/behavioural_safety \
  --min-cell 5
```
