# scraper-dk

Lightweight serverless data pipeline — API → JSON → Parquet → DuckDB → flat file — built with **Python 3.12** and **AWS SAM**.

![Architecture diagram](docs/architecture.svg)

## Features

- Fully serverless (Lambda + EventBridge + S3)
- Historical analytics in DuckDB stored on S3
- Two‑step CI/CD (stage ➜ prod) via GitHub Actions & SAM
- Local dev ≈ live prod using `sam local` and sample data

## Quick Start

```bash
# 1  Clone & install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2  Run unit tests against sample.duckdb
pytest -q

# 3  Invoke the scraper locally
sam local invoke ScraperFunction --event events/sample_event.json

# 4  Deploy to stage
sam build && sam deploy --config-env stage --guided
```