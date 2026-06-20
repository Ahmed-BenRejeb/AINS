"""Read a run's full cassette from MinIO for non-lossy trace reconstruction.

The flight recorder tapes every step's full :class:`~trace_core.TraceRecord` into
the run's cassette blob (``{run_id}.json`` in the ``sentinel-cassettes`` bucket);
Cloudflare D1 only keeps truncated previews for cheap listing. The eval engine
therefore prefers the cassette — this module is the read-only S3 access to it,
mirroring the flight recorder's ``minio_client`` write side.

MinIO runs inside the Langfuse Docker stack on the VM (port 9090) — R2 was skipped
because it requires a credit card. Tests monkeypatch :func:`load_blob`, so no real
MinIO (or network) is touched.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import boto3
from trace_core import TraceRecord

if TYPE_CHECKING:  # boto3-stubs are not installed; only needed for annotations.
    from mypy_boto3_s3.client import S3Client
else:  # pragma: no cover - runtime alias
    S3Client = Any

# MinIO ignores the region but boto3 still requires one (root CLAUDE.md gotcha).
_MINIO_REGION = "us-east-1"
_DEFAULT_BUCKET = "sentinel-cassettes"


@lru_cache(maxsize=1)
def get_s3_client() -> S3Client:
    """Build (and cache) the boto3 S3 client pointed at MinIO (read side).

    Reads ``BLOB_STORAGE_ENDPOINT`` / ``BLOB_STORAGE_ACCESS_KEY`` /
    ``BLOB_STORAGE_SECRET_KEY`` from the environment (``endpoint_url`` →
    ``http://localhost:9090`` on the VM, internal only).
    """
    return boto3.client(
        "s3",
        endpoint_url=os.environ["BLOB_STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["BLOB_STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["BLOB_STORAGE_SECRET_KEY"],
        region_name=_MINIO_REGION,
    )


def _bucket() -> str:
    """Return the cassette bucket name (``BLOB_STORAGE_BUCKET`` or default)."""
    return os.environ.get("BLOB_STORAGE_BUCKET", _DEFAULT_BUCKET)


def load_blob(key: str) -> bytes:
    """Read and return the bytes stored at ``key`` in the cassette bucket.

    Args:
        key: Object key within the bucket (e.g. ``"<run_id>.json"``).

    Returns:
        The stored object's bytes.

    Raises:
        botocore.exceptions.ClientError: If the key does not exist (``NoSuchKey``).
    """
    body: bytes = get_s3_client().get_object(Bucket=_bucket(), Key=key)["Body"].read()
    return body


def load_cassette_records(run_id: str) -> list[TraceRecord] | None:
    """Load a run's full trace from its MinIO cassette.

    Args:
        run_id: UUID of the run.

    Returns:
        The run's steps as :class:`~trace_core.TraceRecord` objects (unordered), or
        ``None`` when the cassette does not exist or carries no full ``records``
        (an older record-less cassette) — signalling the caller to fall back to the
        D1 previews.
    """
    from botocore.exceptions import ClientError

    try:
        raw = load_blob(f"{run_id}.json")
    except ClientError:
        return None
    cassette: dict[str, Any] = json.loads(raw)
    records = cassette.get("records") or []
    if not records:
        return None
    return [TraceRecord.model_validate(record) for record in records]
