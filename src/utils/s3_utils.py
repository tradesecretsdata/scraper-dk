"""Lightweight S3 helpers – no pandas required."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_S3 = boto3.client("s3")


def _default_bucket() -> str:
    bucket = os.getenv("BUCKET_NAME") or os.getenv("BucketName")
    if not bucket:
        raise RuntimeError("Environment variable BUCKET_NAME must be set")
    return bucket


def build_key(*parts: str) -> str:
    """Return an S3 key by clean-joining ``parts`` with single ‘/’."""
    return "/".join(p.strip("/") for p in parts if p)


# ---------------------------------------------------------------------------
# Upload helpers – **no pandas**
# ---------------------------------------------------------------------------


def upload_json(data: Any, key: str, bucket: str | None = None) -> None:
    bucket = bucket or _default_bucket()
    _S3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, separators=(",", ":")).encode(),
        ContentType="application/json",
    )
    logger.info("✅  JSON uploaded → s3://%s/%s", bucket, key)


def upload_csv(text: str, key: str, bucket: str | None = None) -> None:
    """Upload raw CSV text (UTF-8) to S3."""
    bucket = bucket or _default_bucket()
    _S3.put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode(),
        ContentType="text/csv",
    )
    logger.info("✅  CSV uploaded → s3://%s/%s", bucket, key)
