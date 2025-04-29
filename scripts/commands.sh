# Build
sam build --use-container

# Local invoke
sam local invoke

# Deploy
sam deploy --config-env stage

# Deploy & change samconfig
sam deploy --stack-name pipeline-stage \
  --parameter-overrides Env=stage BucketName=tradesecretsdata S3Prefix=scraper-dk RoleArn=arn:aws:iam::688035104276:role/lambda-stage \
  --config-env stage --guided

sam deploy --stack-name pipeline-prod \
  --parameter-overrides Env=prod BucketName=tradesecretsdata S3Prefix=scraper-dk RoleArn=arn:aws:iam::688035104276:role/lambda-prod \
  --config-env prod --guided

# Check out S3 bucket
aws s3 ls s3://tradesecretsdata/scraper-dk/stage/raw/ | tail
