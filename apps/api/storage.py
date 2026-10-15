"""S3-compatible object storage helpers for uploads and artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover
    boto3 = None
    Config = None
    ClientError = Exception

from pydantic_settings import BaseSettings, SettingsConfigDict


PUBLIC_DOWNLOAD_TIERS = frozenset({"public"})
RESTRICTED_DOWNLOAD_TIERS = frozenset(
    {
        "restricted",
        "internal",
        "partner_restricted",
        "analyst_only",
    }
)


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROAD_RISK_STORAGE_")

    endpoint_url: str | None = None
    region: str = "us-east-1"
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    bucket: str = "road-risk"
    public_bucket: str | None = None
    prefix: str = "artifacts"
    uploads_prefix: str = "uploads"
    reports_prefix: str = "reports"
    manifests_prefix: str = "manifests"
    addressing_style: str = "auto"
    use_ssl: bool = True
    verify_ssl: bool | str = True
    presign_expires_s: int = 3600
    auto_create_buckets: bool = False


@dataclass(frozen=True)
class StorageObject:
    bucket: str
    key: str
    etag: str | None = None
    version_id: str | None = None

    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


@dataclass(frozen=True)
class ArtifactAccess:
    storage_uri: str
    publication_tier: str
    access_mode: str
    download_url: str
    expires_in_s: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "storage_uri": self.storage_uri,
            "publication_tier": self.publication_tier,
            "access_mode": self.access_mode,
            "download_url": self.download_url,
            "expires_in_s": self.expires_in_s,
        }


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()


@lru_cache
def get_storage_client():
    if boto3 is None or Config is None:
        raise RuntimeError("boto3 is required for S3 object storage operations")
    settings = get_storage_settings()
    config = Config(s3={"addressing_style": settings.addressing_style})
    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        aws_session_token=settings.session_token,
        region_name=settings.region,
        use_ssl=settings.use_ssl,
        verify=settings.verify_ssl,
        config=config,
    )


def build_object_key(*parts: str, prefix: str | None = None) -> str:
    chunks = [part.strip("/") for part in (prefix, *parts) if part]
    return "/".join(chunk for chunk in chunks if chunk)


def build_artifact_key(*parts: str) -> str:
    settings = get_storage_settings()
    return build_object_key(*parts, prefix=settings.prefix)


def _safe_filename(filename: str, fallback: str) -> str:
    candidate = Path(filename).name.strip()
    return candidate or fallback


def build_upload_key(
    organization_id: str,
    filename: str,
    *,
    municipality_id: str | None = None,
    job_type: str | None = None,
) -> str:
    settings = get_storage_settings()
    return build_object_key(
        organization_id,
        municipality_id or "global",
        job_type or "generic_upload",
        _safe_filename(filename, "upload.bin"),
        prefix=settings.uploads_prefix,
    )


def build_report_key(
    organization_id: str,
    report_type: str,
    filename: str,
    *,
    municipality_id: str | None = None,
) -> str:
    settings = get_storage_settings()
    return build_object_key(
        organization_id,
        municipality_id or "global",
        report_type,
        _safe_filename(filename, "report.bin"),
        prefix=settings.reports_prefix,
    )


def build_manifest_key(
    organization_id: str,
    artifact_kind: str,
    filename: str,
    *,
    municipality_id: str | None = None,
) -> str:
    settings = get_storage_settings()
    return build_object_key(
        organization_id,
        municipality_id or "global",
        artifact_kind,
        _safe_filename(filename, "manifest.json"),
        prefix=settings.manifests_prefix,
    )


def build_generated_artifact_key(
    organization_id: str,
    artifact_kind: str,
    filename: str,
    *,
    municipality_id: str | None = None,
) -> str:
    return build_artifact_key(
        organization_id,
        municipality_id or "global",
        artifact_kind,
        _safe_filename(filename, "artifact.bin"),
    )


def parse_storage_uri(storage_uri: str) -> StorageObject:
    parsed = urlparse(storage_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Unsupported storage URI: {storage_uri}")
    key = parsed.path.lstrip("/")
    if not key:
        raise ValueError(f"Storage URI is missing an object key: {storage_uri}")
    return StorageObject(bucket=parsed.netloc, key=key)


def select_bucket_for_tier(publication_tier: str, *, bucket: str | None = None) -> str:
    if bucket:
        return bucket
    settings = get_storage_settings()
    normalized_tier = (publication_tier or "restricted").strip().lower()
    if normalized_tier in PUBLIC_DOWNLOAD_TIERS and settings.public_bucket:
        return settings.public_bucket
    return settings.bucket


def _ensure_bucket(bucket_name: str) -> None:
    settings = get_storage_settings()
    client = get_storage_client()
    try:
        client.head_bucket(Bucket=bucket_name)
        return
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code") or "")
        if error_code not in {"404", "NoSuchBucket", "NotFound"}:
            raise

    params: dict[str, Any] = {"Bucket": bucket_name}
    if settings.region and settings.region != "us-east-1":
        params["CreateBucketConfiguration"] = {"LocationConstraint": settings.region}
    client.create_bucket(**params)


def ensure_bucket(bucket: str | None = None) -> None:
    settings = get_storage_settings()
    _ensure_bucket(bucket or settings.bucket)


def ensure_default_buckets() -> None:
    settings = get_storage_settings()
    _ensure_bucket(settings.bucket)
    if settings.public_bucket and settings.public_bucket != settings.bucket:
        _ensure_bucket(settings.public_bucket)


def put_bytes(
    key: str,
    payload: bytes,
    *,
    bucket: str | None = None,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None,
) -> StorageObject:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    params: dict[str, Any] = {"Bucket": bucket_name, "Key": key, "Body": payload}
    if content_type:
        params["ContentType"] = content_type
    if metadata:
        params["Metadata"] = metadata
    response = client.put_object(**params)
    return StorageObject(
        bucket=bucket_name,
        key=key,
        etag=response.get("ETag"),
        version_id=response.get("VersionId"),
    )


def get_bytes(
    key: str,
    *,
    bucket: str | None = None,
) -> bytes:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    response = client.get_object(Bucket=bucket_name, Key=key)
    return response["Body"].read()


def put_json(
    key: str,
    payload: Any,
    *,
    bucket: str | None = None,
    metadata: dict[str, str] | None = None,
) -> StorageObject:
    return put_bytes(
        key,
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
        bucket=bucket,
        content_type="application/json",
        metadata=metadata,
    )


def upload_file(
    path: str | Path,
    key: str,
    *,
    bucket: str | None = None,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None,
) -> StorageObject:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    extra_args: dict[str, Any] = {}
    if content_type:
        extra_args["ContentType"] = content_type
    if metadata:
        extra_args["Metadata"] = metadata

    client.upload_file(str(path), bucket_name, key, ExtraArgs=extra_args or None)
    return StorageObject(bucket=bucket_name, key=key)


def download_file(
    key: str,
    path: str | Path,
    *,
    bucket: str | None = None,
) -> Path:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    client.download_file(bucket_name, key, str(target))
    return target


def list_objects(prefix: str, *, bucket: str | None = None) -> list[StorageObject]:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    response = client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    objects: list[StorageObject] = []
    for item in response.get("Contents", []) or []:
        objects.append(StorageObject(bucket=bucket_name, key=item.get("Key", "")))
    return objects


def delete_objects(keys: Iterable[str], *, bucket: str | None = None) -> int:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    payload = [{"Key": key} for key in keys if key]
    if not payload:
        return 0
    response = client.delete_objects(Bucket=bucket_name, Delete={"Objects": payload})
    return len(response.get("Deleted", []) or [])


def presign_get(key: str, *, bucket: str | None = None, expires_s: int | None = None) -> str:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=expires_s or settings.presign_expires_s,
    )


def presign_put(
    key: str,
    *,
    bucket: str | None = None,
    content_type: str | None = None,
    expires_s: int | None = None,
) -> str:
    settings = get_storage_settings()
    client = get_storage_client()
    bucket_name = bucket or settings.bucket
    params = {"Bucket": bucket_name, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    return client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_s or settings.presign_expires_s,
    )


def build_public_object_url(key: str, *, bucket: str | None = None) -> str:
    settings = get_storage_settings()
    bucket_name = bucket or settings.public_bucket or settings.bucket
    if settings.endpoint_url:
        return f"{settings.endpoint_url.rstrip('/')}/{bucket_name}/{key}"
    return f"s3://{bucket_name}/{key}"


def resolve_artifact_download(
    storage_uri: str,
    *,
    publication_tier: str,
    expires_s: int | None = None,
) -> ArtifactAccess:
    storage_object = parse_storage_uri(storage_uri)
    normalized_tier = (publication_tier or "restricted").strip().lower()
    if normalized_tier in PUBLIC_DOWNLOAD_TIERS:
        return ArtifactAccess(
            storage_uri=storage_uri,
            publication_tier=normalized_tier,
            access_mode="public_url",
            download_url=build_public_object_url(storage_object.key, bucket=storage_object.bucket),
            expires_in_s=None,
        )
    return ArtifactAccess(
        storage_uri=storage_uri,
        publication_tier=normalized_tier,
        access_mode="presigned_get",
        download_url=presign_get(
            storage_object.key,
            bucket=storage_object.bucket,
            expires_s=expires_s,
        ),
        expires_in_s=expires_s or get_storage_settings().presign_expires_s,
    )
