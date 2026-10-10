"""Minimal read-only HTTP shim for published serving artifacts."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .published_queries import query_published_resource


PUBLISHED_API_VERSION = "published_resource_api_v1"
DASHBOARD_ASSET_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def _coerce_int(value: str | None, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not parse integer query parameter '{field_name}': {value!r}") from exc


def _coerce_float(value: str | None, *, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not parse numeric query parameter '{field_name}': {value!r}") from exc


def _resolve_path(path_value: str | Path, *, root_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root_dir / path


def _load_published_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        raise RuntimeError(
            f"Published index file does not exist: {index_path}. "
            "Build it first with: road-risk build-published-resource-index "
            "--registry-path data/registry/run_registry.jsonl --output-dir data/published_index"
        )
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("catalog"), list):
        raise RuntimeError("Published index JSON must include a top-level 'catalog' list.")
    return payload


def _load_dashboard_summary(summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists():
        raise RuntimeError(
            f"Dashboard summary file does not exist: {summary_path}. "
            "Build it first with: road-risk build-dashboard-summary "
            "--published-index-path data/published_index/published_resources.json "
            "--output-dir data/dashboard"
        )
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("published_runs"), list):
        raise RuntimeError("Dashboard summary JSON must include a top-level 'published_runs' list.")
    return payload


def resolve_dashboard_asset_response(
    raw_path: str,
    *,
    dashboard_dir: str | Path = "dashboard",
    root_dir: str | Path = ".",
) -> tuple[int, str, bytes] | None:
    root_path = Path(root_dir)
    dashboard_root = _resolve_path(dashboard_dir, root_dir=root_path)
    parsed = urlsplit(raw_path)
    route_path = parsed.path
    if route_path in {"", "/"}:
        route_path = "/dashboard/"
    if not (route_path == "/dashboard" or route_path == "/dashboard/" or route_path.startswith("/dashboard/")):
        return None
    if not dashboard_root.exists():
        return (
            HTTPStatus.NOT_FOUND,
            "text/plain; charset=utf-8",
            f"Dashboard directory does not exist: {dashboard_root}".encode("utf-8"),
        )

    relative_path = route_path[len("/dashboard/") :] if route_path.startswith("/dashboard/") else ""
    if route_path in {"/dashboard", "/dashboard/"} or not relative_path:
        asset_path = dashboard_root / "index.html"
    else:
        asset_path = dashboard_root / relative_path

    try:
        asset_path.resolve().relative_to(dashboard_root.resolve())
    except ValueError:
        return (
            HTTPStatus.NOT_FOUND,
            "text/plain; charset=utf-8",
            b"Dashboard asset path is outside the dashboard directory.",
        )

    if not asset_path.exists() or not asset_path.is_file():
        return (
            HTTPStatus.NOT_FOUND,
            "text/plain; charset=utf-8",
            f"Dashboard asset not found: {asset_path}".encode("utf-8"),
        )

    content_type = DASHBOARD_ASSET_CONTENT_TYPES.get(asset_path.suffix, "application/octet-stream")
    return HTTPStatus.OK, content_type, asset_path.read_bytes()


def _catalog_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return (
        str(record.get("document_mtime_utc") or ""),
        str(record.get("manifest_path") or ""),
    )


def _resolve_latest_from_index(
    payload: dict[str, Any],
    *,
    resource_name: str | None,
    prediction_run_label: str | None,
    occurred_year: int | None,
    tile_size_m: float | None,
    view: str | None,
) -> dict[str, Any]:
    if not resource_name:
        raise RuntimeError("Query parameter 'resource_name' is required.")

    catalog = payload.get("catalog", [])
    matched: list[dict[str, Any]] = []
    for record in catalog:
        if record.get("resource_name") != resource_name:
            continue
        if prediction_run_label is not None and record.get("prediction_run_label") != prediction_run_label:
            continue
        years = {int(year) for year in record.get("occurred_years") or []}
        if occurred_year is not None and occurred_year not in years:
            continue
        record_tile_size = record.get("tile_size_m")
        if tile_size_m is not None:
            if record_tile_size is None or float(record_tile_size) != float(tile_size_m):
                continue
        matched.append(record)

    if not matched:
        raise RuntimeError(
            "No published resource matched the requested filters. "
            f"resource_name={resource_name!r}, prediction_run_label={prediction_run_label!r}, "
            f"occurred_year={occurred_year!r}, tile_size_m={tile_size_m!r}"
        )

    resolved = max(matched, key=_catalog_sort_key)
    available_views = sorted((resolved.get("views") or {}).keys())
    if not available_views:
        raise RuntimeError("Resolved published record does not expose any views.")
    resolved_view = view or available_views[0]
    resolved_view_details = (resolved.get("views") or {}).get(resolved_view)
    if resolved_view_details is None:
        raise RuntimeError(
            f"View '{resolved_view}' is not valid for resource '{resource_name}'. "
            f"Valid values are: {', '.join(available_views)}"
        )

    return {
        "resource_name": resource_name,
        "filters": {
            "prediction_run_label": prediction_run_label,
            "occurred_year": occurred_year,
            "tile_size_m": tile_size_m,
            "view": resolved_view,
        },
        "resolved": {
            "manifest_path": resolved.get("manifest_path"),
            "artifact_kind": resolved.get("artifact_kind"),
            "run_label": resolved.get("run_label"),
            "prediction_run_label": resolved.get("prediction_run_label"),
            "document_mtime_utc": resolved.get("document_mtime_utc"),
            "available_views": available_views,
            "resolved_view": resolved_view,
            "resolved_view_path": resolved_view_details.get("path"),
            "contract_versions": resolved.get("contract_versions", {}),
            "selection": resolved.get("selection", {}),
            "lineage_trace": resolved.get("lineage_trace"),
            "stats": resolved.get("stats", {}),
        },
    }


def handle_published_api_request(
    method: str,
    raw_path: str,
    *,
    published_index_path: str | Path = "data/published_index/published_resources.json",
    dashboard_summary_path: str | Path = "data/dashboard/dashboard_summary.json",
    root_dir: str | Path = ".",
) -> tuple[int, dict[str, Any]]:
    root_path = Path(root_dir)
    index_input = _resolve_path(published_index_path, root_dir=root_path)
    dashboard_summary_input = _resolve_path(dashboard_summary_path, root_dir=root_path)
    parsed = urlsplit(raw_path)
    query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=False).items()}

    if method.upper() != "GET":
        return HTTPStatus.METHOD_NOT_ALLOWED, {
            "api_version": PUBLISHED_API_VERSION,
            "error": {
                "code": "method_not_allowed",
                "message": "Only GET is supported.",
            },
        }

    try:
        if parsed.path in {"/healthz", "/v1/healthz"}:
            return HTTPStatus.OK, {
                "api_version": PUBLISHED_API_VERSION,
                "status": "ok",
            }

        if parsed.path == "/v1/published-index":
            payload = _load_published_index(index_input)
            return HTTPStatus.OK, {
                "api_version": PUBLISHED_API_VERSION,
                "published_index_path": str(index_input),
                "index": payload,
            }

        if parsed.path == "/v1/dashboard-summary":
            payload = _load_dashboard_summary(dashboard_summary_input)
            return HTTPStatus.OK, {
                "api_version": PUBLISHED_API_VERSION,
                "dashboard_summary_path": str(dashboard_summary_input),
                "summary": payload,
            }

        if parsed.path in {"/v1/published-resource/latest", "/v1/published-resource/query"}:
            index_payload = _load_published_index(index_input)
            resolution = _resolve_latest_from_index(
                index_payload,
                resource_name=query.get("resource_name"),
                prediction_run_label=query.get("prediction_run_label"),
                occurred_year=_coerce_int(query.get("occurred_year"), field_name="occurred_year"),
                tile_size_m=_coerce_float(query.get("tile_size_m"), field_name="tile_size_m"),
                view=query.get("view"),
            )
            if parsed.path == "/v1/published-resource/latest":
                return HTTPStatus.OK, {
                    "api_version": PUBLISHED_API_VERSION,
                    "published_index_path": str(index_input),
                    "selection_policy": index_payload.get("selection_policy"),
                    **resolution,
                }

            manifest_path = _resolve_path(
                str(resolution["resolved"]["manifest_path"]),
                root_dir=root_path,
            )
            resource_payload = query_published_resource(
                manifest_path,
                view=resolution["resolved"]["resolved_view"],
                occurred_year=_coerce_int(query.get("occurred_year"), field_name="occurred_year"),
                min_score_band=query.get("min_score_band"),
                limit=_coerce_int(query.get("limit"), field_name="limit"),
                root_dir=root_path,
            )
            return HTTPStatus.OK, {
                "api_version": PUBLISHED_API_VERSION,
                "published_index_path": str(index_input),
                "selection_policy": index_payload.get("selection_policy"),
                "resolution": resolution["resolved"],
                "resource": resource_payload,
            }

        return HTTPStatus.NOT_FOUND, {
            "api_version": PUBLISHED_API_VERSION,
            "error": {
                "code": "not_found",
                "message": f"Unknown path: {parsed.path}",
            },
        }
    except RuntimeError as exc:
        return HTTPStatus.BAD_REQUEST, {
            "api_version": PUBLISHED_API_VERSION,
            "error": {
                "code": "bad_request",
                "message": str(exc),
            },
        }


def _handler_factory(
    *,
    published_index_path: Path,
    root_dir: Path,
    dashboard_dir: Path,
    dashboard_summary_path: Path,
) -> type[BaseHTTPRequestHandler]:
    class PublishedApiHandler(BaseHTTPRequestHandler):
        server_version = "RoadRiskPublishedAPI/1.0"

        def do_GET(self) -> None:  # noqa: N802
            dashboard_response = resolve_dashboard_asset_response(
                self.path,
                dashboard_dir=dashboard_dir,
                root_dir=root_dir,
            )
            if dashboard_response is not None:
                status, content_type, body = dashboard_response
                self.send_response(int(status))
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            status, payload = handle_published_api_request(
                "GET",
                self.path,
                published_index_path=published_index_path,
                dashboard_summary_path=dashboard_summary_path,
                root_dir=root_dir,
            )
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_HEAD(self) -> None:  # noqa: N802
            status, _payload = handle_published_api_request(
                "GET",
                self.path,
                published_index_path=published_index_path,
                dashboard_summary_path=dashboard_summary_path,
                root_dir=root_dir,
            )
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return PublishedApiHandler


def serve_published_api(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    published_index_path: str | Path = "data/published_index/published_resources.json",
    root_dir: str | Path = ".",
    dashboard_dir: str | Path = "dashboard",
    dashboard_summary_path: str | Path = "data/dashboard/dashboard_summary.json",
) -> None:
    handler_class = _handler_factory(
        published_index_path=Path(published_index_path),
        root_dir=Path(root_dir),
        dashboard_dir=Path(dashboard_dir),
        dashboard_summary_path=Path(dashboard_summary_path),
    )
    with ThreadingHTTPServer((host, port), handler_class) as server:
        print(
            json.dumps(
                {
                    "api_version": PUBLISHED_API_VERSION,
                    "dashboard_dir": str(dashboard_dir),
                    "dashboard_summary_path": str(dashboard_summary_path),
                    "host": host,
                    "port": port,
                    "published_index_path": str(published_index_path),
                    "root_dir": str(root_dir),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        server.serve_forever()
