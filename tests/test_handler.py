import csv
import importlib
from io import StringIO


def _fake_fetch():
    """Return a minimal Over/Under pair."""
    return {
        "hits/total": {
            "selections": [
                {
                    "label": "Over",
                    "participants": [{"name": "Jane"}],
                    "points": 1.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
                {
                    "label": "Under",
                    "participants": [{"name": "Jane"}],
                    "points": 1.5,
                    "displayOdds": {"american": "-110", "decimal": 1.91},
                },
            ]
        }
    }


def test_lambda_handler(monkeypatch):
    """Handler end-to-end with S3 uploads mocked (no pandas)."""
    # environment
    monkeypatch.setenv("BUCKET_NAME", "unit-bucket")
    monkeypatch.setenv("S3_PREFIX", "raw")
    monkeypatch.setenv("PROC_PREFIX", "processed")
    monkeypatch.setenv("ENV", "test")

    # stub fetch_main
    import pipeline.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod, "fetch_main", _fake_fetch, raising=True)

    # capture uploads
    raw_keys, csv_keys, csv_bodies = [], [], []

    def fake_upload_json(data, key, bucket=None):  # noqa: D401
        raw_keys.append(key)

    def fake_upload_csv(text, key, bucket=None):  # noqa: D401
        csv_keys.append(key)
        csv_bodies.append(text)

    import utils.s3_utils as s3_mod

    monkeypatch.setattr(s3_mod, "upload_json", fake_upload_json, raising=True)
    monkeypatch.setattr(s3_mod, "upload_csv", fake_upload_csv, raising=True)

    # run handler
    handler = importlib.import_module("handler")
    out = handler.lambda_handler({}, {})  # type: ignore[arg-type]

    assert out["status"] == "ok" and out["rows"] == 1
    assert len(raw_keys) == 1
    assert len(csv_keys) == 1

    # check CSV content
    buf = StringIO(csv_bodies[0])
    reader = csv.DictReader(buf)
    rows = list(reader)
    assert len(rows) == 1 and rows[0]["player"] == "Jane"
