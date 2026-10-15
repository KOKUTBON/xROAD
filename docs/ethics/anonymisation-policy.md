# Anonymisation & Pseudonymisation Policy

**Regulation:** GDPR (EU) 2016/679, Recital 26, Arts. 4(5), 25, 32; informed
by EDPB/WP29 opinion on anonymisation techniques.
**Status:** 2026-06-17.

This policy defines when data in the platform is treated as **anonymous**
(outside GDPR), **pseudonymous** (still personal data, reduced risk), or
**personal**, and the controls that move data between those states. The
acute concern for crash analytics is **re-identification on sparse cells**:
a rare, severe crash at a precise location and time can single out an
individual even without a name.

## 1. Classification of states

| State | Definition | Example in this platform | GDPR |
| --- | --- | --- | --- |
| Personal | Identifiable directly or indirectly | precise `lat/long` + exact time of a crash; `extra` with identifiers | In scope |
| Pseudonymous | Identifiers replaced by keys; re-linkable with extra info | crash matched to a synthetic `crash_id`; coordinates retained internally | In scope, reduced risk |
| Anonymous | Re-identification not reasonably likely | banded segment scores / tiles behind the ≥5 aggregation floor | Out of scope |

The test of "reasonably likely" considers means available to *any* party
(motivated intruder), cost/time, and auxiliary data (e.g. press reports of a
fatal crash). Aggregation alone is not assumed sufficient until the floor and
generalisation below are met.

## 2. Controls by data type

### Crash records (active)
- Precise `latitude`/`longitude`: **`restricted`** — never published
  row-level; used internally for matching/segmentation only.
- `fatalities` / `injuries`: **`restricted`**, **≥5-row aggregation floor**
  before any public exposure; otherwise published only as relative
  reductions / bands.
- `extra` source blob: **`sensitive`** — never published row-level; screened
  for identifiers during ingestion.
- Public outputs: spatial generalisation to segment/tile + banding/indexing,
  so that no public cell maps to fewer than the floor of underlying events.

### Exposure connectors (pending)
- Traffic/speed observations onboarded only as aggregates where possible;
  raw provider exports purged after normalisation (+30-day quarantine).

### Trajectory / near-miss / V2I sensing (roadmap, gated)
Not active. Before any pilot (Issues 21–22) this policy requires:
- **edge/source-side anonymisation** — no raw identifiable tracks leave the
  sensor boundary;
- **no raw-track retention** in the platform; only de-identified
  movement-zone aggregates;
- **k-anonymity / spatial-temporal generalisation** for any movement output;
- **special care for VRUs**, who are harder to anonymise (unique paths,
  low counts);
- a **DPIA update** and necessity re-test as a go-live gate.

## 3. Re-identification risk management

- **Small-cell suppression:** any public aggregate below the floor is
  suppressed, not rounded-and-shown.
- **No mosaic joins:** the public identifier is the synthetic
  `segment_score_id`; internal `segment_id` and exact geometry are withheld
  so public layers cannot be re-joined to internal lineage.
- **Periodic re-identification review:** when onboarding a new source or
  publishing a new surface, assess whether the combination with existing
  public layers lowers effective cell sizes below the floor.
- **Cross-border:** when validating on a second Member State,
  re-assess re-identification under that country's data landscape.

## 4. Pseudonymisation keys

Where pseudonymisation is used (e.g. synthetic `crash_id`), the mapping back
to source records is held only at the controller/source layer under access
control, kept separate from published artifacts, and covered by the retention
rules. Possession of a published artifact must not enable re-linkage.

## 5. Review

Review this policy on any new source, any new public surface, any change to
the aggregation floor, or before any sensing/trajectory pilot.
