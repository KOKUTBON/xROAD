# Elderly & Disabled Road-User Safety

Older and disabled road users face distinct and often higher severity risk,
which matters especially in rural areas with ageing populations. The generic
VRU layer covers pedestrians and cyclists without **age- and
disability-specific** vulnerability; this module adds it.

Implementation: `src/road_risk_modeling/elderly_disabled_safety.py`. Demo:
`tools/elderly_disabled_demo.py` → `data/reporting/elderly_disabled_safety/`.

## 1. Age-band severity / elderly exposure

`elderly_exposure` reports the **65+ casualty share** where casualty age is
recorded, and falls back to an **ageing-area population proxy**
(`area_elderly_population_share`) where it is not — reporting which basis was
used (`recorded_casualty_age` / `ageing_area_proxy` / `unavailable`). The
platform is accident-level and holds no person-level age data by default, so the
proxy is the honest path until age-coded casualty data is onboarded.

## 2. Accessibility / disability infrastructure provision

`accessibility_provision` scores each segment over the disability-relevant
infrastructure provisions, renormalising over the provisions actually known and
reporting `coverage` and the **missing provisions**:

| Provision | Why it matters | Weight |
| --- | --- | --- |
| `pedestrian_crossing` | a formal crossing at all | 0.30 |
| `refuge_island` | crossing continuity / staged crossing for slower walkers | 0.25 |
| `dropped_kerb` | wheelchair / mobility-aid access | 0.25 |
| `lit` | lighting for low-vision and elderly users | 0.20 |

## 3. Elderly/disabled priority

`score_segment` combines **elderly exposure × accessibility deficit**, lifted
where there is a pedestrian/crossing context (where these users are actually
present), into a 0–100 priority. This surfaces elderly/disabled risk **distinctly**
from the generic VRU view — the same place can be low generic-VRU risk yet high
elderly/disabled priority because of a missing refuge or dropped kerb.

## 4. Tailored countermeasure profiles

Each segment's **missing provisions** map to a tailored countermeasure profile
from `COUNTERMEASURE_LIBRARY`, for the intervention briefs:

| Deficit | Measure | Benefits |
| --- | --- | --- |
| No crossing | Install a formal, high-visibility crossing | elderly, disabled, low-vision |
| No refuge | Add a central refuge island (staged crossing) | slower walkers, wheelchair users |
| No dropped kerb | Dropped kerbs with tactile paving | wheelchair / mobility-aid / visually-impaired |
| Poor lighting | Improve pedestrian-scale lighting | low-vision and elderly at dusk |
| Signal too fast | Extend crossing time to a slower walking speed | elderly and disabled pedestrians |

The run aggregates a **countermeasure demand** tally across the network, so a
programme manager sees which measure would benefit the most sections (in the
demo, central refuge islands lead).

## Honest scope

- Where casualty age is not recorded, exposure uses an **area proxy** — flagged
  per segment. Person-level age/disability data is **not** retained.
- Accessibility provisions are **as-attributed**; absent attributes lower the
  reported `coverage` rather than silently assuming provision.
- This is **decision support** for prioritising accessibility interventions, not
  an individual-level assessment.

## Relationship to other work

- Surfaces elderly/disabled groups distinctly within the VRU programme
  ([vru-intelligence.md](vru-intelligence.md), [vru-exposure-layer.md](vru-exposure-layer.md)).
- Countermeasures feed the [intervention briefs](intervention-briefs.md).

## CLI

```bash
road-risk elderly-disabled-assess \
  --segments path/to/segments.csv \
  --output-dir data/reporting/elderly_disabled_safety
```
