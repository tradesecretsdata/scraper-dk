import os
import json
import random
import datetime
import tempfile
import pathlib
import logging
import botocore
import boto3
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

log = logging.getLogger()
log.setLevel(logging.INFO)


def load_env():
    """Read and parse env vars every invocation (cheap)."""
    BUCKET = os.environ["BUCKET_NAME"]
    RAW_PREFIX = os.environ["RAW_PREFIX"]  # e.g. scraper-dk/stage/raw
    PROC_PREFIX = os.environ["PROC_PREFIX"]
    DB_URI = os.environ["DB_URI"]

    # derive helpers
    parts = RAW_PREFIX.split("/")  # ["scraper-dk", "stage", "raw"]
    S3PREFIX, ENV = parts[0], parts[1]
    LATEST_KEY = f"{S3PREFIX}/{ENV}/latest.json"
    DB_KEY = f"{S3PREFIX}/{ENV}/db/scraper-dk.duckdb"
    return BUCKET, ENV, S3PREFIX, RAW_PREFIX, PROC_PREFIX, DB_URI, LATEST_KEY, DB_KEY


def lambda_handler(event, context):
    # Load env variables
    (BUCKET, ENV, S3PREFIX, RAW_PREFIX, PROC_PREFIX, DB_URI, LATEST_KEY, DB_KEY) = (
        load_env()
    )

    print("Env variables:")
    print(f"Bucket: {BUCKET}")
    print(f"Env: {ENV}")
    print(f"Raw prefix: {RAW_PREFIX}")
    print(f"Proc prefix: {PROC_PREFIX}")
    print(f"Db uri: {DB_URI}")
    print(f"latest key: {LATEST_KEY}")

    # S3 client
    s3 = boto3.client("s3")

    ts = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    row = {
        "scraped_at": ts,
        "value1": round(random.random(), 5),
        "value2": random.randint(0, 1000),
    }
    # 1. ─ raw JSON
    raw_key = f"{RAW_PREFIX}/{ts}.json"
    s3.put_object(Bucket=BUCKET, Key=raw_key, Body=json.dumps(row).encode())
    log.info("Wrote raw %s", raw_key)

    # 2. ─ transform → Arrow → Parquet
    tbl = pa.Table.from_pylist([row])
    tmp_pq = pathlib.Path(tempfile.gettempdir()) / "batch.parquet"
    pq.write_table(tbl, tmp_pq)
    proc_key = f"{PROC_PREFIX}/{ts}.parquet"
    s3.upload_file(str(tmp_pq), BUCKET, proc_key)
    log.info("Wrote parquet %s", proc_key)

    # 3. ─ update DuckDB (download → insert → upload)
    local_db = pathlib.Path(tempfile.gettempdir()) / "scraper-dk.duckdb"
    try:
        s3.download_file(BUCKET, DB_KEY, str(local_db))
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] != "404":
            raise
        log.warning("DB not found; creating new one")
    con = duckdb.connect(str(local_db))
    con.execute(
        "CREATE TABLE IF NOT EXISTS readings(scraped_at TIMESTAMP, value1 DOUBLE, value2 INTEGER);"
    )
    con.execute(
        "INSERT INTO readings VALUES (?, ?, ?)", (ts, row["value1"], row["value2"])
    )
    con.execute("CHECKPOINT")
    con.close()
    s3.upload_file(str(local_db), BUCKET, DB_KEY)
    log.info("Upserted DuckDB")

    # 4. ─ overwrite 'latest' flat file for the frontend
    s3.put_object(
        Bucket=BUCKET,
        Key=f"{LATEST_KEY}",
        Body=json.dumps(row).encode(),
        ContentType="application/json",
    )

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
