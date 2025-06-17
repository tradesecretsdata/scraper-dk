import pytest

from pipeline import parse as parse_mod


def test_parse_main():
    """Merged row & vig-free odds without pandas."""
    responses = {
        "hits/total": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "John"}],
                    "points": 1.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "John"}],
                    "points": 1.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
            ]
        }
    }

    rows = parse_mod.parse_main(responses)

    assert len(rows) == 1
    row = rows[0]

    assert row["player"] == "John"
    assert row["category"] == "Hits"

    # vig-free should be +100 / 2.0 when both sides −110
    assert pytest.approx(row["vig_free_over_decimal_odds"], rel=1e-3) == 2.0
    assert row["vig_free_over_american_odds"] == 100
