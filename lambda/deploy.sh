#!/bin/bash
# Deploy the Lambda function using AWS SAM
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - AWS SAM CLI installed (pip install aws-sam-cli)
#
# Usage:
#   ./deploy.sh                    # Deploy with defaults
#   ./deploy.sh --guided           # Interactive deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Copy vision_llm module into lambda directory for packaging
echo "Copying vision_llm module..."
cp -r ../vision_llm ./vision_llm

# Build the Lambda package
echo "Building Lambda package..."
sam build

# Deploy
if [[ "$1" == "--guided" ]]; then
    echo "Starting guided deployment..."
    sam deploy --guided
else
    echo "Deploying with samconfig.toml (run with --guided first time)..."
    sam deploy
fi

# Cleanup
echo "Cleaning up..."
rm -rf ./vision_llm

echo "Deployment complete!"
