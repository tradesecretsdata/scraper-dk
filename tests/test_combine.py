"""Unit tests for src/combine.py (Step 2)."""

from __future__ import annotations

import types

import pipeline.combine as combine_mod

# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


class _FakeS3Client(types.SimpleNamespace):  # noqa: D101
    def __init__(self, keys_to_csv: dict[str, str]):
        super().__init__()
        self._keys = list(keys_to_csv)
        self._csv = keys_to_csv

    # ---- list paginator ----
    class _FakePaginator:  # noqa: D101
        def __init__(self, keys):
            self._keys = keys

        def paginate(self, **_):  # noqa: D401
            yield {"Contents": [{"Key": k} for k in self._keys]}

    def get_paginator(self, _):  # noqa: D401
        return _FakeS3Client._FakePaginator(self._keys)

    # ---- downloads handled via utils.read_csv stub ----


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_load_draftable_rows(monkeypatch):
    """Should read all CSVs under the prefix and append slate_id."""
    # -- env vars ----------------------------------------------------------
    monkeypatch.setenv("BUCKET_NAME", "unit-bucket")

    prefix = "dk-contests/2024-01-01/mlb/"
    keys = [f"{prefix}123.csv", f"{prefix}456.csv"]

    # same tiny CSV for both keys
    csv_text = "name,position,salary\nAlice,P,8000\nBob,C,5000\n"
    keys_to_csv = {k: csv_text for k in keys}

    # -- stub boto3 client in combine module ------------------------------
    fake_s3 = _FakeS3Client(keys_to_csv)
    monkeypatch.setattr(combine_mod, "_S3", fake_s3, raising=True)

    # -- stub read_csv (imported directly in combine.py) -------------------

    def fake_read_csv(key, bucket=None):  # noqa: D401
        return keys_to_csv[key]

    monkeypatch.setattr(combine_mod, "read_csv", fake_read_csv, raising=True)

    # ---------------------------------------------------------------------
    rows = combine_mod.load_draftable_rows(date="2024-01-01", sport="mlb")

    assert len(rows) == 4  # 2 files × 2 rows each
    slate_ids = {r["slate_id"] for r in rows}
    assert slate_ids == {"123", "456"}

    # each row should preserve original CSV columns
    assert {r["name"] for r in rows} == {"Alice", "Bob"}
    assert {r["position"] for r in rows} == {"P", "C"}


# ---------------------------------------------------------------------------
# Merge test
# ---------------------------------------------------------------------------


def test_merge_rows():
    draft_rows = [
        {"name": "Alice", "position": "P", "salary": 8000, "slate_id": "1"},
        {"name": "Bob", "position": "C", "salary": 5000, "slate_id": "1"},
    ]

    player_rows = [
        {"player": "Alice", "doubles": 0.2},
        {"player": "Carl", "doubles": 0.3},  # not in draft rows
    ]

    merged = combine_mod.merge_rows(player_rows=player_rows, draft_rows=draft_rows)

    # Should include 3 rows (2 draft + 1 unmatched player)
    assert len(merged) == 3

    # Alice row merges
    alice = next(
        r for r in merged if r.get("name") == "Alice" or r.get("player") == "Alice"
    )
    assert alice["position"] == "P" and alice["doubles"] == 0.2

    # Carl row carried forward
    carl = next(r for r in merged if r.get("player") == "Carl")
    assert carl["doubles"] == 0.3 and "position" not in carl
