# Environment Matrix

| Environment | S3 Prefix | Lambda Alias | EventBridge Rate | IAM Role | Notes |
|-------------|-----------|--------------|------------------|----------|-------|
| **Stage**   | `stage/`  | `stage`      | `rate(30 minutes)` | `lambda-stage` | Safe sandbox |
| **Prod**    | `prod/`   | `prod`       | `rate(5 minutes)`  | `lambda-prod`  | Customer‑facing |

> All resources live in a single AWS account `<AWS_ACCOUNT_ID>`, segmented by prefix & alias rather than separate accounts.
