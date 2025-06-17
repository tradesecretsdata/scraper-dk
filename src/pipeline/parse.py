"""Transform DraftKings API payloads into merged Over/Under rows.

Now returns a **subcategory** column in addition to category.
No pandas / numpy required.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


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


def _vig_free_decimal(p_over: float, p_under: float) -> Tuple[float, float]:
    vig = p_over + p_under
    return 1 / (p_over / vig), 1 / (p_under / vig)


# ---------------------------------------------------------------------------


def parse_main(payloads: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert raw DraftKings payloads into a list of dict rows.

    Each row contains:
      • category      -> “game”, “batter”, or “pitcher”
      • subcategory   -> e.g. “doubles”, “walks allowed”
      • merged Over / Under lines
      • vig-free decimal & American odds
    """
    rows: list[dict[str, Any]] = []

    for ep_key, payload in payloads.items():
        if "selections" not in payload:
            continue

        try:
            category_slug, subcat_slug = ep_key.split("/", 1)
        except ValueError:  # malformed key
            continue

        # category remains the slug (game / batter / pitcher)
        category = category_slug

        # subcategory – nice readable form, lower-case with spaces
        subcategory = re.sub(r"[_\-]+", " ", subcat_slug).lower()

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
                    "vig_free_over_american_odds": _decimal_to_american(vf_over_dec),
                    "vig_free_under_american_odds": _decimal_to_american(vf_under_dec),
                }
            )

    return rows
