"""Configuration for the Lambda function."""
import json
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _get_secret(secret_name: str, region: str = None) -> dict:
    """Fetch secret from AWS Secrets Manager (cached)."""
    import boto3
    from botocore.exceptions import ClientError

    region = region or os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret_string = response.get("SecretString", "{}")
        return json.loads(secret_string)
    except ClientError:
        return {}


def _get_openai_key() -> str:
    """Get OpenAI API key from env var or Secrets Manager."""
    # First check env var (for local dev or direct injection)
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key

    # Fall back to Secrets Manager
    secret_name = os.environ.get("OPENAI_SECRET_NAME", "")
    if secret_name:
        secrets = _get_secret(secret_name)
        return secrets.get("OPENAI_API_KEY", "")

    return ""


class Config:
    # S3 Buckets
    INPUT_BUCKET = os.environ["INPUT_BUCKET"]
    OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
    RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]

    # Processing defaults
    DEFAULT_FOV = int(os.environ.get("DEFAULT_FOV", "90"))
    DEFAULT_VIEW_ANGLE = int(os.environ.get("DEFAULT_VIEW_ANGLE", "45"))
    DEFAULT_OUTPUT_SIZE = (1080, 810)
    DEFAULT_BELOW_SIZE = (1080, 1080)
    DEFAULT_BELOW_FRACTION = 0.6

    # LLM - fetched lazily to support Secrets Manager
    @property
    def openai_api_key(self) -> str:
        return _get_openai_key()

    # Class-level access (backwards compatible)
    OPENAI_API_KEY = property(lambda self: _get_openai_key())

    DEFAULT_PROMPT = """Analyze this image. Describe what you see. Respond in the following JSON format

```JSON
{
    "mood": str,
    "number_of_people": int,
    "description": str
}
```"""

    # Valid view directions
    VALID_VIEWS = ["North", "South", "East", "West", "Below"]
    VIEW_SHORTCUTS = {"N": "North", "S": "South", "E": "East", "W": "West", "B": "Below"}
