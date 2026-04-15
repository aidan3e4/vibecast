#!/usr/bin/env bash
# First-time setup: create secrets in AWS Secrets Manager from .env.
# Run once before the first deploy.
# Usage: ./setup-secrets.sh [--env-file <path>] [--region <region>]

set -euo pipefail

ENV_FILE=".env"
REGION="eu-central-1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --region)   REGION="$2";   shift 2 ;;
    *) shift ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: env file '$ENV_FILE' not found." >&2
  exit 1
fi

# Parse key=value pairs, ignoring comments and blank lines
declare -A env_vars
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  value="${value#\"}" ; value="${value%\"}"
  value="${value#\'}" ; value="${value%\'}"
  key="${key%"${key##*[![:space:]]}"}"
  env_vars["$key"]="$value"
done < "$ENV_FILE"

# --- AWS login ---
AWS_PROFILE_NAME="${env_vars[AWS_PROFILE]:-}"
if [[ -n "$AWS_PROFILE_NAME" ]]; then
  export AWS_PROFILE="$AWS_PROFILE_NAME"
  echo "Using AWS profile: $AWS_PROFILE_NAME"
  # Login if the current session has no valid credentials
  if ! aws sts get-caller-identity &>/dev/null; then
    echo "Session expired or not logged in — running aws sso login..."
    aws sso login --profile "$AWS_PROFILE_NAME"
  fi
fi

create_secret() {
  local secret_id="$1"
  local json="$2"
  echo "  Creating $secret_id ..."
  if aws secretsmanager describe-secret --secret-id "$secret_id" --region "$REGION" &>/dev/null; then
    echo "    Already exists — skipping. To update, use put-secret-value manually (see DEPLOY.md)."
  else
    aws secretsmanager create-secret \
      --name "$secret_id" \
      --secret-string "$json" \
      --region "$REGION" \
      --output text --query 'Name' 2>&1 | sed 's/^/    /'
    echo "    Created."
  fi
}

echo "Reading secrets from: $ENV_FILE"
echo "AWS region: $REGION"
echo ""

if [[ -n "${env_vars[OPENAI_API_KEY]:-}" ]]; then
  create_secret "vibecast/openai" "{\"OPENAI_API_KEY\":\"${env_vars[OPENAI_API_KEY]}\"}"
else
  echo "  Skipping vibecast/openai (OPENAI_API_KEY not set)"
fi

if [[ -n "${env_vars[NOVITA_API_KEY]:-}" ]]; then
  create_secret "vibecast/novita" "{\"NOVITA_API_KEY\":\"${env_vars[NOVITA_API_KEY]}\"}"
else
  echo "  Skipping vibecast/novita (NOVITA_API_KEY not set)"
fi

echo ""
echo "Done. You can now run ./deploy.sh"
