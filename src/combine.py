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


# ---------------------------------------------------------------------------
# Step 3 – merge with player prop data
# ---------------------------------------------------------------------------


def _build_player_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return mapping ``player_name`` → *row* built from *player_rows*."""
    idx: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = r.get("player")
        if name:
            idx[str(name)] = r
    return idx


def merge_rows(
    *,
    player_rows: List[Dict[str, Any]],
    draft_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return **combined** rows by joining on player-name.

    • Draftable rows use key ``name``.
    • Player prop rows use key ``player``.

    A *left-outer* style join is applied:
      – Every draftable row is preserved with added player-prop columns.
      – Player-only rows with **no** matching draft row are appended as
        additional rows (only props columns).
    """

    idx = _build_player_index(player_rows)

    merged: list[dict[str, Any]] = []
    matched_players: set[str] = set()

    for d in draft_rows:
        name = str(d.get("name"))
        combined = {**d}

        prow = idx.get(name)
        if prow:
            combined.update(prow)
            matched_players.add(name)

        merged.append(combined)

    # Append unmatched player prop rows
    for name, prow in idx.items():
        if name in matched_players:
            continue
        merged.append(dict(prow))

    logger.info(
        "Merged draftable=%d with player_props=%d → rows=%d",
        len(draft_rows),
        len(player_rows),
        len(merged),
    )
    return merged


# ---------------------------------------------------------------------------
# Column sanitization helper (Step 5 fix)
# ---------------------------------------------------------------------------


def sanitize_player_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return *rows* with every key having trailing '_ou' / '_OU' removed.

    Operates **in-place** on each row – this keeps downstream code untouched
    and avoids unnecessary copies in Lambda memory-constrained environment.
    """
    for r in rows:
        for key in list(r.keys()):
            if key.lower().endswith("_ou"):
                base = key[:-3]
                # Do not overwrite existing base key if already present
                if base not in r:
                    r[base] = r[key]
                del r[key]
    return rows


# ---------------------------------------------------------------------------
# Post-merge cleanup helper (Step 8 fix)
# ---------------------------------------------------------------------------


def clean_combined_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return *rows* with duplicates dropped and slate_id != 0.

    Duplicate detection is based on the **full row content**: rows that are
    byte-for-byte identical after converting to a sorted tuple of key/value
    pairs are considered duplicates (first occurrence is kept).

    Rows where the ``slate_id`` column is missing or equals ``0`` (string or
    int) are *excluded* from the result.
    """

    seen: set[tuple] = set()
    cleaned: list[dict[str, Any]] = []

    for r in rows:
        slate = str(r.get("slate_id", "")).strip()
        if slate == "0" or slate == "":
            continue  # drop invalid slate rows

        key_tuple = tuple(sorted(r.items()))
        if key_tuple in seen:
            continue  # duplicate row – skip
        seen.add(key_tuple)
        cleaned.append(r)

    return cleaned


# ---------------------------------------------------------------------------
# Column rename/drop/reorder helper (Step 10)
# ---------------------------------------------------------------------------


def finalize_combined_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply column rename, drop, and ordering rules required before upload.

    Operations applied IN-PLACE on each row:
      1. **Rename** keys per ``_RENAME_MAP`` if present.
      2. **Drop** keys in ``_DROP_KEYS``.
      3. **Re-order** keys so preferred columns appear first.

    The function returns *rows* (same list) for convenience.
    """

    # --- config ---------------------------------------------------------
    _RENAME_MAP = {
        "slate_start_str": "slate_start",
        "name": "player",
        "pos": "position",
        "opp": "opponent",
        "opp_sp": "opponent_sp",
    }
    _DROP_KEYS = {
        "slate_id",
        "playerid",  # lowercase variant
        "playerId",  # camelCase variant (Step 14 fix)
        "game_start",
        "vig_free_spread",  # obsolete after Step 20 fix
    }

    _PREFERRED_ORDER = [
        # ── core player info ───────────────────────────────
        "player",
        "fpts",
        "fpts_complete",
        "dk_salary",
        "pts/$",
        "position",
        "team",
        "opponent",
        "opponent_sp",
        # ── game betting columns (Step 19 + Step 20 fix) ───────────────
        "spread",
        "total",
        "vig_free_moneyline",
        "pct_win",
        # ── slate metadata (Step 13 feature) ───────────────
        "game_type",
        "num_games",
        "slate_start",
        "slate_display",
        # ── batter stats (Step 12 fix – reorder stat columns) ──
        "singles",
        "doubles",
        "triples",
        "home_runs",
        "stolen_bases",
        "runs",
        "rbis",
        "walks_batter",
        "hit_by_pitch",
        # ── pitcher stats ───────────────────────────────────
        "earned_runs_allowed",
        "outs_recorded",
        "strikeouts_thrown",
        "hits_allowed",
        "walks_allowed",
    ]

    for i, r in enumerate(rows):
        # ----- rename ----------------------------------------------------
        for old_key, new_key in _RENAME_MAP.items():
            if old_key in r:
                # Always prefer the renamed value (likely string) over existing
                r[new_key] = r.pop(old_key)

        # ----- drop ------------------------------------------------------
        for k in list(r.keys()):
            if k in _DROP_KEYS:
                r.pop(k, None)

        # ----- slate_display (Step 13) ----------------------------------
        if "slate_display" not in r:
            slate_start_val = r.get("slate_start")
            num_games_val = r.get("num_games")
            if slate_start_val is not None and num_games_val is not None:
                r["slate_display"] = f"{slate_start_val} - {num_games_val} games"

        # Ensure we don't keep both 'name' and renamed 'player'
        if "name" in r and "player" in r:
            r.pop("name")

        # ----- reorder ---------------------------------------------------
        ordered = {}
        for k in _PREFERRED_ORDER:
            if k in r:
                ordered[k] = r[k]
        # Append remaining keys in their existing insertion order
        for k in r.keys():
            if k not in ordered:
                ordered[k] = r[k]
        # Replace row dict in list to preserve order for CSV header union
        rows[i] = ordered

    return rows


# ---------------------------------------------------------------------------
# Public combine_main
# ---------------------------------------------------------------------------


def combine_main(
    *,
    player_rows: List[Dict[str, Any]],
    date: str | None = None,
    sport: str = "mlb",
    bucket: str | None = None,
) -> List[Dict[str, Any]]:
    """High-level helper used by Lambda handler.

    1. Loads DraftKings *draftable* player CSVs from S3
    2. Merges them onto *player_rows* (pivoted prop table)
    3. Returns the combined row list ready for CSV upload
    """

    draft_rows = load_draftable_rows(date=date, sport=sport, bucket=bucket)
    merged = merge_rows(player_rows=player_rows, draft_rows=draft_rows)
    return clean_combined_rows(merged)


__all__ = [
    "load_draftable_rows",
    "merge_rows",
    "sanitize_player_rows",
    "combine_main",
    "clean_combined_rows",
    "finalize_combined_rows",
]
