"""Configuration for the Lambda function."""

import json
import os
from functools import lru_cache

from vibecast import get_default_prompt
from vibecast.models import DEFAULT_MODEL, Provider, get_provider_for_model


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


def _get_api_key(env_var: str, secret_key: str, secret_name_env: str = None) -> str:
    """Get API key from env var or Secrets Manager."""
    # First check env var (for local dev or direct injection)
    key = os.environ.get(env_var, "")
    if key:
        return key

    # Fall back to Secrets Manager
    secret_name_env = secret_name_env or f"{env_var.replace('_API_KEY', '')}_SECRET_NAME"
    secret_name = os.environ.get(secret_name_env, "")
    if secret_name:
        secrets = _get_secret(secret_name)
        return secrets.get(secret_key, "")

    return ""


def _get_openai_key() -> str:
    """Get OpenAI API key from env var or Secrets Manager."""
    return _get_api_key("OPENAI_API_KEY", "OPENAI_API_KEY", "OPENAI_SECRET_NAME")


def _get_anthropic_key() -> str:
    """Get Anthropic API key from env var or Secrets Manager."""
    return _get_api_key("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_SECRET_NAME")


def _get_google_key() -> str:
    """Get Google API key from env var or Secrets Manager."""
    return _get_api_key("GOOGLE_API_KEY", "GOOGLE_API_KEY", "GOOGLE_SECRET_NAME")


def _get_novita_key() -> str:
    """Get Novita API key from env var or Secrets Manager."""
    return _get_api_key("NOVITA_API_KEY", "NOVITA_API_KEY", "NOVITA_SECRET_NAME")


def get_api_key_for_model(model_id: str) -> str:
    """Get the appropriate API key for a given model."""
    provider = get_provider_for_model(model_id)
    if provider == Provider.OPENAI:
        return _get_openai_key()
    elif provider == Provider.ANTHROPIC:
        return _get_anthropic_key()
    elif provider == Provider.GOOGLE:
        return _get_google_key()
    elif provider == Provider.NOVITA:
        return _get_novita_key()
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
    DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL") or DEFAULT_MODEL

    @property
    def openai_api_key(self) -> str:
        return _get_openai_key()

    # Class-level access (backwards compatible)
    OPENAI_API_KEY = property(lambda self: _get_openai_key())

    @staticmethod
    def get_api_key_for_model(model_id: str) -> str:
        """Get the appropriate API key for a model."""
        return get_api_key_for_model(model_id)

    # Load default prompt from versioned prompts directory
    try:
        DEFAULT_PROMPT = get_default_prompt()
    except FileNotFoundError:
        # Fallback if prompts directory not available
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
