# Record of Processing Activities (RoPA) & Legal-Basis Register

**Regulation:** GDPR (EU) 2016/679, Article 30.
**Status:** Template / first record — 2026-06-17. Each controller completes
the identity fields and confirms the legal basis per deployment.

This record complements the machine-readable `source_licensing_register.csv`
in [data-governance.md](../data-governance.md): that register answers
*licensing/redistribution*; this record answers *GDPR legal basis and
processing accountability*.

---

## 1. Controller / processor

| Field | Value |
| --- | --- |
| Controller | Deploying road/municipal authority (_to complete per deployment_) |
| Processor | Platform operator, under a written Art. 28 agreement |
| DPO contact | _to complete_ |
| Joint-controller arrangement? | Only if two authorities co-decide purposes — _to complete_ |

---

## 2. Processing activities

| ID | Activity | Purpose | Data categories | Subjects | Legal basis (Art. 6) |
| --- | --- | --- | --- | --- | --- |
| P1 | Ingest & canonicalise crash records | Build the modelling base | Crash attributes, location, casualty counts | Crash-involved persons | 6(1)(e) public interest (road safety), authority-held |
| P2 | Geospatial enrichment & segmentation | Attach risk to road objects | Location, road geometry (OSM) | — (geometry, no persons) | 6(1)(e); OSM is open data |
| P3 | Risk modelling (frequency, severity) | Score places | De-identified aggregates | — | 6(1)(e) |
| P4 | Publish risk surfaces & briefs | Inform interventions | Banded/aggregated scores (≥5 floor) | — (not personal once aggregated) | 6(1)(e) |
| P5 | Exposure connectors (motor-flow, speed, VRU) | Replace proxies | Traffic/speed observations | Potentially road users | 6(1)(e) and/or 6(1)(f); per provider contract — **pending** |
| P6 | Trajectory / near-miss / V2I (roadmap) | Interaction-level safety | Movement tracks, sensor feeds | Identifiable road users incl. VRUs | **Not yet active — DPIA update required (Issues 21–22)** |
| P7 | Platform accounts & audit logging | Security, accountability | User identity, access logs | Authority staff | 6(1)(c) legal obligation / 6(1)(f) legitimate interest |

No Art. 9 special-category processing is performed at the individual level;
casualty severity is processed only as aggregates (see DPIA §1.2).

---

## 3. Per-source legal-basis register

Aligns with the four "approved/approved-per-request" + three "pending"
sources in `source_licensing_register.csv`.

| Source | Status | License / rights | GDPR legal basis | Personal-data risk | Notes |
| --- | --- | --- | --- | --- | --- |
| Bari open-data crashes (2022–2025) | approved | Open data, attribution | 6(1)(e) | Low–medium (location/time) | Primary operational crash feed |
| Puglia cleaned legacy CSV (2016–2021) | approved | Legacy delivery | 6(1)(e) | Low–medium | 48,150 rows; historical baseline |
| OSM road network | approved | ODbL (share-alike) | n/a (no personal data) | None | Attribution + share-alike obligations |
| Bari signal-phase provider deliveries | approved per request | Provider terms | 6(1)(e)/contract | Low (infrastructure) | Controller data, restricted |
| Motor-flow connector | pending provider terms | TBD | 6(1)(e)/6(1)(f) TBD | Medium | Gating item before go-live |
| Observed-speed connector | pending provider terms | TBD | 6(1)(e)/6(1)(f) TBD | Medium | Gating item before go-live |
| DATEX II live event feed | pending operator terms | TBD | 6(1)(e) TBD | Low–medium | Gating item before go-live |

---

## 4. Retention & transfers

- **Retention:** per the `retention_rules` matrix in
  [data-governance.md](../data-governance.md) — canonical crash rows kept
  indefinitely under governance review; provider raw exports purged after
  normalisation; audit logs capped at 24 months.
- **Recipients:** authority analysts/operators (RBAC, org-scoped); the public
  only via aggregated surfaces.
- **International transfers:** none required for the current Italy-only
  pilots. Any cross-border validation
  must prefer open/aggregated data; restricted transfers require Chapter V
  safeguards documented per dataset.

---

## 5. Security measures (Art. 32)

RBAC + organization-scoped APIs, audit logging, object-storage access
controls, encrypted secrets, and the procedures in the production security /
incident-response runbooks. The publication surface **fails closed**: any
field without a classification entry raises `KeyError` rather than leaking.
