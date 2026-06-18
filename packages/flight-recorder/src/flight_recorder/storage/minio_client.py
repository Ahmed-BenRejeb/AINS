"""MinIO (S3-compatible) blob storage for cassette payloads.

Cassettes are stored as JSON blobs in the ``sentinel-cassettes`` bucket. MinIO
runs inside the Langfuse Docker stack on the VM (port 9090) — R2 was skipped
because it requires a credit card. This module is the only place that talks to
the S3 API; everything else goes through :func:`store_blob` / :func:`load_blob`.

Tests monkeypatch :func:`store_blob` / :func:`load_blob` with an in-memory dict,
so no real MinIO is needed to exercise the recorder.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import boto3

if TYPE_CHECKING:  # boto3-stubs are not installed; only needed for annotations.
    from mypy_boto3_s3.client import S3Client
else:  # pragma: no cover - runtime alias
    S3Client = Any

# MinIO ignores the region but boto3 still requires one (root CLAUDE.md gotcha).
_MINIO_REGION = "us-east-1"
_DEFAULT_BUCKET = "sentinel-cassettes"


@lru_cache(maxsize=1)
def get_s3_client() -> S3Client:
    """Build (and cache) the boto3 S3 client pointed at MinIO.

    Reads ``BLOB_STORAGE_ENDPOINT`` / ``BLOB_STORAGE_ACCESS_KEY`` /
    ``BLOB_STORAGE_SECRET_KEY`` from the environment.

    Returns:
        A configured boto3 ``s3`` client with ``endpoint_url`` set to MinIO.
    """
    return boto3.client(
        "s3",
        endpoint_url=os.environ["BLOB_STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["BLOB_STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["BLOB_STORAGE_SECRET_KEY"],
        region_name=_MINIO_REGION,
    )


def get_bucket() -> str:
    """Return the cassette bucket name (``BLOB_STORAGE_BUCKET`` or default)."""
    return os.environ.get("BLOB_STORAGE_BUCKET", _DEFAULT_BUCKET)


def store_blob(key: str, data: bytes) -> None:
    """Write ``data`` to ``key`` in the cassette bucket (overwrites).

    Args:
        key: Object key within the bucket (e.g. ``"<run_id>.json"``).
        data: Raw bytes to store.
    """
    get_s3_client().put_object(Bucket=get_bucket(), Key=key, Body=data)


def load_blob(key: str) -> bytes:
    """Read and return the bytes stored at ``key``.

    Args:
        key: Object key within the bucket.

    Returns:
        The stored object's bytes.

    Raises:
        botocore.exceptions.ClientError: If the key does not exist (``NoSuchKey``).
    """
    body: bytes = get_s3_client().get_object(Bucket=get_bucket(), Key=key)["Body"].read()
    return body


def blob_exists(key: str) -> bool:
    """Return ``True`` if an object exists at ``key`` in the cassette bucket."""
    from botocore.exceptions import ClientError

    try:
        get_s3_client().head_object(Bucket=get_bucket(), Key=key)
    except ClientError:
        return False
    return True
