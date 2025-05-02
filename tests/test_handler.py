import os
import pathlib
import importlib
import boto3
import sys
from moto import mock_aws
import pytest

sys.path.append(str(pathlib.Path(__file__).parents[1] / "src"))


@pytest.fixture
def s3_env(monkeypatch):
    bucket = "tradesecretsdata"  # ← your real bucket
    monkeypatch.setenv("BUCKET_NAME", bucket)
    monkeypatch.setenv("RAW_PREFIX", "scraper-dk/unit-test/raw")
    monkeypatch.setenv("PROC_PREFIX", "scraper-dk/unit-test/processed")
    monkeypatch.setenv(
        "DB_URI", f"s3://{bucket}/scraper-dk/unit-test/db/scraper-dk.duckdb"
    )

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=bucket)
        yield s3


def test_handler_writes_objects(s3_env):
    # re-import handler *after* moto + env are set
    import handler

    importlib.reload(handler)

    resp = handler.lambda_handler({}, {})
    assert resp["statusCode"] == 200

    s3 = s3_env
    keys = {
        o["Key"]
        for o in s3.list_objects_v2(Bucket=os.environ["BUCKET_NAME"]).get(
            "Contents", []
        )
    }

    assert any(
        k.endswith(".json") and k.startswith("scraper-dk/unit-test/raw/") for k in keys
    )
    assert any(
        k.endswith(".parquet") and k.startswith("scraper-dk/unit-test/processed/")
        for k in keys
    )
    assert "scraper-dk/unit-test/db/scraper-dk.duckdb" in keys
    assert "scraper-dk/unit-test/latest.json" in keys
