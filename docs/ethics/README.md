# Ethics, Data Protection & GDPR Pack

This directory is the data-protection and research-ethics dossier for the
Road Accidents Risk Modeling platform. It exists to make the platform
defensible under the EU General Data Protection Regulation (GDPR,
Regulation (EU) 2016/679) and to support the kind of ethics self-assessment
that research funders and public-sector deployers typically require.

## Contents

| Document | Purpose |
| --- | --- |
| [dpia.md](dpia.md) | Data Protection Impact Assessment (GDPR Art. 35) covering crash microdata, geolocation, and the planned trajectory/sensing inputs. |
| [records-of-processing.md](records-of-processing.md) | Record of Processing Activities (GDPR Art. 30) and the per-source legal-basis register. |
| [privacy-by-design.md](privacy-by-design.md) | Data-protection-by-design and by-default note (GDPR Art. 25), tied to the existing field-classification matrix and aggregation floors. |
| [anonymisation-policy.md](anonymisation-policy.md) | Anonymisation/pseudonymisation policy and re-identification-risk controls, with focus on sparse crash cells and future VRU/trajectory data. |

## Relationship to existing governance

This pack is the **legal/ethics layer** on top of the already-implemented
**technical governance layer**:

- [docs/data-governance.md](../data-governance.md) — per-field
  classification (`public` / `internal` / `restricted` / `sensitive`),
  retention rules, public-map aggregation floors, and the
  `source_licensing_register`.
- [docs/governance-interoperability.md](../governance-interoperability.md) —
  source-family governance, DATEX II alignment, mobility-data-space patterns.

The technical layer answers *"which field can which role see, and at what
aggregation?"*. This pack answers *"on what legal basis do we process it,
what is the risk to data subjects, and how is that risk mitigated?"*.

## Scope and status

- **Controller / processor roles** are defined per deployment: in a
  municipal deployment the road authority is normally the **controller**
  and the platform operator is a **processor** acting under a written
  agreement (GDPR Art. 28). The DPIA assumes this default and flags where
  it must be confirmed per pilot.
- This dossier is a **living document**. Onboarding any new source,
  enabling real-time/sensing inputs, or deploying in
  a new jurisdiction requires a review pass and, where triggered, a DPIA
  update before go-live.
- Nothing here is legal advice. Before a production deployment each
  controller must have these artifacts reviewed by its Data Protection
  Officer (DPO) and, where required, consult its supervisory authority
  (GDPR Art. 36).
