This service is deployed as a lambda in AWS using a docker container (it was slightly larger to the 250 Mb size limit for the zip file). It's deployed using the aws sam cli. Some commands are in the makefile.

## AWS login

The scripts read `AWS_PROFILE` from `.env` and automatically run `aws sso login` if the session has expired. Set the profile in `.env`:

```
AWS_PROFILE=aidan3e4admin
```

## First-time setup

Secrets are stored in AWS Secrets Manager (`vibecast/openai`, `vibecast/novita`). On a new environment, create them from your `.env` file:

```
./setup-secrets.sh
```

This will trigger SSO login if needed, then create the secrets. It skips any secret that already exists, so it's safe to re-run.

## Deploying

```
./deploy.sh          # builds and deploys (prompts for changeset confirmation)
./deploy.sh --yes    # same, skips confirmation
```

Or via make:

```
make deploy
make deploy-yes
```

## Updating a secret

To rotate or update a secret value manually:

```
aws secretsmanager put-secret-value \
  --secret-id vibecast/openai \
  --secret-string '{"OPENAI_API_KEY":"sk-your-new-key-here"}' \
  --region eu-central-1
```

## Other settings

Bucket names and other non-secret config are passed through `samconfig.toml`.

The llm-inference package is installed from the main branch in github. To refresh it locally (and thus in the lambda since the lambda uses uv.lock) do a `make update-deps` in the lambda dir