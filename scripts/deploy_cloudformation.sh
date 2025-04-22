aws cloudformation deploy \
  --stack-name pipeline-roles \
  --template-file roles.yaml \
  --parameter-overrides \
      Repo=tradesecretsdata/scraper-dk \
      BucketName=tradesecretsdata \
      S3Prefix=scraper-dk \
  --capabilities CAPABILITY_NAMED_IAM

