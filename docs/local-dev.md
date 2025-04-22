# Local Development Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12.x | use `pyenv` or `asdf` |
| AWS SAM CLI | ≥ 1.115 | `brew install aws-sam-cli` |
| Docker | latest | for `sam local` emulation |

## Environment Variables

Create `.env` in repo root:

```dotenv
AWS_REGION=<YOUR_AWS_REGION>
S3_BUCKET=<YOUR_S3_BUCKET>
RAW_PREFIX=stage/raw
PROC_PREFIX=stage/processed
DB_URI=s3://<YOUR_S3_BUCKET>/stage/db/mydata.duckdb
API_URL=<EXTERNAL_API_ENDPOINT>
```

Load it in shells: export $(cat .env | xargs)

## Typical Workflow
```bash
# 1  Run formatter + tests on save (requires entr)
find src tests -name '*.py' | entr -c make dev

# 2  Invoke Lambda with local event
sam local invoke ScraperFunction --event events/sample_event.json

# 3  Start API Gateway/lambda locally (rare)
sam local start-api
```

## Debugging Tips
* Add print()s; they appear in sam local invoke output.
* sam logs -n ScraperFunction --stack-name <STACK_NAME> --tail streams CloudWatch logs.