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
        • Complete game = 2.5 (?)
        • Complete game shutout = 2.5 (?)
        • No hitter = 5 = poisson probability of hit against = 0
                ○ May not be exactly right but these last 3 don't matter much


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
    • If ``role == 'Pitcher'`` the **fpts** cell is left blank (empty string)
      for now – pitcher projections will be added in a later milestone.

    The function mutates *player_rows* in-place and also *removes* any prior
    ``fpts_batter`` key to keep the table tidy.
    """

    for row in player_rows:
        role = str(row.get("role", "")).strip().title()
        if role == "Batter":
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
            # Placeholder for future pitcher logic
            row["fpts"] = ""
            row["pts/$"] = ""

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
