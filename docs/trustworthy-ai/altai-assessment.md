# ALTAI Self-Assessment

Self-assessment against the **Assessment List for Trustworthy AI (ALTAI)** of
the EU High-Level Expert Group on AI, across its seven requirements. Each
requirement records **status** (`met` / `partial` / `gap`), evidence, and any
open action.

This is a good-faith self-assessment for the current municipal-analytics scope.
It must be re-run before any deployment that changes the [AI Act
classification](eu-ai-act-classification.md).

## 1. Human agency and oversight — **met**

- All outputs are **decision support for a human road authority**; no automated
  action, no actuator control, no decision about any individual.
- The scenario/countermeasure layer produces **reviewable proposals**, not
  commitments ([model-cards.md](model-cards.md) card 4).
- *Action:* document a "human-in-command" note per pilot deployment contract.

## 2. Technical robustness and safety — **partial**

- Reproducible pipelines with lineage contracts and SHA-256 manifests
  ([docs/reproducibility.md](../reproducibility.md)); deterministic re-runs.
- Multiple baselines (naive, last-year, linear) bound every model's added value.
- Cross-jurisdiction transferability is **measured**, not assumed
  ([european-generalisation.md](../european-generalisation.md)).
- *Gap:* no adversarial-robustness testing (low relevance — no person-facing
  inputs) and the **severity model is fragile on sparse data** (documented in
  its model card). *Action:* gate severity outputs behind a minimum-positive
  threshold.

## 3. Privacy and data governance — **met**

- Full GDPR/DPIA layer ([docs/ethics/](../ethics/)); per-field classification
  and public-map aggregation floors ([docs/data-governance.md](../data-governance.md)).
- Data minimisation: models operate at **accident/segment level**; person- and
  vehicle-level rows are dropped on ingestion (e.g. BAAC `usagers`).

## 4. Transparency — **met**

- Model cards + dataset datasheets (this pack), uncertainty surfaced in outputs
  ([uncertainty-reporting.md](uncertainty-reporting.md)).
- Feature lists and metrics are public and reproducible.
- The scenario layer is **rule-based and auditable**.

## 5. Diversity, non-discrimination and fairness — **partial**

- Bias review covers under-reporting, exposure bias, urban/rural and VRU groups
  ([bias-fairness-review.md](bias-fairness-review.md)).
- The platform scores **infrastructure, not people**, which removes most
  protected-attribute concerns — but **under-reporting bias** can still
  systematically under-serve some areas.
- *Gap:* no automated fairness-metric monitoring in production. *Action:*
  add urban/rural capture-rate parity to the published QA pack.

## 6. Societal and environmental well-being — **met**

- Direct societal benefit: targeting interventions to reduce fatalities/injuries,
  aligned with Vision Zero and the Safe System approach.
- Low environmental footprint: lightweight tree models, CPU-only, no large-scale
  training; deterministic re-runs avoid wasteful recompute.

## 7. Accountability — **met**

- Every artifact is traceable to inputs via lineage contracts; auditability is
  built into the manifest scheme.
- This dossier + the ethics pack constitute the accountability record; the
  living-document policy assigns review on any material change.
- *Action:* name a per-deployment accountable owner (road authority DPO/owner).

## Overall

| Requirement | Status |
| --- | --- |
| 1 Human agency & oversight | met |
| 2 Technical robustness & safety | partial |
| 3 Privacy & data governance | met |
| 4 Transparency | met |
| 5 Diversity & fairness | partial |
| 6 Societal & environmental | met |
| 7 Accountability | met |

**Verdict:** the platform passes a documented ALTAI self-assessment for its
current minimal-risk analytics scope, with two `partial` items (robustness on
sparse severity data; production fairness monitoring) tracked as named actions.
