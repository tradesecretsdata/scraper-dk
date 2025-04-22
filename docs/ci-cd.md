# CI/CD Pipeline

![CI/CD diagram](../assets/cicd.png)

## GitHub Actions Workflows

### `.github/workflows/test.yml`
Runs lint + unit tests on every PR.

### `.github/workflows/deploy.yml`

```yaml
name: deploy
on:
  push:
    branches: [main]
jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements-dev.txt
      - run: pytest -q
  deploy-stage:
    needs: build-and-test
    environment: stage
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<AWS_ACCOUNT_ID>:role/GitHubStageDeploy
          aws-region: <AWS_REGION>
      - run: sam build
      - run: sam deploy --config-env stage --no-confirm-changeset --no-fail-on-empty-changeset
  promote-prod:
    needs: deploy-stage
    if: ${{ success() }}
    environment: prod
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<AWS_ACCOUNT_ID>:role/GitHubProdDeploy
          aws-region: <AWS_REGION>
      - run: sam deploy --config-env prod --no-confirm-changeset --no-fail-on-empty-changeset
```

## Manual Promotion
`gh workflow run deploy.yml -f ref=main -f environment=prod`

## Security Notes
* GitHub → AWS uses OIDC roles, no long‑lived secrets.
* Stage role limited to S3 prefix `stage/*`; prod role to `prod/*`