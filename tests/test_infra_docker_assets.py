"""Tests for the Docker Compose and CI/CD runtime configuration.

These tests do not run docker locally. They only assert that the
expected files exist, that the compose file parses as a mapping, that
all referenced Dockerfiles exist, that the service contract matches the
documented production-platform roadmap, and that the CI workflow files
are wired correctly.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKER_DIR = REPO_ROOT / "infra" / "docker"
STAGING_DIR = REPO_ROOT / "infra" / "staging"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"


def _load_yaml(path: Path) -> dict:
    """Parse a YAML file using PyYAML if available, otherwise a minimal fallback.

    The repo's `dev` extras already include modern Python tooling, but PyYAML
    is not in the listed dependencies. We try to import it and fall back to a
    very small structural parser so this test stays self-contained.
    """
    try:
        import yaml  # type: ignore
    except Exception:  # pragma: no cover - fallback path
        return _light_yaml_parse(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _light_yaml_parse(path: Path) -> dict:
    """Tiny structural YAML parser for the assertions we need.

    It does not implement YAML; it only extracts top-level keys and the
    immediate child keys under `services:` and `volumes:`. That is enough
    to validate the compose file shape without adding a hard dependency.
    """
    text = path.read_text(encoding="utf-8")
    sections: dict[str, dict[str, dict]] = {"services": {}, "volumes": {}}
    current_top: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*$", raw_line):
            current_top = raw_line.split(":", 1)[0].strip()
            sections.setdefault(current_top, {})
            continue
        if current_top in ("services", "volumes") and raw_line.startswith("  ") and not raw_line.startswith("    "):
            match = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):", raw_line)
            if match:
                sections[current_top][match.group(1)] = {}
    return sections


class InfraDockerAssetsTests(unittest.TestCase):
    def test_compose_file_exists_and_lists_core_services(self) -> None:
        compose_path = DOCKER_DIR / "docker-compose.yml"
        self.assertTrue(compose_path.is_file(), f"missing {compose_path}")

        compose = _load_yaml(compose_path)
        services = compose.get("services", {})
        self.assertIn("api", services, "API service must be defined")
        self.assertIn("postgres", services, "Postgres service must be defined")
        self.assertIn("redis", services, "Redis service must be defined")
        self.assertIn("minio", services, "MinIO service must be defined")
        self.assertIn("worker", services, "Worker service must be defined")
        self.assertIn("web", services, "Web service must be defined")

        volumes = compose.get("volumes", {})
        for expected in ("postgres_data", "redis_data", "minio_data"):
            self.assertIn(expected, volumes, f"compose must declare volume `{expected}`")

    def test_compose_exposes_staging_runtime_contract(self) -> None:
        compose_path = DOCKER_DIR / "docker-compose.yml"
        compose_body = compose_path.read_text(encoding="utf-8")

        self.assertIn("../../data:/app/data:ro", compose_body)
        self.assertIn("ROAD_RISK_API_ENV", compose_body)
        self.assertIn("ROAD_RISK_STORAGE_ENDPOINT_URL", compose_body)
        self.assertIn('profiles: ["web", "all"]', compose_body)

    def test_referenced_dockerfiles_exist(self) -> None:
        for name in ("Dockerfile.api", "Dockerfile.worker", "Dockerfile.web"):
            path = DOCKER_DIR / name
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_dockerignore_excludes_data_directory(self) -> None:
        root_dockerignore = REPO_ROOT / ".dockerignore"
        infra_dockerignore = DOCKER_DIR / ".dockerignore"
        self.assertTrue(root_dockerignore.is_file(), f"missing {root_dockerignore}")
        self.assertTrue(infra_dockerignore.is_file(), f"missing {infra_dockerignore}")

        root_body = root_dockerignore.read_text(encoding="utf-8")
        infra_body = infra_dockerignore.read_text(encoding="utf-8")
        # Compose builds from the repository root, so the root ignore file
        # is the one that actively keeps large analytics outputs out of the
        # Docker build context.
        self.assertIn("data/", root_body)
        self.assertIn(".git/", root_body)
        self.assertIn("docs/", root_body)
        self.assertIn("tests/", root_body)
        self.assertIn("data/models/", infra_body)

    def test_env_example_documents_required_variables(self) -> None:
        env_example = DOCKER_DIR / ".env.example"
        self.assertTrue(env_example.is_file(), f"missing {env_example}")
        body = env_example.read_text(encoding="utf-8")
        for key in (
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "MINIO_ROOT_USER",
            "MINIO_ROOT_PASSWORD",
            "ROAD_RISK_STORAGE_BUCKET",
            "API_HOST_PORT",
        ):
            self.assertIn(key, body, f"`.env.example` must document {key}")

    def test_api_dockerfile_runs_uvicorn_with_apps_api_main(self) -> None:
        dockerfile = (DOCKER_DIR / "Dockerfile.api").read_text(encoding="utf-8")
        # The API container must boot the existing FastAPI app from apps/api.
        self.assertIn("apps.api.main:app", dockerfile)
        # Non-root user keeps the production image away from root execution.
        self.assertIn("useradd", dockerfile)
        # Container must expose the documented API port.
        self.assertIn("EXPOSE 8000", dockerfile)

    def test_worker_dockerfile_runs_real_celery_runtime(self) -> None:
        dockerfile = (DOCKER_DIR / "Dockerfile.worker").read_text(encoding="utf-8")
        self.assertIn("services.workers.celery_app", dockerfile)
        self.assertIn("celery", dockerfile.lower())
        self.assertIn(".[api,worker,analytics]", dockerfile)

    def test_web_dockerfile_builds_nextjs_shell(self) -> None:
        dockerfile = (DOCKER_DIR / "Dockerfile.web").read_text(encoding="utf-8")
        self.assertIn("apps/web/package.json", dockerfile)
        self.assertIn("npm run build", dockerfile)
        self.assertIn("EXPOSE 3000", dockerfile)

    def test_docker_build_workflow_targets_all_three_images(self) -> None:
        workflow = WORKFLOW_DIR / "docker-build.yml"
        self.assertTrue(workflow.is_file(), f"missing {workflow}")
        body = workflow.read_text(encoding="utf-8")
        for image in ("api", "worker", "web"):
            self.assertIn(f"image: {image}", body, f"docker-build workflow must build the {image} image")
        # The workflow should run on PR and main pushes; otherwise CI does
        # not actually guard regressions.
        self.assertIn("pull_request:", body)
        self.assertIn("push:", body)

    def test_compose_validate_workflow_uses_env_example(self) -> None:
        workflow = WORKFLOW_DIR / "compose-validate.yml"
        self.assertTrue(workflow.is_file(), f"missing {workflow}")
        body = workflow.read_text(encoding="utf-8")
        self.assertIn("infra/docker/.env.example", body)
        self.assertIn("infra/staging/.env.example", body)
        self.assertIn("docker compose", body)
        self.assertIn("--profile scheduler", body)
        self.assertIn("config --quiet", body)

    def test_web_ci_workflow_checks_type_tests_and_build(self) -> None:
        workflow = WORKFLOW_DIR / "web-ci.yml"
        self.assertTrue(workflow.is_file(), f"missing {workflow}")
        body = workflow.read_text(encoding="utf-8")
        self.assertIn("apps/web", body)
        self.assertIn("npm ci", body)
        self.assertIn("npm run typecheck", body)
        self.assertIn("npm run test", body)
        self.assertIn("npm run build", body)

    def test_staging_smoke_assets_exist_and_cover_release_checks(self) -> None:
        for relative in (
            ".env.example",
            "docker-compose.staging.yml",
            "seed_staging.sql",
            "smoke_staging.py",
            "run_staging_smoke.sh",
        ):
            self.assertTrue((STAGING_DIR / relative).is_file(), f"missing staging asset {relative}")

        smoke = (STAGING_DIR / "smoke_staging.py").read_text(encoding="utf-8")
        for endpoint in (
            "/healthz",
            "/v1/observability/info",
            "/v1/observability/readiness",
            "/openapi.json",
            "/v1/public/cities",
            "/v1/ingestion-jobs/upload-center",
            "/v1/ingestion-jobs/uploads",
            "/v1/jobs/published-refresh",
            "/v1/reports/generate",
        ):
            self.assertIn(endpoint, smoke)

        runner = (STAGING_DIR / "run_staging_smoke.sh").read_text(encoding="utf-8")
        self.assertIn("alembic -c alembic.ini upgrade head", runner)
        self.assertIn("seed_staging.sql", runner)
        self.assertIn("smoke_staging.py", runner)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
