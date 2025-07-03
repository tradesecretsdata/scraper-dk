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
