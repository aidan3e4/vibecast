#!/usr/bin/env bash
# Deploy vibecast to AWS Lambda via SAM.
# Assumes secrets are already set up in AWS Secrets Manager (run setup-secrets.sh first).
# Usage: ./deploy.sh [--yes]   (--yes skips the changeset confirmation prompt)

set -euo pipefail

CONFIRM_FLAG=""
ENV_FILE=".env"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)      CONFIRM_FLAG="--no-confirm-changeset"; shift ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# --- AWS login ---
if [[ -f "$ENV_FILE" ]]; then
  AWS_PROFILE_NAME="$(grep -E '^AWS_PROFILE\s*=' "$ENV_FILE" | head -1 | sed 's/^AWS_PROFILE\s*=\s*//' | tr -d '"'"'")"
  if [[ -n "$AWS_PROFILE_NAME" ]]; then
    export AWS_PROFILE="$AWS_PROFILE_NAME"
    echo "Using AWS profile: $AWS_PROFILE_NAME"
    if ! aws sts get-caller-identity &>/dev/null; then
      echo "Session expired or not logged in — running aws sso login..."
      aws sso login --profile "$AWS_PROFILE_NAME"
    fi
  fi

  DOCKER_HOST_VAL="$(grep -E '^DOCKER_HOST\s*=' "$ENV_FILE" | head -1 | sed 's/^DOCKER_HOST\s*=\s*//' | tr -d '"'"'")"
  if [[ -n "$DOCKER_HOST_VAL" ]]; then
    export DOCKER_HOST="$DOCKER_HOST_VAL"
    echo "Using DOCKER_HOST: $DOCKER_HOST_VAL"
  fi
fi

echo "Building..."
sam build

echo ""
echo "Deploying..."
sam deploy --resolve-image-repos $CONFIRM_FLAG

echo ""
echo "Deploy complete."
