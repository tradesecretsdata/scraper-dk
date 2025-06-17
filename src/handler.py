"""AWS Lambda handler – pandas-free implementation."""

from __future__ import annotations

import csv
import io
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List

from pipeline.fetch import fetch_main
from pipeline.parse import parse_main
from utils.s3_utils import build_key, upload_csv, upload_json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _rows_to_csv(rows: List[Dict[str, Any]]) -> str:
    """Convert list-of-dicts -> CSV string."""
    if not rows:
        return ""

    header = list(rows[0])
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------


def lambda_handler(
    event: Dict[str, Any], context: Any
) -> Dict[str, Any]:  # noqa: ANN401
    try:
        raw_payloads = fetch_main()  # <-- no S3 side-effects
        logger.info("Fetched %d raw endpoint payloads", len(raw_payloads))

        # -- upload raw -----------------------------------------------------
        bucket = os.getenv("BUCKET_NAME") or os.getenv("BucketName")
        prefix_raw = os.getenv("S3_PREFIX", "raw").strip("/")
        env_name = os.getenv("ENV", "dev").strip("/")

        ts = _utc_stamp()
        for ep_key, payload in raw_payloads.items():
            key = build_key(prefix_raw, env_name, "raw", ep_key, f"{ts}.json")
            upload_json(payload, key, bucket=bucket)

        # -- parse ----------------------------------------------------------
        rows = parse_main(raw_payloads)
        logger.info("Parsed %d Over/Under rows", len(rows))

        # -- upload processed CSV ------------------------------------------
        csv_content = _rows_to_csv(rows)
        proc_prefix = os.getenv("PROC_PREFIX", "processed").strip("/")
        proc_key = build_key(proc_prefix, f"{ts}.csv")
        upload_csv(csv_content, proc_key, bucket=bucket)

        logger.info("🎉 Pipeline complete")
        return {"status": "ok", "rows": len(rows)}

    except Exception as exc:
        logger.error("❌ Pipeline failed – %s", exc)
        logger.debug("Traceback:\n%s", "".join(traceback.format_exception(exc)))
        return {"status": "error", "error": str(exc)}
