"""
Pitchers
        • Innings pitched = 2.25 (computed from outs recorded divided by 3)
        • Strikeout = 2
        • Win = 4
                ○ Definition: pitcher at the time the team takes the lead and does not relinquish it
                ○ Calculation must be based on innings pitched and moneyline
        • Earned run allowed = -2
        • Hit against = -0.6
        • Base on balls against = -0.6
        • Hit batsman = -0.6

Batters
        • Single = 3
        • Double = 5
        • Triple = 8
        • Home Run = 10
        • Run batted in = 2
        • Run = 2
        • Base on balls (walks) = 2
        • Hit by pitch = 2
        • Stolen base = 5
"""

from __future__ import annotations
from typing import Dict, List, Any

# ───────────────────────────────────────────────────────────────
# Fantasy point weights (DraftKings scoring)
# ───────────────────────────────────────────────────────────────
_BATTER_WEIGHTS: dict[str, float] = {
    "singles": 3.0,
    "doubles": 5.0,
    "triples": 8.0,
    "home_runs": 10.0,
    "rbis": 2.0,
    "runs": 2.0,
    "walks_batter": 2.0,
    "hit_by_pitch": 2.0,
    "stolen_bases": 5.0,
}

# Pitcher fantasy point weights (DraftKings scoring – Step 22 feature)
_PITCHER_WEIGHTS: dict[str, float] = {
    "innings_pitched": 2.25,
    "strikeouts_thrown": 2.0,
    "earned_runs_allowed": -2.0,
    "hits_allowed": -0.6,
    "walks_allowed": -0.6,
    "hit_batsman": -0.6,
}


def _safe(val: Any) -> float:
    """Return numeric value or 0 when None / not-a-number."""
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def compute_batter_fpts(player_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add DraftKings fantasy point projection to *each* player row.

    The function appends a ``fpts_batter`` key to every row, calculated as the
    weighted sum of mean event counts (Poisson means) for each offensive stat.

    Any missing statistic is treated as zero. The input list is modified in
    place and returned for convenience.
    """
    for row in player_rows:
        fpts = 0.0
        for stat, weight in _BATTER_WEIGHTS.items():
            # Accept both raw stat key and *_ou variants
            val = row.get(stat) if stat in row else row.get(f"{stat}_ou")
            fpts += weight * _safe(val)
        row["fpts_batter"] = fpts
    return player_rows


# ───────────────────────────────────────────────────────────────
# Helper – assign player role
# ───────────────────────────────────────────────────────────────


def add_role_column(player_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add a ``role`` column based on the player's *pos* value.

    A player is considered a **Pitcher** when ``pos`` equals ``SP`` or
    ``RP`` (case-insensitive). All other positions are treated as
    **Batter**.

    The function mutates *player_rows* in place and returns the same list for
    convenience.
    """

    for row in player_rows:
        pos_val = str(row.get("pos", "")).strip().upper()
        row["role"] = "Pitcher" if pos_val in {"SP", "RP"} else "Batter"
    return player_rows


def compute_fpts(player_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach a general ``fpts`` projection to each row based on *role*.

    • If ``role == 'Batter'`` the DraftKings scoring weights are applied using
      the same logic as *compute_batter_fpts*.
    • If ``role == 'Pitcher'`` the DraftKings pitcher scoring weights are
      applied. This includes deriving *innings_pitched* from *outs_recorded*,
      estimating *hit_batsman* from a league-average rate (0.42 per 9 IP), and
      summing fantasy points via the weights in ``_PITCHER_WEIGHTS``.

    The function mutates *player_rows* in-place and also *removes* any prior
    ``fpts_batter`` key to keep the table tidy.
    """

    for row in player_rows:
        role = str(row.get("role", "")).strip().title()
        if role == "Batter":
            # ── Step 26: ensure stolen_bases defaults to 0 for batters ──
            if row.get("stolen_bases") in (None, ""):
                row["stolen_bases"] = 0.0
            # Compute batter fantasy points using the existing weights
            fpts = 0.0
            for stat, weight in _BATTER_WEIGHTS.items():
                val = row.get(stat) if stat in row else row.get(f"{stat}_ou")
                fpts += weight * _safe(val)
            row["fpts"] = fpts

            # -- pts/$ value metric -------------------------------------
            salary = _safe(row.get("dk_salary"))
            if salary > 0:
                # Multiply by 1000 to express points per $1000 salary (Step 11 fix)
                row["pts/$"] = 1000 * fpts / salary
            else:
                row["pts/$"] = ""
        else:
            # ── Pitcher fantasy points (Step 22) ───────────────────────
            # 1. Derive innings pitched from outs recorded (3 outs = 1 IP)
            outs_val = row.get("outs_recorded")
            if outs_val in (None, ""):
                innings_pitched = None
            else:
                innings_pitched = _safe(outs_val) / 3.0

            # Add innings_pitched column (blank if unknown)
            row["innings_pitched"] = (
                innings_pitched if innings_pitched is not None else ""
            )

            # 2. Estimate hit batsmen based on league-average 0.42 per 9 IP
            if innings_pitched is not None:
                hit_batsman_val = 0.42 * innings_pitched / 9.0
            else:
                hit_batsman_val = None
            row["hit_batsman"] = hit_batsman_val if hit_batsman_val is not None else ""

            # 3. Compute pitcher fantasy points using weights
            fpts = 0.0
            for stat, weight in _PITCHER_WEIGHTS.items():
                fpts += weight * _safe(row.get(stat))
            row["fpts"] = fpts

            # Ensure 'hit_by_pitch' is blank for pitchers (Step 23 fix)
            row["hit_by_pitch"] = ""

            # 4. pts/$ metric (same formula as batters)
            salary = _safe(row.get("dk_salary"))
            row["pts/$"] = 1000 * fpts / salary if salary > 0 else ""

        # ----- fpts_complete flag (Step 15) ----------------------------
        # Determine if all required stat inputs are present (non-empty)
        if role == "Batter":
            required_fields = [
                "singles",
                "doubles",
                "triples",
                "home_runs",
                "stolen_bases",
                "runs",
                "rbis",
                "walks_batter",
                "hit_by_pitch",
            ]
        else:  # Pitcher
            required_fields = [
                "earned_runs_allowed",
                "outs_recorded",
                "strikeouts_thrown",
                "hits_allowed",
                "walks_allowed",
            ]

        row["fpts_complete"] = all(
            row.get(fld) not in (None, "") for fld in required_fields
        )

        # Drop legacy key if present
        if "fpts_batter" in row:
            del row["fpts_batter"]
    return player_rows


# __all__ for export convenience
__all__ = [
    "compute_batter_fpts",
    "add_role_column",
    "compute_fpts",
]
