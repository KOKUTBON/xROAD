# Terraform

This directory contains versioned infrastructure-as-code scaffolding for
Road Risk staging and production deployment targets.

## Targets

| Target | Path | Purpose |
| --- | --- | --- |
| EU/self-hosted Kubernetes | [`self-hosted-k8s/`](self-hosted-k8s/) | Prepare the namespace and prerequisite controllers for the default municipal deployment path. |

## Current Scope

The first IaC target intentionally prepares the cluster boundary rather
than provisioning a full data plane in-repo. Municipal deployments often
use existing platform services for PostgreSQL/PostGIS, Redis, object
storage, DNS, and OIDC. The Kubernetes package in
[`../k8s`](../k8s) consumes those endpoints through ConfigMaps and
Secrets.

Use this Terraform layer to install or standardize:

- the Road Risk namespace
- ingress-nginx for HTTP ingress
- cert-manager for TLS certificates
- External Secrets Operator for cloud/Vault-backed secrets

After Terraform completes, apply the manifests and environment-specific
configuration documented in [`../k8s/README.md`](../k8s/README.md).
