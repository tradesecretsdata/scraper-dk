"""
Parse DraftKings JSON payloads into merged Over/Under rows.

Adds a `poisson_mean` column – the λ that reproduces the vig-free
probability of going *over* the betting line, assuming a Poisson model.
No pandas / numpy required.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


# ──────────────────────────────
# Basic conversions / utilities
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
    """Return P(X ≤ k) for X~Poisson(λ) via direct summation."""
    term = math.exp(-lam)
    cumulative = term  # P(X=0)
    for i in range(1, k + 1):
        term *= lam / i
        cumulative += term
    return cumulative


def _solve_lambda(k: int, p_over: float, tol: float = 1e-6) -> float:
    """
    Find λ such that P(X > k) = p_over.

    Because the Poisson CDF is **monotonically decreasing** in λ
    for any fixed k, we binary-search on that property.

    Parameters
    ----------
    k        floor(points)
    p_over   vig-free probability of going over the line
    """
    target_cdf = 1.0 - p_over
    lo, hi = 0.0, 100.0  # 100 is safely above any realistic MLB prop mean

    for _ in range(60):  # enough for ~1e-18 precision
        mid = (lo + hi) / 2
        cdf_mid = _poisson_cdf(mid, k)

        if abs(cdf_mid - target_cdf) < tol:
            return mid

        # CDF decreases with λ:
        #  • if cdf_mid < target  → λ too HIGH → move upper bound down
        #  • if cdf_mid > target  → λ too LOW  → move lower bound up
        if cdf_mid < target_cdf:
            hi = mid
        else:
            lo = mid

    return (lo + hi) / 2.0


# ──────────────────────────────
#           Public API
# ──────────────────────────────
def parse_main(payloads: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert raw endpoint payloads to list-of-dict rows.

    Keeps only Over/Under markets that have both sides.
    """
    rows: list[dict[str, Any]] = []

    for ep_key, payload in payloads.items():
        if "selections" not in payload:
            continue

        try:
            category_slug, subcat_slug = ep_key.split("/", 1)
        except ValueError:
            continue  # malformed key

        category = category_slug
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

            # --- Poisson mean ---------------------------------------------
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
# Tiny demo
# ──────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    sample = {
        "pitcher_props/triples_ou": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "John"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "John"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
            ]
        }
    }

    from pprint import pprint

    pprint(parse_main(sample))
