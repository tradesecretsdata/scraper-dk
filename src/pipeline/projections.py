"""
Pitchers
        • Innings pitched = 2.25 = outs recorded / 3
        • Strikeout = 2
        • Win = 4
                ○ Definition: pitcher at the time the team takes the lead and does not relinquish it
                ○ Calculation must be based on innings pitched and game line
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
    "walks": 2.0,
    "hit_by_pitch": 2.0,
    "stolen": 5.0,
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
            fpts += weight * _safe(row.get(stat))
        row["fpts_batter"] = fpts
    return player_rows


# __all__ for export convenience
__all__ = [
    "compute_batter_fpts",
]
