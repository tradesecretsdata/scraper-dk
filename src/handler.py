import os, json, random, datetime, tempfile, pathlib, logging, botocore
import boto3, duckdb, pyarrow as pa, pyarrow.parquet as pq

s3 = boto3.client("s3")
log = logging.getLogger()
log.setLevel(logging.INFO)

BUCKET       = os.environ["BUCKET_NAME"]          # pass via template if you like
ENV          = os.environ["RAW_PREFIX"].split("/")[1]  # "stage" or "prod"
S3PREFIX     = os.environ["RAW_PREFIX"].split("/")[0]  # s3prefix
RAW_PREFIX   = os.environ["RAW_PREFIX"]           # s3prefix/stage/raw
PROC_PREFIX  = os.environ["PROC_PREFIX"]          # s3prefix/stage/processed
DB_URI       = os.environ["DB_URI"]               # s3://bucket/s3prefix/stage/db/scraper-dk.duckdb
LATEST_KEY   = f"{ENV}/latest.json"

def lambda_handler(event, context):
    print("Env variables:")
    print(f"Bucket: {BUCKET}")
    print(f"Env: {ENV}")
    print(f"Raw prefix: {RAW_PREFIX}")
    print(f"Proc prefix: {PROC_PREFIX}")
    print(f"Db uri: {DB_URI}")
    print(f"latest key: {LATEST_KEY}")

    ts = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    row = {
        "scraped_at": ts,
        "value1": round(random.random(), 5),
        "value2": random.randint(0, 100),
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
        s3.download_file(BUCKET, f"{S3PREFIX}/{ENV}/db/scraper-dk.duckdb", str(local_db))
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] != "404":
            raise
        log.warning("DB not found; creating new one")
    con = duckdb.connect(str(local_db))
    con.execute(
        "CREATE TABLE IF NOT EXISTS readings(scraped_at TIMESTAMP, value1 DOUBLE, value2 INTEGER);"
    )
    con.execute("INSERT INTO readings VALUES (?, ?, ?)",
                (ts, row["value1"], row["value2"]))
    con.execute("CHECKPOINT")
    con.close()
    s3.upload_file(str(local_db), BUCKET, f"{S3PREFIX}/{ENV}/db/scraper-dk.duckdb")
    log.info("Upserted DuckDB")

    # 4. ─ overwrite 'latest' flat file for the frontend
    s3.put_object(Bucket=BUCKET, Key=LATEST_KEY,
                  Body=json.dumps(row).encode(),
                  ContentType="application/json")

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
