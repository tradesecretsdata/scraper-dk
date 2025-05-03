#!/usr/bin/env bash
# scripts/commands.sh

########################################
# Formatting / Linting / Local Testing
########################################
# Format code & check
black src tests
black --check src tests

# Run unit tests
pytest

# Build and invoke
# NOTE: must use env-vars because it, unlike .env, has priority over template.yaml
# NOTE: optionally remove --use-container for faster (x86-64 instead of arm64) build
sam build --use-container --debug
sam local invoke ScraperFunction --env-vars env-dev.json

########################################
# Environment
########################################
source .env # Before running scripts

########################################
# Cloudformation
########################################
aws cloudformation deploy \
  --stack-name pipeline-roles \
  --template-file roles.yaml \
  --parameter-overrides \
      Repo=$BUCKET_NAME/$S3_PREFIX \
      BucketName=$BUCKET_NAME \
      S3Prefix=$S3_PREFIX \
  --capabilities CAPABILITY_NAMED_IAM

########################################
# SAM / Lambda
########################################
# Build
sam build --use-container

# Local invoke
sam local invoke

# Deploy
## Stage
sam deploy --config-env stage
### Deploy & change samconfig
sam deploy --stack-name pipeline-stage \
  --parameter-overrides \
    Env=stage \
    BucketName=$BUCKET_NAME \
    S3Prefix=$S3_PREFIX \
    RoleArn=arn:aws:iam::688035104276:role/lambda-stage \
  --config-env stage \
  --guided

## Prod
sam deploy --config-env prod
### Deploy & change samconfig
sam deploy --stack-name pipeline-prod \
  --parameter-overrides \
    Env=prod \
    BucketName=$BUCKET_NAME \
    S3Prefix=$S3_PREFIX \
    RoleArn=arn:aws:iam::688035104276:role/lambda-prod \
  --config-env prod \
  --guided

########################################
# Make sure stuff is working
########################################

# S3
## View latest raw data in s3 (stage)
aws s3 ls s3://$BUCKET_NAME/$S3_PREFIX/stage/raw/ | tail

# Duckdb
## Download latest duckdb file (stage)
aws s3 cp s3://$BUCKET_NAME/$S3_PREFIX/stage/db/$S3_PREFIX.duckdb .

## Show the 5 most recent rows in a single shot
duckdb $S3_PREFIX.duckdb -c \
  "SELECT * FROM readings ORDER BY scraped_at DESC LIMIT 5;"

## See min/max timestamps
duckdb $S3_PREFIX.duckdb -c \
  "SELECT MIN(scraped_at), MAX(scraped_at) FROM readings;"

