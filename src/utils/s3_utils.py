"""Utility helpers for S3 upload / download.

All Lambda code should import these helpers instead of instantiating
`boto3.client("s3")` directly.  This keeps S3 interaction in one place
and makes future changes (signing, encryption, logging, retries, …)
trivial.
"""

from __future__ import annotations

import io
import json
import logging
import os
from typing import Any

import boto3
import pandas as pd

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Single shared client – cold-start cost only once
_S3 = boto3.client("s3")


def _default_bucket() -> str:
    bucket = os.getenv("BUCKET_NAME") or os.getenv("BucketName")
    if not bucket:
        raise RuntimeError(
            "Environment variable 'BUCKET_NAME' (or legacy 'BucketName') must be set"
        )
    return bucket


def build_key(*parts: str) -> str:  # noqa: D401
    """Return an S3 key by clean-joining the given path parts."""
    return "/".join(p.strip("/") for p in parts if p)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def upload_json(data: Any, key: str, bucket: str | None = None) -> None:
    """Serialize *data* to JSON and upload to ``s3://bucket/key``."""
    bucket = bucket or _default_bucket()
    _S3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, separators=(",", ":")).encode(),
        ContentType="application/json",
    )
    logger.info("✅  JSON uploaded → s3://%s/%s", bucket, key)


def upload_dataframe(df: pd.DataFrame, key: str, bucket: str | None = None) -> None:
    """Upload *df* as UTF-8 CSV to ``s3://bucket/key``."""
    bucket = bucket or _default_bucket()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    _S3.put_object(
        Bucket=bucket,
        Key=key,
        Body=buf.getvalue().encode(),
        ContentType="text/csv",
    )
    logger.info("✅  CSV uploaded → s3://%s/%s  (rows=%d)", bucket, key, len(df))
