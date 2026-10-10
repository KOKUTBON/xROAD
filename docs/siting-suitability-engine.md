# Siting Suitability Engine

The suitability engine ranks candidate parcels for parks, schools, and community institutions.
Its control order is deliberate:

1. Mandatory siting-standard rules filter candidates, including missing mandatory data.
2. A transparent weighted MCA combines population served, provision gap,
   access-route safety, accessibility, and demographic equity.
3. A deterministic nearest-neighbour demand/benefit model trained on existing
   facilities and usage proxies contributes 20% of the final score. It cannot
   override compliance.

Each result includes criterion scores, the model refinement, served population,
access-route risk, full rule results and citations, and potential companion
Recommended countermeasures for excluded road-safety cases. Candidate geometry may
come from grid cells or cadastral/land-use parcels; the committed Bari demo uses
a deterministic built-environment demo grid because parcel licensing and
current usage observations are not yet available.

`weight_sensitivity_analysis()` reranks candidates after increasing and
decreasing each criterion weight by 20%. The output reports top-k overlap and
top-site changes. This makes policy-weight fragility visible rather than hiding
it in one composite score.

Reproduce the Bari outputs:

```bash
PYTHONPATH=src python3 tools/siting_suitability_demo.py
```

The generated `data/planning/siting/bari/` directory contains top-10 park and
top-5 primary-school GeoJSON, JSON reports, and concise Markdown summaries.
These are screening outputs, not land availability findings or planning
approvals.
