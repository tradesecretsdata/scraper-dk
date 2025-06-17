"""Transform DraftKings API payloads into merged Over/Under rows
with proper *category* and *subcategory* names (no pandas needed)."""

from __future__ import annotations

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
    Convert raw endpoint payloads to list-of-dict rows containing:

    category     → top-level slug (e.g. ``pitcher_props``)
    subcategory  → readable slug with spaces (e.g. ``walks allowed ou``)
    plus merged Over / Under odds and their vig-free equivalents.
    """
    rows: list[dict[str, Any]] = []

    for ep_key, payload in payloads.items():
        if "selections" not in payload:
            continue

        try:
            category_slug, subcat_slug = ep_key.split("/", 1)
        except ValueError:
            continue  # malformed key

        category = category_slug  # already slug form
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
