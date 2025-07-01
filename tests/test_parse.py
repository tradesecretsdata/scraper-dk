import pytest
from pipeline import parse as parse_mod


def test_parse_main():
    responses = {
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

    rows = parse_mod.parse_main(responses)
    assert len(rows) == 1
    row = rows[0]

    assert row["category"] == "pitcher_props"
    assert row["subcategory"] == "triples_ou"
    assert row["player"] == "John"
    assert pytest.approx(row["vig_free_over_decimal_odds"], rel=1e-3) == 2.0
    assert row["vig_free_over_american_odds"] == 100


def test_parse_home_runs_one_sided():
    responses = {
        "batter_props/home_runs": {
            "selections": [
                {
                    "label": "1+",
                    "participants": [{"name": "Slugger"}],
                    "points": None,  # raw points irrelevant for milestones
                    "displayOdds": {"american": "+290", "decimal": 3.9},
                },
                # 2+ HR and higher milestones should be ignored by parser
                {
                    "label": "2+",
                    "participants": [{"name": "Slugger"}],
                    "points": None,
                    "displayOdds": {"american": "+900", "decimal": 10.0},
                },
            ]
        }
    }

    rows = parse_mod.parse_main(responses)
    assert len(rows) == 1
    row = rows[0]

    assert row["subcategory"] == "home_runs"
    assert row["points"] == 0.5
    assert row["over_american_odds"] == 290
    # Under odds are not provided in one-sided market
    assert row["under_american_odds"] is None

    # Vig-free odds should be noticeably longer than the quoted price
    assert row["vig_free_over_american_odds"] > row["over_american_odds"]
    # Rough expected range (~+340)
    assert 330 <= row["vig_free_over_american_odds"] <= 360

    # Poisson mean should be > 0 for a non-zero HR probability
    assert row["poisson_mean"] and row["poisson_mean"] > 0


def test_pivot_includes_hit_by_pitch():
    # Minimal rows example for a batter prop to ensure player is included.
    responses = {
        "batter_props/singles": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "Batter"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "Batter"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
            ]
        }
    }

    detailed, pivot = parse_mod.parse_and_pivot(responses)
    assert len(pivot) == 1
    row = pivot[0]
    # Constant 0.04 assigned
    assert row["hit_by_pitch"] == pytest.approx(0.04)
