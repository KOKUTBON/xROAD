# Gender-Sensitive & Intersectional Approach

Road-safety burden is not evenly distributed across sex, age, location, and
disability. This document and the `intersectional_analysis` module integrate
gender and intersectional dimensions into the analysis so prevention can be
designed for the groups actually most at risk.

Implementation: `src/road_risk_modeling/intersectional_analysis.py`. Demo:
`tools/intersectional_demo.py` → `data/reporting/intersectional_analysis/`.

## The privacy tension, resolved

Disaggregation is needed for the analysis; the
[anonymisation policy](ethics/anonymisation-policy.md) demands protection of
sparse cells (sex + age + rural location + disability can identify individuals in
small areas). The resolution is **aggregate stratified counts with a k-anonymity
floor**: any stratum below `min_cell` (default 10) is **suppressed** — never
published or modelled at the individual level. In the demo, 14 of the finest
intersectional strata are suppressed for exactly this reason, leaving 18
publishable.

## 1. Sex/gender-disaggregated analysis

`stratify(rows, ["sex"])` produces sex-disaggregated casualty counts and
**fatal share** per group, suppressed below the floor. This is the base gender
view: are women or men over-represented in casualties and in fatal outcomes on
the target network?

## 2. Intersectional lens

`stratify(rows, ["sex", "age_band", "area_type", "disability"])` crosses the four
dimensions — **gender × age × rural location × disability** — so
that compounded disadvantage is visible (e.g. *elderly women in rural areas*, or
*disabled users in a given setting*) rather than averaged away. Intermediate
views (sex, sex × age, full stack) are all emitted, each independently
suppressed.

## 3. Bias check

Intersectional outputs feed the existing
[bias & fairness review](trustworthy-ai/bias-fairness-review.md): the
distributional fairness question — *does the tool direct safety investment
equitably across groups?* — is now answerable with the sex- and
intersectionally-disaggregated burden, not just the area-type split. The check:
prevention prioritisation should not under-serve a group whose casualties are
**under-reported** or **concentrated in suppressed small cells**; where a group's
strata are mostly suppressed, that is flagged as a coverage gap rather than read
as low risk.

## Honest scope

- Disaggregation depends on **sex/age/disability being recorded** on casualty
  data; where absent, strata fall into `unknown` (reported, not invented).
- All outputs are **aggregate and suppressed**; no individual-level gender or
  disability data is retained or modelled.
- This integrates the dimension into the *analysis*; richer causal gender
  analysis is left as future research.

## CLI

```bash
road-risk intersectional-analysis \
  --casualties path/to/casualties.csv \
  --output-dir data/reporting/intersectional_analysis \
  --min-cell 10
```
