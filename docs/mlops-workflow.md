# MLOps Registry and Training Workflow

The MLOps workflow uses a lightweight file-based registry aligned with the repository's
lineage manifests. The
[ML training and serving ADR](adr-ml-training-serving-architecture.md) selects
this registry over an MLflow service for v1 and records the evidence-based
triggers for reconsidering that choice.

Every registered run records:

- deterministic seed, parameters, metrics, git SHA, Python/platform and key
  package versions;
- content hashes for every training matrix or knowledge artifact;
- a content-addressed immutable model copy;
- a complete model card covering intended use, training data, metrics,
  limitations, and ethics;
- an append-only stage-change audit trail.

Models register as `candidate`. Explicit stage flips move a version to
`staging` or `production`; only one version can occupy a stage. Serving calls
`ModelRegistry.resolve(model_name, stage="production")`, verifies the artifact
checksum, and never resolves a configured filesystem path. Rollback is the
same audited stage flip to a previous version.

Registrations that omit or empty any required model-card field fail. Start
from [`model-card-template.json`](model-card-template.json) and replace every
instructional value with model-specific evidence.

The reference pipeline migrates the Bari frequency baseline:

```bash
make mlops-frequency-reference
make eval
make mlops-stage-reference
make mlops-promote-reference
```

The first target trains from the versioned aggregate matrix and registers the
artifact as a candidate. `make eval` applies the
[model evaluation gates](model-evaluation-gates.md). The next two targets
perform audited staging and production transitions. Training therefore cannot
silently publish itself or bypass a failing quality gate.
Pass `--version` to `tools/set_model_stage.py` to promote or roll back to a
specific version; omitting it selects the latest registered version. Notebooks
may explore data but must call shared training functions; they are not
accepted as production pipelines.

For object-storage deployments, mirror the content-addressed `artifacts/`
prefix into MinIO and retain the same SHA-256 keys. The registry metadata is
small and can remain in versioned storage or move to a transactional service
without changing the serving contract.
