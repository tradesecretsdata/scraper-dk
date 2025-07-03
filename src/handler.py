"""AWS Lambda entry point – now uploads TWO processed CSVs.

  • {PROC_PREFIX}/bets/{timestamp}.csv      – detailed, one row per bet
  • {PROC_PREFIX}/players/{timestamp}.csv   – one row per player (pivot)
  • {PROC_PREFIX}/combined/{timestamp}.csv  – merged DraftKings + props

Environment vars
----------------
BUCKET_NAME   – destination S3 bucket
S3_PREFIX     – prefix for raw JSON uploads  (default 'raw')
PROC_PREFIX   – prefix for processed outputs (default 'processed')
ENV           – env name used inside the raw prefix (default 'dev')
"""

from __future__ import annotations

import csv
import io
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List

from pipeline.fetch import fetch_main
from pipeline.parse import parse_and_pivot  # ← returns bets, players
from pipeline.projections import compute_batter_fpts, add_role_column
from utils.s3_utils import build_key, upload_csv, upload_json
from combine import combine_main, sanitize_player_rows

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _rows_to_csv(rows: List[Dict[str, Any]]) -> str:
    """Convert list-of-dict rows → CSV string with all columns present.

    The original version relied on the *first* row to define the header,
    causing later rows that had additional keys to drop those columns – this
    hid player-prop stats in the *combined* CSV.  We now build the header as
    the *union* of keys across all rows, preserving order (first-seen wins).
    """
    if not rows:
        return ""

    # Build ordered header union
    seen: set[str] = set()
    header: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                header.append(k)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(
    event: Dict[str, Any], context: Any
) -> Dict[str, Any]:  # noqa: ANN401
    try:
        bucket = os.getenv("BUCKET_NAME") or os.getenv("BucketName")
        raw_prefix = os.getenv("S3_PREFIX", "raw").strip("/")
        proc_prefix = os.getenv("PROC_PREFIX", "processed").strip("/")
        env_name = os.getenv("ENV", "dev").strip("/")

        timestamp = _utc_stamp()

        # 1) Fetch DraftKings endpoints
        raw_payloads = fetch_main()
        logger.info("Fetched %d endpoint payloads", len(raw_payloads))

        # 2) Upload RAW JSONs
        for ep_key, payload in raw_payloads.items():
            key = build_key(raw_prefix, env_name, "raw", ep_key, f"{timestamp}.json")
            upload_json(payload, key, bucket=bucket)

        # 3) Parse → two tables
        bet_rows, player_rows = parse_and_pivot(raw_payloads)
        logger.info("Parsed bets=%d  players=%d", len(bet_rows), len(player_rows))

        # 3½) Normalize column names (no fantasy point projections here – moved after combine)
        player_rows = sanitize_player_rows(player_rows)

        # 4) Upload processed CSVs (bets / players)
        bets_key = build_key(proc_prefix, "bets", f"{timestamp}.csv")
        players_key = build_key(proc_prefix, "players", f"{timestamp}.csv")

        upload_csv(_rows_to_csv(bet_rows), bets_key, bucket=bucket)
        upload_csv(_rows_to_csv(player_rows), players_key, bucket=bucket)

        # 5) Combine with draftable CSVs
        combined_rows = combine_main(player_rows=player_rows, bucket=bucket)

        # 5½) Assign role and compute fantasy points on *combined* rows
        combined_rows = add_role_column(combined_rows)
        combined_rows = compute_batter_fpts(combined_rows)

        # Now upload the combined CSV
        combined_key = build_key(proc_prefix, "combined", f"{timestamp}.csv")
        upload_csv(_rows_to_csv(combined_rows), combined_key, bucket=bucket)

        logger.info(
            "🎉 Uploaded bets → %s, players → %s, combined → %s",
            bets_key,
            players_key,
            combined_key,
        )

        # Return counts for monitoring
        return {
            "status": "ok",
            "bets_rows": len(bet_rows),
            "players_rows": len(player_rows),
            "combined_rows": len(combined_rows),
        }

    except Exception as exc:
        logger.error("❌ Pipeline failed – %s", exc)
        logger.debug("Traceback:\n%s", "".join(traceback.format_exception(exc)))
        return {"status": "error", "error": str(exc)}
