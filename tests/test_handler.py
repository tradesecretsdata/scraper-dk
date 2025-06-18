import csv
import importlib
from io import StringIO


# ---------------------------------------------------------------------------
# Fixtures / stubs
# ---------------------------------------------------------------------------
def _fake_fetch():
    """Return two markets for the SAME player to test pivot logic."""
    return {
        # pitcher prop
        "pitcher_props/triples_ou": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "Jane"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "Jane"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
            ]
        },
        # batter prop for same player
        "batter_props/doubles": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "Jane"}],
                    "points": 0.5,
                    "displayOdds": {"american": "+120", "decimal": 2.20},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "Jane"}],
                    "points": 0.5,
                    "displayOdds": {"american": "-140", "decimal": 1.71},
                },
            ]
        },
    }


def test_lambda_handler(monkeypatch):
    """Handler should upload one bets CSV and one players CSV."""
    # -- env vars ----------------------------------------------------------
    monkeypatch.setenv("BUCKET_NAME", "unit-bucket")
    monkeypatch.setenv("S3_PREFIX", "raw")
    monkeypatch.setenv("PROC_PREFIX", "processed")
    monkeypatch.setenv("ENV", "test")

    # -- stub fetch_main ---------------------------------------------------
    import pipeline.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod, "fetch_main", _fake_fetch, raising=True)

    # -- capture uploads ---------------------------------------------------
    raw_keys, csv_keys, csv_bodies = [], [], []

    def fake_upload_json(data, key, bucket=None):  # noqa: D401
        raw_keys.append(key)

    def fake_upload_csv(text, key, bucket=None):  # noqa: D401
        csv_keys.append(key)
        csv_bodies.append((key, text))

    import utils.s3_utils as s3_mod

    monkeypatch.setattr(s3_mod, "upload_json", fake_upload_json, raising=True)
    monkeypatch.setattr(s3_mod, "upload_csv", fake_upload_csv, raising=True)

    # -- run handler -------------------------------------------------------
    handler = importlib.import_module("handler")
    result = handler.lambda_handler({}, {})  # type: ignore[arg-type]

    # -- result assertions -------------------------------------------------
    assert result["status"] == "ok"
    assert result["bets_rows"] == 2  # two detailed rows
    assert result["players_rows"] == 1  # one player pivot row

    # -- S3 key assertions -------------------------------------------------
    assert len(raw_keys) == 2  # raw JSON uploads (2 endpoints)
    assert len(csv_keys) == 2  # two CSV uploads
    assert any("/bets/" in k for k in csv_keys)
    assert any("/players/" in k for k in csv_keys)

    # -- content assertions ------------------------------------------------
    bets_csv = next(text for key, text in csv_bodies if "/bets/" in key)
    players_csv = next(text for key, text in csv_bodies if "/players/" in key)

    # bets table: 2 rows, columns include subcategory
    bets_rows = list(csv.DictReader(StringIO(bets_csv)))
    assert len(bets_rows) == 2
    assert {r["subcategory"] for r in bets_rows} == {"triples_ou", "doubles"}

    # players table: 1 row, columns for each subcategory
    players_rows = list(csv.DictReader(StringIO(players_csv)))
    assert len(players_rows) == 1
    row = players_rows[0]
    assert row["player"] == "Jane"
    assert "triples_ou" in row and "doubles" in row
