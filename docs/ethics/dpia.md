# Data Protection Impact Assessment (DPIA)

**Regulation:** GDPR (EU) 2016/679, Article 35.
**System:** Road Accidents Risk Modeling platform (`v1.0.0` municipal baseline).
**Status:** Template / first assessment — 2026-06-17. To be reviewed and signed off per deployment by the controller's DPO.

A DPIA is required here because the processing is **likely to result in a
high risk** under Art. 35(3) and the EDPB criteria: it involves systematic
evaluation/scoring of geographic risk, large-scale processing of data that
can be location-sensitive, matching/combining datasets from multiple
sources, and — in the roadmap — innovative use of sensing technology
(trajectory/near-miss, V2I) that can observe individuals in public space.

---

## 1. Description of the processing

### 1.1 Nature, scope, context, and purposes

- **Purpose.** Identify, rank, and explain road-collision risk at segment,
  junction, and crossing level so that road authorities can prioritise
  safety interventions (Safe System / Vision Zero). The processing is in the
  **public interest** (road safety) — see legal basis in
  [records-of-processing.md](records-of-processing.md).
- **Scope today (`v1.0`).** Historical crash records (Puglia legacy +
  official Bari open data 2022–2025), road network geometry (OSM), and
  derived risk artifacts. Pilots: Bari, Foggia, Taranto, Lecce.
- **Scope on the roadmap.** Motor-flow / observed-speed / VRU exposure
  connectors (Issue 16), conflict & trajectory intelligence (Issue 21),
  and a bounded digital twin with V2I / roadside sensing (Issue 22).
- **Context.** B2G/G2G; the controller is normally the municipal or
  regional road authority, the operator is a processor (Art. 28).

### 1.2 Data categories

| Category | Examples in this platform | Personal data? |
| --- | --- | --- |
| Crash event attributes | year/month/day/hour, roadway type, light/weather, severity band | Not directly identifying, but **can become personal** when combined with precise time + location (an identifiable individual was involved in a specific crash). |
| Precise location | `latitude` / `longitude` of a crash | Potentially personal via re-identification (small areas, rare events). Classified `restricted`. |
| Casualty counts | `fatalities`, `injuries` | Relate to identifiable persons; special-category-adjacent (health/death). Classified `restricted`, 5-row aggregation floor. |
| Free-text / source extras | `extra` blob carried from source systems | May contain identifiers; classified `sensitive`, never published row-level. |
| **Roadmap — trajectory/sensing** | movement zones, near-miss tracks, V2I/roadside sensor feeds | **Likely personal data** (behaviour of identifiable road users); special care for VRUs. Not yet ingested. |
| Platform user accounts | analyst/admin/operator identities, audit logs | Personal data of platform users (staff). |

**Special categories (Art. 9).** The platform does **not** intentionally
process health data about named individuals. Casualty severity is handled
only as aggregate counts behind an aggregation floor. Death/injury data is
treated with special-category-level caution even though crash statistics are
generally not Art. 9 data once de-identified.

### 1.3 Data subjects

Persons involved in recorded crashes; road users observed by future sensing
inputs (drivers, pedestrians, cyclists, micromobility users — including
vulnerable groups); and platform users (authority staff).

---

## 2. Necessity and proportionality

- **Lawfulness, fairness, transparency.** Legal basis is documented per
  source in the RoPA (primarily Art. 6(1)(e) public interest for the
  authority-held crash data; Art. 6(1)(f) / contract for operational
  feeds). A public-facing privacy notice is required per deployment.
- **Purpose limitation.** Data is used only for road-safety risk modelling
  and intervention prioritisation. Reuse for enforcement against named
  individuals is **out of scope and prohibited** by design.
- **Data minimisation.** Direct identifiers are not required for the model.
  Modelling operates on canonical entities and aggregates; precise
  coordinates and counts are `restricted` and never published row-level
  (see [privacy-by-design.md](privacy-by-design.md)).
