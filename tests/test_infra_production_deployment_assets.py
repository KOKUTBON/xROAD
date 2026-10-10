"""Structural tests for the production deployment package added under #142."""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
K8S_DIR = REPO_ROOT / "infra" / "k8s"
TERRAFORM_DIR = REPO_ROOT / "infra" / "terraform" / "self-hosted-k8s"


class ProductionDeploymentPackageTests(unittest.TestCase):
    def test_kubernetes_package_contains_release_blocker_assets(self) -> None:
        for relative in (
            "configmap.template.yaml",
            "secrets.external-secret.example.yaml",
            "secrets.sealed-secret.example.yaml",
            "api.deployment.yaml",
            "worker.deployment.yaml",
            "scheduler.deployment.yaml",
            "web.deployment.yaml",
            "ingress.yaml",
            "hpa.yaml",
            "pdb.yaml",
            "environments/staging.env.example",
            "environments/production.env.example",
        ):
            self.assertTrue((K8S_DIR / relative).is_file(), f"missing infra/k8s/{relative}")

    def test_web_deployment_is_hardened_and_service_backed(self) -> None:
        manifest = (K8S_DIR / "web.deployment.yaml").read_text(encoding="utf-8")
        for expected in (
            "kind: Deployment",
            "name: road-risk-web",
            "image: road-risk/web:dev",
            "readOnlyRootFilesystem: true",
            "allowPrivilegeEscalation: false",
            "imagePullSecrets:",
            "kind: Service",
            "targetPort: 3000",
            "readinessProbe:",
        ):
            self.assertIn(expected, manifest)

    def test_ingress_scaling_and_disruption_budgets_cover_core_services(self) -> None:
        ingress = (K8S_DIR / "ingress.yaml").read_text(encoding="utf-8")
        hpa = (K8S_DIR / "hpa.yaml").read_text(encoding="utf-8")
        pdb = (K8S_DIR / "pdb.yaml").read_text(encoding="utf-8")

        for expected in (
            "kind: Ingress",
            "cert-manager.io/cluster-issuer",
            "road-risk-platform-tls",
            "road-risk-api",
            "road-risk-web",
        ):
            self.assertIn(expected, ingress)

        for expected in ("road-risk-api", "road-risk-worker", "road-risk-web"):
            self.assertIn("kind: HorizontalPodAutoscaler", hpa)
            self.assertIn(expected, hpa)
            self.assertIn("kind: PodDisruptionBudget", pdb)
            self.assertIn(expected, pdb)

        self.assertIn("road-risk-scheduler", pdb)
        self.assertNotIn("name: road-risk-scheduler\n  namespace: road-risk\n", hpa)

    def test_config_and_secret_templates_document_runtime_contract(self) -> None:
        config = (K8S_DIR / "configmap.template.yaml").read_text(encoding="utf-8")
        external_secret = (K8S_DIR / "secrets.external-secret.example.yaml").read_text(encoding="utf-8")
        sealed_secret = (K8S_DIR / "secrets.sealed-secret.example.yaml").read_text(encoding="utf-8")

        for expected in (
            "ROAD_RISK_API_AUTH_ENABLED",
            "ROAD_RISK_API_AUTH_JWKS_URL",
            "ROAD_RISK_STORAGE_ENDPOINT_URL",
            "ROAD_RISK_WEB_API_BASE_URL",
            "ROAD_RISK_WEB_OIDC_ISSUER",
            "ROAD_RISK_BUILD_SHA",
        ):
            self.assertIn(expected, config)

        for expected in (
            "kind: ExternalSecret",
            "ROAD_RISK_DATABASE_URL",
            "ROAD_RISK_REDIS_URL",
            "ROAD_RISK_STORAGE_SECRET_ACCESS_KEY",
            "ROAD_RISK_WEB_OIDC_CLIENT_SECRET",
        ):
            self.assertIn(expected, external_secret)

        self.assertIn("kind: SealedSecret", sealed_secret)
        self.assertIn("AgREPLACE_WITH_KUBESEAL_OUTPUT", sealed_secret)

    def test_environment_samples_separate_staging_and_production(self) -> None:
        staging = (K8S_DIR / "environments" / "staging.env.example").read_text(encoding="utf-8")
        production = (K8S_DIR / "environments" / "production.env.example").read_text(encoding="utf-8")

        self.assertIn("ROAD_RISK_ENVIRONMENT=staging", staging)
        self.assertIn("ROAD_RISK_NAMESPACE=road-risk-staging", staging)
        self.assertIn("SMOKE_API_BASE_URL=https://api.staging", staging)
        self.assertIn("ROAD_RISK_ENVIRONMENT=production", production)
        self.assertIn("ROAD_RISK_NAMESPACE=road-risk-production", production)
        self.assertIn("ROAD_RISK_IMAGE_TAG=1.0.0", production)

    def test_terraform_self_hosted_k8s_scaffold_bootstraps_platform_dependencies(self) -> None:
        for relative in (
            "README.md",
            "versions.tf",
            "variables.tf",
            "main.tf",
            "outputs.tf",
            "terraform.tfvars.example",
        ):
            self.assertTrue((TERRAFORM_DIR / relative).is_file(), f"missing terraform asset {relative}")

        main = (TERRAFORM_DIR / "main.tf").read_text(encoding="utf-8")
        variables = (TERRAFORM_DIR / "variables.tf").read_text(encoding="utf-8")
        readme = (TERRAFORM_DIR / "README.md").read_text(encoding="utf-8")

        for expected in (
            "resource \"kubernetes_namespace_v1\" \"road_risk\"",
            "resource \"helm_release\" \"ingress_nginx\"",
            "resource \"helm_release\" \"cert_manager\"",
            "resource \"helm_release\" \"external_secrets\"",
        ):
            self.assertIn(expected, main)

        for expected in ("variable \"environment\"", "variable \"namespace\"", "variable \"kube_context\""):
            self.assertIn(expected, variables)

        self.assertIn("smoke_staging.py", readme)
        self.assertIn("External Secrets Operator", readme)

    def test_docs_reference_rollout_tls_and_remote_smoke(self) -> None:
        k8s_readme = (K8S_DIR / "README.md").read_text(encoding="utf-8")
        runbook = (REPO_ROOT / "docs" / "production-runbook.md").read_text(encoding="utf-8")
        staging = (REPO_ROOT / "docs" / "staging-deployment-smoke.md").read_text(encoding="utf-8")

        for expected in (
            "cert-manager",
            "kubectl -n road-risk set image",
            "rollout status deployment/road-risk-web",
            "infra/staging/smoke_staging.py",
            "terraform/self-hosted-k8s",
        ):
            self.assertIn(expected, k8s_readme)

        self.assertIn("web.deployment.yaml", runbook)
        self.assertIn("remote staging smoke", runbook.lower())
        self.assertIn("Remote Kubernetes Staging", staging)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
