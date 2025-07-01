"""Combine DraftKings contest CSV files for a given day/sport.

Step 2 of *agent-work-plan.md*
—————————————————————————
Read all ``.csv`` files from
``s3://{bucket}/dk-contests/{date}/{sport}/`` and return their rows as a
``list[dict]``.

Each file name (e.g. ``129974.csv``) is the **DraftKings slate ID**.  We add
this ID to every parsed row under the ``slate_id`` key.

Pandas is intentionally *not* used – we rely on the std-lib ``csv`` module to
keep the Lambda bundle small.
"""

from __future__ import annotations

import csv
import logging
import os
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List

import boto3

from utils.s3_utils import read_csv

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_S3 = boto3.client("s3")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_bucket() -> str:
    bucket = os.getenv("BUCKET_NAME") or os.getenv("BucketName")
    if not bucket:
        raise RuntimeError("Environment variable BUCKET_NAME must be set")
    return bucket


def _today_str() -> str:
    """Return current UTC date string – ``YYYY-MM-DD``."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _list_csv_keys(bucket: str, prefix: str) -> List[str]:
    """Return a *sorted* list of object keys under *prefix* ending ``.csv``."""
    paginator = _S3.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".csv"):
                keys.append(key)
    keys.sort()
    logger.info("Found %d CSV files under %s", len(keys), prefix)
    return keys


def _extract_slate_id(key: str) -> str:
    """Return the filename (without extension) from an S3 key."""
    filename = key.rsplit("/", 1)[-1]
    return re.sub(r"\.csv$", "", filename, flags=re.I)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_draftable_rows(
    *,
    date: str | None = None,
    sport: str = "mlb",
    bucket: str | None = None,
) -> List[Dict[str, Any]]:
    """Return concatenated rows from *every* contest CSV for the given day.

    Parameters
    ----------
    date
        ``YYYY-MM-DD`` (UTC). Defaults to *today* if omitted.
    sport
        League slug (default ``mlb``).
    bucket
        S3 bucket name. Falls back to the ``BUCKET_NAME`` env var.
    """

    bucket = bucket or _default_bucket()
    date = date or _today_str()

    prefix = f"dk-contests/{date}/{sport.strip('/')}/"

    rows: list[dict[str, Any]] = []

    for key in _list_csv_keys(bucket, prefix):
        slate_id = _extract_slate_id(key)
        csv_text = read_csv(key, bucket=bucket)
        reader = csv.DictReader(StringIO(csv_text))
        for r in reader:
            r = dict(r)  # copy – DictReader returns OrderedDict
            r["slate_id"] = slate_id
            rows.append(r)

    logger.info(
        "Loaded %d rows from %d contest CSVs",
        len(rows),
        len({r["slate_id"] for r in rows}),
    )
    return rows


# Convenience wrapper (placeholder until Step 3)
# ───────────────────────────────────────────────


def combine_main(
    *,
    date: str | None = None,
    sport: str = "mlb",
    bucket: str | None = None,
) -> List[Dict[str, Any]]:
    """Currently just calls :func:`load_draftable_rows`.

    In Step 3 we will accept *player_rows* and return the merged result.
    """

    return load_draftable_rows(date=date, sport=sport, bucket=bucket)
