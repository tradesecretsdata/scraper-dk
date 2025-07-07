import pytest
from pipeline.projections import compute_fpts


def test_compute_batter_fpts_basic():
    row = {
        "player": "Test",
        "singles": 1.0,
        "doubles": 0.5,
        "triples": 0.1,
        "home_runs": 0.05,
        "rbis": 0.8,
        "runs": 0.9,
        "walks_batter_ou": 0.7,
        "hit_by_pitch": 0.04,
        "stolen_bases": 0.2,
    }

    # Attach role before computing general fantasy points
    row["role"] = "Batter"
    res = compute_fpts([row])[0]

    expected = (
        1.0 * 3
        + 0.5 * 5
        + 0.1 * 8
        + 0.05 * 10
        + 0.8 * 2
        + 0.9 * 2
        + 0.7 * 2
        + 0.04 * 2
        + 0.2 * 5
    )

    assert pytest.approx(res["fpts"], rel=1e-9) == expected

    # pts/$ when dk_salary present (multiplied by 1000)
    row_with_salary = dict(row, dk_salary=5000)
    res2 = compute_fpts([row_with_salary])[0]
    assert pytest.approx(res2["pts/$"], rel=1e-9) == expected / 5000 * 1000


# ----------------------------------------------------------------------
# New – pitcher fantasy point projection (Step 22)
# ----------------------------------------------------------------------


def test_compute_pitcher_fpts_basic():
    row = {
        "player": "Ace",
        "outs_recorded": 15,  # 5.0 IP
        "strikeouts_thrown": 6,
        "earned_runs_allowed": 2,
        "hits_allowed": 5,
        "walks_allowed": 2,
        "dk_salary": 9000,
    }

    # Assign pitcher role before computing
    row["role"] = "Pitcher"

    res = compute_fpts([row])[0]

    # Manual expected calculation
    innings_pitched = 15 / 3
    hit_batsman = 0.42 * innings_pitched / 9

    expected = (
        innings_pitched * 2.25
        + row["strikeouts_thrown"] * 2
        + row["earned_runs_allowed"] * -2
        + row["hits_allowed"] * -0.6
        + row["walks_allowed"] * -0.6
        + hit_batsman * -0.6
    )

    assert pytest.approx(res["fpts"], rel=1e-9) == expected

    expected_pts_per = expected / 9000 * 1000
    assert pytest.approx(res["pts/$"], rel=1e-9) == expected_pts_per

    # Ensure hit_by_pitch is blank for pitchers (Step 23 fix)
    assert res["hit_by_pitch"] in ("", None)
