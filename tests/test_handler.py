import os
import pathlib
import boto3
import sys
from moto import mock_aws
import pytest

# import the Lambda entrypoint
sys.path.append(str(pathlib.Path(__file__).parents[1] / "src"))
from handler import lambda_handler


@pytest.fixture
def s3_and_env(monkeypatch):
    """Create fake S3 + env vars that handler.py expects."""
    bucket = "unit-test-bucket"
    monkeypatch.setenv("BUCKET_NAME", bucket)
    monkeypatch.setenv("RAW_PREFIX", "scraper-dk/stage/raw")
    monkeypatch.setenv("PROC_PREFIX", "scraper-dk/stage/processed")
    monkeypatch.setenv("DB_URI", f"s3://{bucket}/scraper-dk/stage/db/scraper-dk.duckdb")

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=bucket)
        yield s3


def test_handler_writes_all_objects(s3_and_env):
    """Lambda should create raw JSON, Parquet, DB, and latest.json."""
    s3 = s3_and_env
    response = lambda_handler({}, {})

    assert response["statusCode"] == 200

    keys = {
        obj["Key"]
        for obj in s3.list_objects_v2(Bucket=os.environ["BUCKET_NAME"]).get(
            "Contents", []
        )
    }

    assert any(
        k.startswith("scraper-dk/stage/raw/") and k.endswith(".json") for k in keys
    )
    assert any(
        k.startswith("scraper-dk/stage/processed/") and k.endswith(".parquet")
        for k in keys
    )
    assert "scraper-dk/stage/db/scraper-dk.duckdb" in keys
    assert "scraper-dk/stage/latest.json" in keys
