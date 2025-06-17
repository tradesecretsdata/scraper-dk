import pytest

from pipeline import parse as parse_mod


def test_parse_main():
    """Row has correct category & NEW subcategory column."""
    responses = {
        "batter/doubles": {
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

    assert row["category"] == "batter"
    assert row["subcategory"] == "doubles"
    assert row["player"] == "John"

    # vig-free should be +100 / 2.0 when both sides −110
    assert pytest.approx(row["vig_free_over_decimal_odds"], rel=1e-3) == 2.0
    assert row["vig_free_over_american_odds"] == 100
