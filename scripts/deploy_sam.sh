sam build --use-container
sam deploy --stack-name pipeline-stage \
  --parameter-overrides Env=stage BucketName=tradesecretsdata S3Prefix=scraper-dk RoleArn=arn:aws:iam::688035104276:role/lambda-stage \
  --config-env stage --guided

sam deploy --stack-name pipeline-prod \
  --parameter-overrides Env=prod BucketName=tradesecretsdata S3Prefix=scraper-dk RoleArn=arn:aws:iam::688035104276:role/lambda-prod \
  --config-env prod --guided
