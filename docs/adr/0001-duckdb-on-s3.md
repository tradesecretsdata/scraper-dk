# ADR 0001: Store DuckDB database on S3

*Status: Accepted — <YYYY‑MM‑DD>*

## Context

We need historical SQL querying without provisioning a database server. DuckDB 1.1 supports reading a `.duckdb` file directly from S3 (write via download → mutate → upload pattern).

## Decision

- Keep a **single** DuckDB file per environment (`stage/db/mydata.duckdb`, `prod/db/mydata.duckdb`).
- Writers (Lambda) download‑and‑re‑upload on every run.
- Readers attach the S3 URI read‑only.

## Consequences

### Positive

- $0 database hosting cost; we pay only S3 storage + PUT/GET.
- Same SQL engine locally and in prod.

### Negative

- Single‑writer pattern; must guard against concurrent writers.
- Download/upload adds latency (≈ 100–300 ms with <50 MB DB).

## Alternatives Considered

| Option | Notes |
|--------|-------|
| Aurora Serverless v2 | \$~0.20/day base cost, more IAM/infra overhead |
| DynamoDB + Athena | No native SQL joins, two storage layers |