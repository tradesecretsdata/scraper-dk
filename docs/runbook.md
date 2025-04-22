# Operations Runbook

## 1. Dashboards & Alerts

| Metric | Alarm Condition | Action |
|--------|-----------------|--------|
| `Errors` (Lambda) | ≥ 1 in 15 min | Investigate logs, reopen failed event from DLQ |
| `ScrapeSuccess` (custom) | No datapoint in 10 min | Panic: pipeline stalled |

## 2. Common Procedures

### Re‑deploy with hotfix
```bash
git checkout hotfix
sam build && sam deploy --config-env prod
```

### Replay Mis-Parsed Day
```bash
aws s3 cp s3://<S3_BUCKET>/<RAW_PREFIX>/2025-04-20T*.json ./tmp/
python scripts/reprocess.py ./tmp/*.json --output-date 2025-04-20
```

### Rollback DuckDB Snapshot
1. Go to S3 console → object versions.
2. Restore previous version of `prod/db/mydata.duckdb`
3. Re‑run scraper once `(sam invoke ...)`

### Rotate Yearly Snapshot
```bash
duckdb prod.duckdb "COPY (SELECT * FROM readings WHERE scraped_at >= date_trunc('year', now())) TO 'current.duckdb' (FORMAT DUCKDB);"
aws s3 cp current.duckdb s3://<S3_BUCKET>/prod/db/mydata.duckdb
```

## 3. Playbook: High Error Rate
1. Check CloudWatch Logs → stack trace?
2. If API outage, silence alarm with SNS topic <SNS_TOPIC_ARN> (expires in 30 min).
3. Retry DLQ messages after root cause fixed.