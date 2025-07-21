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
from pipeline.projections import compute_fpts, add_role_column
from pipeline.game_bets import extract_game_rows, build_game_index
from utils.s3_utils import build_key, upload_csv, upload_json
from pipeline.combine import (
    combine_main,
    sanitize_player_rows,
    finalize_combined_rows,
    _PREFERRED_ORDER,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _rows_to_csv(
    rows: List[Dict[str, Any]],
    *,
    preferred_order: List[str] | None = None,
) -> str:
    """Convert list-of-dict *rows* to a CSV string.

    The header is built as the *union* of keys across all rows.  If
    *preferred_order* is provided, columns present in that list are ordered
    accordingly at the front of the header while preserving their specified
    sequence.  Any remaining columns are appended in the order they are first
    encountered (first-seen wins). This guarantees that important columns
    like ``hit_by_pitch`` or ``innings_pitched`` respect their desired
    position regardless of which row happens to appear first.
    """

    if not rows:
        return ""

    # ------------------------------------------------------------------
    # 1) Build ordered header union (first-seen wins)
    # ------------------------------------------------------------------
    seen: set[str] = set()
    header: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                header.append(k)

    # ------------------------------------------------------------------
    # 2) Apply preferred ordering if provided
    # ------------------------------------------------------------------
    if preferred_order is not None:
        ordered_header: list[str] = []

        # First – columns that appear in preferred_order AND header
        for col in preferred_order:
            if col in header:
                ordered_header.append(col)

        # Then – any remaining columns in their existing order
        for col in header:
            if col not in ordered_header:
                ordered_header.append(col)

        header = ordered_header

    # ------------------------------------------------------------------
    # 3) DictWriter → CSV string
    # ------------------------------------------------------------------
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

        # 5a) Extract and join game betting data (Steps 17–19)
        game_rows = extract_game_rows(raw_payloads)
        logger.info("Extracted %d game-betting rows", len(game_rows))

        if game_rows:
            game_idx = build_game_index(game_rows)
            for row in combined_rows:
                abbr = str(row.get("team"))
                g = game_idx.get(abbr)
                if g:
                    # replace vig_free_spread with raw spread amount → 'spread'
                    row["spread"] = g.get("spread_amount")
                    row["total"] = g.get("total")
                    row["vig_free_moneyline"] = g.get("vig_free_moneyline")
                    row["pct_win"] = g.get("pct_win")

            # ensure legacy column removed if still present
            for row in combined_rows:
                row.pop("vig_free_spread", None)

        # 5½) Assign role and compute fantasy points on *combined* rows
        combined_rows = add_role_column(combined_rows)
        combined_rows = compute_fpts(combined_rows)

        # 5⅝) Add pitcher win probability component and adjust fpts (Step 25)
        def _safe(val: Any) -> float:
            try:
                return float(val) if val not in (None, "") else 0.0
            except (TypeError, ValueError):
                return 0.0

        for row in combined_rows:
            role = str(row.get("role", "")).strip().title()
            if role == "Pitcher":
                # Compute innings pitched (already present or derive)
                ip_val = row.get("innings_pitched")
                if ip_val in (None, ""):
                    outs_val = row.get("outs_recorded")
                    ip = _safe(outs_val) / 3.0 if outs_val not in (None, "") else None
                else:
                    ip = _safe(ip_val)

                pct_win = row.get("pct_win")
                if ip is not None and pct_win not in (None, ""):
                    pct_pitcher_win = _safe(pct_win) * ip / 9.0
                else:
                    pct_pitcher_win = None

                row["pct_pitcher_win"] = (
                    pct_pitcher_win if pct_pitcher_win is not None else ""
                )

                # Add to fantasy points (4 pts per win probability share)
                fpts_before = _safe(row.get("fpts"))
                fpts_after = fpts_before + 4.0 * _safe(pct_pitcher_win)
                row["fpts"] = fpts_after

                # Recalculate pts/$ if salary available
                salary = _safe(row.get("dk_salary"))
                if salary > 0:
                    row["pts/$"] = 1000 * fpts_after / salary

                # Update fpts_complete (now requires pct_pitcher_win)
                required_fields = [
                    "earned_runs_allowed",
                    "outs_recorded",
                    "strikeouts_thrown",
                    "hits_allowed",
                    "walks_allowed",
                    "pct_pitcher_win",
                ]
                row["fpts_complete"] = all(
                    row.get(fld) not in (None, "") for fld in required_fields
                )
            else:
                # Ensure column exists for batters to retain CSV header
                if "pct_pitcher_win" not in row:
                    row["pct_pitcher_win"] = ""

        # 5¾) Final column cleanup (rename/drop/order)
        combined_rows = finalize_combined_rows(combined_rows)

        # Now upload the combined CSV
        combined_key = build_key(proc_prefix, "combined", f"{timestamp}.csv")
        upload_csv(
            _rows_to_csv(combined_rows, preferred_order=_PREFERRED_ORDER),
            combined_key,
            bucket=bucket,
        )

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
