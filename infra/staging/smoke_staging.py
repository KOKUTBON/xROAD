#!/usr/bin/env python3
"""End-to-end staging smoke checks for the Road Risk platform.

The script intentionally uses only the Python standard library so it can
run from a clean checkout, CI runner, or staging jump host without extra
dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeResult:
    name: str
    status: str
    detail: str


class SmokeFailure(RuntimeError):
    """Raised when a required staging smoke check fails."""


def _json_request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, method=method, data=data, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller controls staging URL.
            body = response.read()
            if not body:
                return {}
            return json.loads(body.decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except (ConnectionError, OSError, URLError, TimeoutError) as exc:
        raise SmokeFailure(f"{method} {url} failed: {exc}") from exc


def _text_request(url: str, *, timeout: float = 15.0) -> str:
    request = Request(url, method="GET", headers={"Accept": "text/html,application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller controls staging URL.
            return response.read().decode("utf-8", errors="replace")
    except (ConnectionError, OSError, HTTPError, URLError, TimeoutError) as exc:
        raise SmokeFailure(f"GET {url} failed: {exc}") from exc


def _bytes_request(
    method: str,
    url: str,
    payload: bytes,
    *,
    content_type: str,
    timeout: float = 15.0,
) -> None:
    request = Request(
        url,
        method=method,
        data=payload,
        headers={"Content-Type": content_type},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller controls staging URL.
            response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except (ConnectionError, OSError, URLError, TimeoutError) as exc:
        raise SmokeFailure(f"{method} {url} failed: {exc}") from exc


def _join(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _public_object_storage_url(upload_url: str, public_base_url: str | None) -> str:
    if not public_base_url:
        return upload_url
    parsed = urlparse(upload_url)
    if parsed.hostname not in {"minio", "road-risk-minio"}:
        return upload_url
    public = urlparse(public_base_url)
    return urlunparse(
        (
            public.scheme,
            public.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _wait_for_json(
    url: str,
    *,
    token: str | None,
    deadline_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + deadline_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _json_request("GET", url, token=token)
        except SmokeFailure as exc:
            last_error = exc
            time.sleep(interval_seconds)
    raise SmokeFailure(f"Timed out waiting for {url}: {last_error}") from last_error


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _record(results: list[SmokeResult], name: str, detail: str) -> None:
    results.append(SmokeResult(name=name, status="pass", detail=detail))
    print(f"[pass] {name}: {detail}")


def run_smoke(args: argparse.Namespace) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    token = args.bearer_token
    api = args.api_base_url
    web = args.web_base_url

    health = _wait_for_json(
        _join(api, "/healthz"),
        token=token,
        deadline_seconds=args.wait_seconds,
        interval_seconds=2.0,
    )
    _expect(health.get("status") == "ok", f"Unexpected health payload: {health}")
    _record(results, "api_liveness", "GET /healthz returned ok")

    info = _json_request("GET", _join(api, "/v1/observability/info"), token=token)
    _expect(info.get("contract_version") == "observability_info_v1", f"Unexpected info payload: {info}")
    _record(results, "observability_info", f"environment={info.get('app_environment')}")

    readiness = _json_request("GET", _join(api, "/v1/observability/readiness"), token=token)
    _expect(readiness.get("status") in {"ready", "degraded"}, f"Unexpected readiness payload: {readiness}")
    if args.require_ready:
        _expect(readiness.get("status") == "ready", f"Readiness is not ready: {readiness}")
    _record(results, "observability_readiness", f"status={readiness.get('status')}")

    openapi = _json_request("GET", _join(api, "/openapi.json"), token=token)
    _expect("/healthz" in openapi.get("paths", {}), "OpenAPI schema does not include /healthz")
    _record(results, "openapi_schema", f"paths={len(openapi.get('paths', {}))}")

    cities = _json_request("GET", _join(api, "/v1/public/cities"), token=token)
    city_keys = {str(row.get("city_key")) for row in cities.get("cities", [])}
    _expect(args.city_key in city_keys, f"{args.city_key} is missing from public city catalog: {city_keys}")
    _record(results, "public_city_catalog", f"cities={len(city_keys)}")

    risk_query = urlencode({"limit": 25})
    risk_map = _json_request(
        "GET",
        _join(api, f"/v1/public/cities/{args.city_key}/risk-map?{risk_query}"),
        token=token,
    )
    features = risk_map.get("map_resource", {}).get("data", {}).get("features", [])
    _expect(len(features) > 0, "Public risk map returned no features")
    _record(results, "public_risk_map", f"features={len(features)}")

    analyst_query = urlencode({"limit": 10, "junction_limit": 5, "crossing_limit": 5})
    analyst_map = _json_request(
        "GET",
        _join(api, f"/v1/analyst/cities/{args.city_key}/risk-map?{analyst_query}"),
        token=token,
    )
    segment_features = analyst_map.get("segment_layer", {}).get("data", {}).get("features", [])
    _expect(len(segment_features) > 0, "Analyst risk map returned no segment features")
    _record(results, "analyst_risk_map", f"segments={len(segment_features)}")

    home = _text_request(_join(web, "/"))
    _expect("Road Risk Platform" in home, "Web home route did not render the app shell")
    _record(results, "web_public_route", "GET / rendered")

    workspace = _text_request(_join(web, "/workspace"))
    _expect("Road Risk Platform" in workspace, "Workspace route did not render the app shell")
    _record(results, "web_workspace_route", "GET /workspace rendered")

    if not args.skip_mutating:
        upload_center_query = urlencode(
            {"organization_id": args.organization_id, "municipality_id": args.municipality_id}
        )
        upload_center = _json_request(
            "GET",
            _join(api, f"/v1/ingestion-jobs/upload-center?{upload_center_query}"),
            token=token,
        )
        upload_sources = [
            source
            for source in upload_center.get("sources", [])
            if source.get("upload_enabled") and source.get("source_id")
        ]
        _expect(upload_sources, f"Upload center returned no upload-enabled sources: {upload_center}")
        source_id = upload_sources[0]["source_id"]
        _record(results, "upload_center_sources", f"sources={len(upload_sources)}")

        upload_payload = {
            "organization_id": args.organization_id,
            "municipality_id": args.municipality_id,
            "source_id": source_id,
            "filename": "staging_crashes.csv",
            "content_type": "text/csv",
            "parameters": {
                "field_mapping": {
                    "crash_id": "crash_id",
                    "latitude": "latitude",
                    "longitude": "longitude",
                },
                "staging_smoke": True,
            },
        }
        upload_registration = _json_request(
            "POST",
            _join(api, "/v1/ingestion-jobs/uploads"),
            token=token,
            payload=upload_payload,
        )
        upload_url = upload_registration.get("upload_url")
        job_id = upload_registration.get("job_id")
        _expect(bool(upload_url) and bool(job_id), f"Upload registration failed: {upload_registration}")
        _bytes_request(
            "PUT",
            _public_object_storage_url(str(upload_url), args.minio_public_base_url),
            b"crash_id,latitude,longitude\nsmoke-1,41.125,16.866\n",
            content_type="text/csv",
        )
        validation = _json_request(
            "POST",
            _join(api, f"/v1/ingestion-jobs/{job_id}/validate"),
            token=token,
            payload={"organization_id": args.organization_id},
        )
        validation_status = validation.get("job", {}).get("status")
        _expect(validation_status == "validated_ready", f"Upload validation failed: {validation}")
        _record(results, "upload_validation_flow", "job_id_present")

        approval = _json_request(
            "POST",
            _join(api, f"/v1/ingestion-jobs/{job_id}/approve"),
            token=token,
            payload={"organization_id": args.organization_id, "decision_note": "staging smoke"},
        )
        _expect(approval.get("job", {}).get("status") == "queued", f"Upload approval failed: {approval}")
        _record(results, "upload_approval_flow", "status=queued")

        execution = _json_request(
            "POST",
            _join(api, f"/v1/ingestion-jobs/{job_id}/run"),
            token=token,
            payload={"organization_id": args.organization_id, "dispatch_mode": args.dispatch_mode},
        )
        execution_status = execution.get("job", {}).get("status")
        _expect(
            execution_status in {"completed", "queued", "running"},
            f"Upload execution failed: {execution}",
        )
        _record(results, "upload_execution_flow", f"status={execution_status}")

        job_payload = {
            "organization_id": args.organization_id,
            "data_root": "/app/data",
            "registry_output_dir": "/tmp/road-risk-staging/registry",
            "published_index_output_dir": "/tmp/road-risk-staging/published_index",
            "dashboard_output_dir": "/tmp/road-risk-staging/dashboard",
            "output_dir": "/tmp/road-risk-staging/reporting/published_refresh/latest",
            "dispatch_mode": args.dispatch_mode,
        }
        job = _json_request("POST", _join(api, "/v1/jobs/published-refresh"), token=token, payload=job_payload)
        job_status = job.get("job", {}).get("status")
        _expect(job_status in {"completed", "queued", "running"}, f"Unexpected job status: {job}")
        _record(results, "background_job_trigger", f"status={job_status}")

        job_id = job.get("job", {}).get("job_id")
        _expect(bool(job_id), f"Published refresh response missing job id: {job}")
        detail_url = _join(
            api,
            f"/v1/jobs/{job_id}?{urlencode({'organization_id': args.organization_id})}",
        )
        detail = _json_request("GET", detail_url, token=token)
        _expect(detail.get("job", {}).get("status") in {"completed", "queued", "running"}, f"Job detail failed: {detail}")
        _record(results, "background_job_detail", "job_id_present")

        report_payload = {
            "organization_id": args.organization_id,
            "city_key": args.city_key,
            "report_type": "executive_overview",
            "output_format": "md",
            "visibility_tier": "internal",
            "dispatch_mode": args.dispatch_mode,
        }
        report = _json_request("POST", _join(api, "/v1/reports/generate"), token=token, payload=report_payload)
        report_status = report.get("report", {}).get("status")
        _expect(report_status in {"generated", "queued", "running"}, f"Unexpected report status: {report}")
        report_id = report.get("report", {}).get("report_id")
        _expect(bool(report_id), f"Report response missing report id: {report}")
        _record(results, "report_generation", f"status={report_status}")

        report_detail = _json_request(
            "GET",
            _join(api, f"/v1/reports/{report_id}?{urlencode({'organization_id': args.organization_id})}"),
            token=token,
        )
        _expect(report_detail.get("report", {}).get("report_id") == report_id, f"Report detail failed: {report_detail}")
        _record(results, "report_detail", "report_id_present")

        if report_status == "generated":
            download = _json_request(
                "GET",
                _join(api, f"/v1/reports/{report_id}/download?{urlencode({'organization_id': args.organization_id})}"),
                token=token,
            )
            _expect(download.get("access", {}).get("access_mode"), f"Report download access missing: {download}")
            _record(results, "report_download", f"mode={download.get('access', {}).get('access_mode')}")

    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run staging smoke checks against Road Risk services.")
    parser.add_argument("--api-base-url", default="http://localhost:18000")
    parser.add_argument("--web-base-url", default="http://localhost:13000")
    parser.add_argument("--organization-id", default="00000000-0000-0000-0000-000000000118")
    parser.add_argument("--municipality-id", default="00000000-0000-0000-0000-000000000119")
    parser.add_argument("--city-key", default="bari")
    parser.add_argument("--minio-public-base-url", default="http://localhost:19000")
    parser.add_argument("--bearer-token", default=None)
    parser.add_argument("--dispatch-mode", choices=["inline", "queued"], default="inline")
    parser.add_argument("--skip-mutating", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=90.0)
    parser.add_argument("--json-output", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        results = run_smoke(args)
    except SmokeFailure as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as handle:
            json.dump([result.__dict__ for result in results], handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
