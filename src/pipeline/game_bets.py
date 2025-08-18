"""Extract and post-process *Game Lines / Game* betting data.

This module implements **Step 17–18** of *agent.md*:

17. Extract game betting data
18. Calculate vig-free prices + win probability

Public helpers
--------------
extract_game_rows(payloads) -> list[dict]
    Return one row per *team* with raw + vig-free betting columns.

build_game_index(rows) -> dict[str, dict]
    Convenience mapper ``team_abbr`` → *row* for join on combined table.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from .parse import (
    _american_to_prob,  # type: ignore
    _decimal_to_american,  # type: ignore
    _normalize_american,  # type: ignore
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _vig_free_two_sided(
    price1: int | None, price2: int | None
) -> Tuple[int | None, int | None]:
    """Return vig-free American odds for a *two-sided* market.

    Parameters
    ----------
    price1, price2
        Quoted American prices for each side. Either may be ``None`` – the
        function returns ``(None, None)`` in that case.
    """
    if price1 is None or price2 is None:
        return None, None

    p1, p2 = _american_to_prob(price1), _american_to_prob(price2)
    if p1 is None or p2 is None or p1 <= 0 or p2 <= 0:
        return None, None

    vig = p1 + p2
    if vig <= 0:
        return None, None

    p1_vf, p2_vf = p1 / vig, p2 / vig
    dec1, dec2 = 1.0 / p1_vf, 1.0 / p2_vf
    return _decimal_to_american(dec1), _decimal_to_american(dec2)


# ---------------------------------------------------------------------------
# Public extraction logic (Step 17/18)
# ---------------------------------------------------------------------------


def extract_game_rows(payloads: Mapping[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse *Game Lines / Game* payload into one-row-per-team structure.

    Returns an **empty list** if no ``game_lines/game`` payload is present.
    """
    games_payload = payloads.get("game_lines/game")
    if not games_payload:
        return []

    events = {evt["id"]: evt for evt in games_payload.get("events", [])}

    # Index markets → eventId → id by *name*
    market_map: dict[str, dict[str, str]] = {}
    for m in games_payload.get("markets", []):
        name = m.get("name")
        if name not in {"Moneyline", "Run Line", "Total"}:
            continue
        market_map.setdefault(name, {})[m["eventId"]] = m["id"]

    # Bucket selections by marketId for faster lookup
    sel_by_market: dict[str, list[dict[str, Any]]] = {}
    for sel in games_payload.get("selections", []):
        sel_by_market.setdefault(sel["marketId"], []).append(sel)

    rows: list[dict[str, Any]] = []

    for event_id, evt in events.items():
        parts = {p["venueRole"].lower(): p for p in evt.get("participants", [])}
        if "home" not in parts or "away" not in parts:
            continue  # skip malformed events

        money_id = market_map.get("Moneyline", {}).get(event_id)
        run_id = market_map.get("Run Line", {}).get(event_id)
        total_id = market_map.get("Total", {}).get(event_id)

        # Total runs (same for both teams) – grab the O/U *points* value
        total_pts = None
        if total_id and total_id in sel_by_market:
            for sel in sel_by_market[total_id]:
                if sel.get("outcomeType") == "Over":
                    total_pts = sel.get("points")
                    break

        # Gather quoted odds for both sides ------------------------------
        def _find_price(
            participant_id: str, market_id: str | None
        ) -> Tuple[int | None, float | None]:
            if not market_id or market_id not in sel_by_market:
                return None, None
            for s in sel_by_market[market_id]:
                # selections list *participants* list – match first id
                p0 = s.get("participants", [{}])[0]
                if p0.get("id") == participant_id:
                    american = _normalize_american(s["displayOdds"]["american"])
                    points_val = s.get("points")
                    return american, points_val
            return None, None

        home_price_ml, _ = _find_price(parts["home"]["id"], money_id)
        away_price_ml, _ = _find_price(parts["away"]["id"], money_id)
        vf_home_ml, vf_away_ml = _vig_free_two_sided(home_price_ml, away_price_ml)

        home_spread_price, home_spread_amt = _find_price(parts["home"]["id"], run_id)
        away_spread_price, away_spread_amt = _find_price(parts["away"]["id"], run_id)
        vf_home_spread, vf_away_spread = _vig_free_two_sided(
            home_spread_price, away_spread_price
        )

        # Construct rows for HOME and AWAY --------------------------------
        def _build_row(side_key: str) -> Dict[str, Any]:
            part = parts[side_key]
            opp_part = parts["away" if side_key == "home" else "home"]

            is_home = side_key == "home"
            money_q = home_price_ml if is_home else away_price_ml
            vf_money = vf_home_ml if is_home else vf_away_ml

            pct_win = _american_to_prob(vf_money) if vf_money is not None else None

            # ──────────────────────────────────────────────────────────
            # Compute team / opponent run totals via Pythagorean expectation
            #   P(win) = R^z / (R^z + O^z) with z = 1.83
            #   R + O = total_pts
            #   Solve for R (team runs). Opp runs = total_pts - R.
            # ──────────────────────────────────────────────────────────
            team_total = opp_total = None
            if pct_win is not None and total_pts not in (None, 0):
                try:
                    z = 1.83
                    ratio = (pct_win / (1.0 - pct_win)) ** (1.0 / z)
                    team_total = total_pts * ratio / (1.0 + ratio)
                    opp_total = total_pts / (1.0 + ratio)
                except (ZeroDivisionError, ValueError):
                    team_total = opp_total = None

            return {
                "event_id": event_id,
                "team": part.get("name"),
                "team_abbr": part.get("metadata", {}).get("shortName"),
                "opp": opp_part.get("name"),
                "opp_abbr": opp_part.get("metadata", {}).get("shortName"),
                "side": "Home" if is_home else "Away",
                # quoted lines
                "moneyline": money_q,
                # derived columns
                "vig_free_moneyline": vf_money,
                "pct_win": pct_win,
                "team_total": team_total,
                "opp_total": opp_total,
            }

        rows.append(_build_row("home"))
        rows.append(_build_row("away"))

    return rows


# ---------------------------------------------------------------------------
# Join helper (Step 19)
# ---------------------------------------------------------------------------


def build_game_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return mapping ``team_abbr`` → *row* for quick lookup during joins."""
    return {str(r.get("team_abbr")): r for r in rows if r.get("team_abbr")}


__all__ = [
    "extract_game_rows",
    "build_game_index",
]