- **Accuracy.** QA/curation stages (`qa-canonical`, `curate-canonical`)
  flag and exclude blocking geospatial/quality issues; lineage is captured
  in the run registry.
- **Storage limitation.** Retention is bounded per data class (see
  `retention_rules` in [data-governance.md](../data-governance.md));
  provider raw exports are purged after normalisation (+30-day quarantine);
  audit logs capped at 24 months.
- **Proportionality of granularity.** Public surfaces are banded/indexed and
  gated by a ≥5 aggregation floor; precise location and counts stay internal.

---

## 3. Risks to data subjects and mitigations

| # | Risk | Likelihood / severity (pre-mitigation) | Mitigation | Residual |
| --- | --- | --- | --- | --- |
| R1 | **Re-identification of a crash victim** by joining precise coordinates + exact time in a sparse area | Medium / High | Coordinates `restricted`; public surfaces aggregated to segment/tile with ≥5 floor; see [anonymisation-policy.md](anonymisation-policy.md) | Low |
| R2 | **Disclosure of casualty/health detail** linkable to a person | Medium / High | Counts `restricted` with 5-row floor; only relative reductions / bands published | Low |
| R3 | **Function creep** — risk scores reused for individual enforcement / insurance | Medium / High | Purpose limitation in this DPIA + processor agreement; no person-level output is produced | Low |
| R4 | **Leakage of `sensitive` source `extra` fields** containing identifiers | Low / High | `sensitive` class never published row-level; publication surface fails closed (`KeyError` on unclassified field) | Low |
| R5 | **Roadmap: trajectory/sensing observes identifiable road users**, esp. VRUs | High / High | Not yet active. Requires DPIA update, edge anonymisation, no raw-track retention, and a fresh necessity test before any pilot (Issues 21–22) | **Open — gated** |
| R6 | **Bias / unfair prioritisation** (under-reporting, exposure bias across areas/VRU groups) | Medium / Medium | Fairness review, model cards, uncertainty reporting | Medium — in progress |
| R7 | **Security breach / unauthorised access** | Low / High | RBAC, org-scoped APIs, audit logging, security runbook; object-storage access controls | Low |
| R8 | **Cross-border transfer** when validating on non-IT data | Low / Medium | Prefer open/aggregated data; for any restricted transfer use Chapter V safeguards; document per dataset | Low |

---

## 4. Data subject rights

Because crash data is authority-held and de-identified for modelling, most
requests are handled by the **controller (road authority)** against the
source register, not against derived artifacts. The platform supports rights
by design:

- **Transparency (Arts. 13–14):** controller publishes a privacy notice; the
  source register and this pack document the processing.
- **Access / erasure / rectification (Arts. 15–17):** acted on at the
  canonical-record layer by the controller; derived aggregates are
  regenerated via the reproducible pipeline + run registry. Public aggregates
  behind the ≥5 floor generally fall outside individual erasure because they
  are not personal data.
- **Objection (Art. 21):** applies to the controller's public-interest basis;
  handled at source.
- **No automated decision with legal effect on individuals (Art. 22):** the
  platform scores *places*, not persons — confirmed and enforced by design.

---

## 5. Consultation and sign-off

- **DPO review:** required per deployment before go-live.
- **Prior consultation with supervisory authority (Art. 36):** required only
  if residual high risk remains after mitigation — currently flagged for the
  roadmap sensing inputs (R5) once those leave the design stage.
- **Sign-off table (per deployment):**

| Role | Name | Date | Outcome |
| --- | --- | --- | --- |
| Controller representative | _to complete_ | | |
| Data Protection Officer | _to complete_ | | |
| Technical lead | _to complete_ | | |

---

## 6. Review triggers

Re-run this DPIA when any of the following occur:
- a new source is onboarded (esp. any non-aggregated or sensing feed);
- real-time / trajectory / V2I inputs move from design to pilot (Issues 21–22);
- deployment in a new jurisdiction or cross-border data use;
- a change to aggregation floors, retention, or the public publication surface;
- a personal-data breach affecting this system.
