"""
Parse DraftKings payloads and pivot into a player table with complete columns.

Exports
-------
parse_main(payloads)     -> list[dict]   # detailed bet rows
pivot_players(rows)      -> list[dict]   # one row per player, all subcats
parse_and_pivot(...)     -> (rows, pivot_rows)
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Tuple


# ──────────────────────────────
# Conversions / math utilities
# ──────────────────────────────
def _normalize_american(val) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace("−", "-").strip())
    except ValueError:
        return None


def _decimal_to_american(dec: float | None) -> int | None:
    if dec is None:
        return None
    return int(round((dec - 1) * 100)) if dec >= 2 else int(round(-100 / (dec - 1)))


def _american_to_prob(american: int | None) -> float | None:
    if american is None:
        return None
    if american >= 0:
        return 100 / (american + 100)
    return -american / (-american + 100)


def _vig_free_decimal(p_over: float, p_under: float) -> Tuple[float, float]:
    vig = p_over + p_under
    return 1 / (p_over / vig), 1 / (p_under / vig)


# ──────────────────────────────
#   Poisson helpers
# ──────────────────────────────
def _poisson_cdf(lam: float, k: int) -> float:
    term = math.exp(-lam)
    cumulative = term
    for i in range(1, k + 1):
        term *= lam / i
        cumulative += term
    return cumulative


def _solve_lambda(k: int, p_over: float, tol: float = 1e-6) -> float:
    target = 1.0 - p_over
    lo, hi = 0.0, 100.0
    for _ in range(60):
        mid = (lo + hi) / 2
        cdf_mid = _poisson_cdf(mid, k)
        if abs(cdf_mid - target) < tol:
            return mid
        if cdf_mid < target:  # λ too high → move hi down
            hi = mid
        else:  # λ too low  → move lo up
            lo = mid
    return (lo + hi) / 2.0


# ──────────────────────────────
# 1) Detailed row-level parser
# ──────────────────────────────
def parse_main(payloads: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for ep_key, payload in payloads.items():
        if "selections" not in payload:
            continue

        try:
            category_slug, subcat_slug = ep_key.split("/", 1)
        except ValueError:
            continue

        category = category_slug  # e.g. pitcher_props
        subcategory = subcat_slug

        groups: dict[Tuple[str, float | None], dict[str, Any]] = {}

        for sel in payload["selections"]:
            label = str(sel.get("label", "")).lower()
            if label not in {"over", "under"}:
                continue

            player = sel.get("participants", [{}])[0].get("name")
            points = sel.get("points")

            g = groups.setdefault(
                (player, points), {"player": player, "points": points}
            )
            g[label] = {
                "american": _normalize_american(sel["displayOdds"]["american"]),
                "decimal": float(sel["displayOdds"]["decimal"]),
            }

        for (player, points), g in groups.items():
            if "over" not in g or "under" not in g:
                continue

            over_dec = g["over"]["decimal"]
            under_dec = g["under"]["decimal"]

            p_over, p_under = 1 / over_dec, 1 / under_dec
            vf_over_dec, vf_under_dec = _vig_free_decimal(p_over, p_under)
            vf_over_amer = _decimal_to_american(vf_over_dec)
            vf_under_amer = _decimal_to_american(vf_under_dec)

            p_over_vf = _american_to_prob(vf_over_amer)
            k_floor = int(math.floor(points)) if points is not None else 0
            poisson_mean = (
                _solve_lambda(k_floor, p_over_vf) if p_over_vf is not None else None
            )

            rows.append(
                {
                    "category": category,
                    "subcategory": subcategory,
                    "player": player,
                    "points": points,
                    #
                    "over_decimal_odds": over_dec,
                    "over_american_odds": g["over"]["american"],
                    "under_decimal_odds": under_dec,
                    "under_american_odds": g["under"]["american"],
                    #
                    "vig_free_over_decimal_odds": vf_over_dec,
                    "vig_free_under_decimal_odds": vf_under_dec,
                    "vig_free_over_american_odds": vf_over_amer,
                    "vig_free_under_american_odds": vf_under_amer,
                    #
                    "poisson_mean": poisson_mean,
                }
            )

    return rows


# ──────────────────────────────
# 2) Player-pivot helper
# ──────────────────────────────
def pivot_players(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a “wide” table: one row per player, one column per subcategory,
    cell = poisson_mean. Ensures every row has **all** columns so the CSV
    header includes pitcher-only and batter-only props.

    Only categories pitcher_props / batter_props are considered.
    """
    table: dict[str, dict[str, Any]] = defaultdict(dict)
    all_subcats: set[str] = set()

    for r in rows:
        if r["category"] not in {"pitcher_props", "batter_props"}:
            continue
        if r["player"] is None:
            continue

        subcat = r["subcategory"]
        all_subcats.add(subcat)

        player_row = table[r["player"]]
        player_row["player"] = r["player"]
        player_row[subcat] = r["poisson_mean"]

    # ensure every row has every subcategory key
    for row in table.values():
        for subcat in all_subcats:
            row.setdefault(subcat, None)

    return list(table.values())


# ──────────────────────────────
# 3) Convenience wrapper
# ──────────────────────────────
def parse_and_pivot(
    payloads: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    detailed = parse_main(payloads)
    pivoted = pivot_players(detailed)
    return detailed, pivoted


# ──────────────────────────────
# Demo when executed directly
# ──────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    # Quick sanity demo
    demo = {
        "pitcher_props/strikeouts_ou": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "Max Fried"}],
                    "points": 6.5,
                    "displayOdds": {"american": "+120", "decimal": 2.2},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "Max Fried"}],
                    "points": 6.5,
                    "displayOdds": {"american": "-140", "decimal": 1.71},
                },
            ]
        },
        "batter_props/doubles": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "Max Fried"}],
                    "points": 0.5,
                    "displayOdds": {"american": "+200", "decimal": 3.0},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "Max Fried"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-300", "decimal": 1.33},
                },
            ]
        },
    }

    bets, players = parse_and_pivot(demo)

    from pprint import pprint

    pprint(players)
