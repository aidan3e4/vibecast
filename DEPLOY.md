This service is deployed as a lambda in AWS using a docker container (it was slightly larger to the 250 Mb size limit for the zip file). It's deployed using the aws sam cli. Some commands are in the makefile.

The secrets are stored in AWS secret manager (in aidan3e4 account). For example to change the OpenAI api key use
aws secretsmanager put-secret-value \
  --secret-id vibecast/openai \
  --secret-string '{"OPENAI_API_KEY":"sk-your-new-key-here"}' \
  --region eu-central-1
This requires AWS login, which can be done with sso by
- aws sso login --profile=PROFILE
- export AWS_PROFILE=PROFILE


Some other settings such as bucket names are passed through samconfig.toml.

The llm-inference package is installed from the main branch in github. To refresh it locally (and thus in the lambda since the lambda uses uv.lock) do a `make update-deps` in the lambda dir