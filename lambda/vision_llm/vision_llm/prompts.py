"""Prompt versioning management.

Prompts are stored in S3 with the naming convention:
    prompts/prompt_{name}_{version}.txt

Examples:
    prompts/prompt_default_0.txt  - name="default", version=0
    prompts/prompt_dan_2.txt      - name="dan", version=2

For local development or when S3 is not configured, falls back to
local filesystem in the prompts/ directory.
"""

import os
import re
from pathlib import Path

# Local fallback directory (bundled with deployment)
LOCAL_PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_PATTERN = re.compile(r"^prompt_(.+)_(\d+)\.txt$")
S3_PROMPTS_PREFIX = "prompts/"


def _get_s3_client():
    """Get boto3 S3 client (lazy import to avoid issues in local dev)."""
    import boto3
    return boto3.client("s3")


def _get_prompts_bucket() -> str | None:
    """Get the S3 bucket for prompts storage."""
    return os.environ.get("PROMPTS_BUCKET") or os.environ.get("RESULTS_BUCKET")


def _list_s3_prompts() -> dict[str, list[int]]:
    """List all prompts from S3.

    Returns:
        Dict mapping prompt name to list of versions
    """
    bucket = _get_prompts_bucket()
    if not bucket:
        return {}

    prompts = {}
    try:
        s3 = _get_s3_client()
        paginator = s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=bucket, Prefix=S3_PROMPTS_PREFIX):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                filename = key.split("/")[-1]
                match = PROMPT_PATTERN.match(filename)
                if match:
                    name = match.group(1)
                    version = int(match.group(2))
                    if name not in prompts:
                        prompts[name] = []
                    prompts[name].append(version)
    except Exception:
        pass

    return prompts


def _list_local_prompts() -> dict[str, list[int]]:
    """List all prompts from local filesystem.

    Returns:
        Dict mapping prompt name to list of versions
    """
    prompts = {}

    if not LOCAL_PROMPTS_DIR.exists():
        return prompts

    for file in LOCAL_PROMPTS_DIR.glob("prompt_*_*.txt"):
        match = PROMPT_PATTERN.match(file.name)
        if match:
            name = match.group(1)
            version = int(match.group(2))
            if name not in prompts:
                prompts[name] = []
            prompts[name].append(version)

    return prompts


def _merge_prompts(s3_prompts: dict, local_prompts: dict) -> dict[str, list[int]]:
    """Merge S3 and local prompts, with S3 taking precedence."""
    merged = dict(local_prompts)
    for name, versions in s3_prompts.items():
        if name in merged:
            # Merge versions, removing duplicates
            merged[name] = sorted(set(merged[name] + versions))
        else:
            merged[name] = versions
    return merged


def list_prompts() -> list[dict]:
    """List all available prompts with their names and versions.

    Returns:
        List of dicts with keys: name, version, latest (bool), source (s3|local)
    """
    s3_prompts = _list_s3_prompts()
    local_prompts = _list_local_prompts()

    result = []

    # Process S3 prompts
    for name, versions in sorted(s3_prompts.items()):
        versions.sort()
        max_version = max(versions)
        for v in versions:
            result.append({
                "name": name,
                "version": v,
                "latest": v == max_version,
                "source": "s3",
            })

    # Add local prompts that aren't in S3
    for name, versions in sorted(local_prompts.items()):
        if name in s3_prompts:
            continue  # Skip, already added from S3
        versions.sort()
        max_version = max(versions)
        for v in versions:
            result.append({
                "name": name,
                "version": v,
                "latest": v == max_version,
                "source": "local",
            })

    return result


def get_prompt_names() -> list[dict]:
    """Get all prompt names with their latest version.

    Returns:
        List of dicts with keys: name, latest_version, version_count
    """
    s3_prompts = _list_s3_prompts()
    local_prompts = _list_local_prompts()
    merged = _merge_prompts(s3_prompts, local_prompts)

    result = []
    for name, versions in sorted(merged.items()):
        result.append({
            "name": name,
            "latest_version": max(versions),
            "version_count": len(versions),
        })

    return result


def get_prompt(name: str, version: int = None) -> str:
    """Get a prompt by name and optional version.

    Checks S3 first, then falls back to local filesystem.

    Args:
        name: Prompt name (e.g., "default", "dan")
        version: Specific version number. If None, returns latest version.

    Returns:
        Prompt content as string

    Raises:
        FileNotFoundError: If prompt doesn't exist
    """
    s3_prompts = _list_s3_prompts()
    local_prompts = _list_local_prompts()
    merged = _merge_prompts(s3_prompts, local_prompts)

    if name not in merged:
        raise FileNotFoundError(f"No prompts found with name: {name}")

    if version is None:
        version = max(merged[name])

    if version not in merged[name]:
        raise FileNotFoundError(f"Prompt not found: {name} v{version}")

    # Try S3 first
    if name in s3_prompts and version in s3_prompts[name]:
        bucket = _get_prompts_bucket()
        s3 = _get_s3_client()
        key = f"{S3_PROMPTS_PREFIX}prompt_{name}_{version}.txt"
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    # Fall back to local
    file_path = LOCAL_PROMPTS_DIR / f"prompt_{name}_{version}.txt"
    if file_path.exists():
        return file_path.read_text()

    raise FileNotFoundError(f"Prompt not found: {name} v{version}")


def create_prompt_line(name: str, content: str) -> dict:
    """Create a new prompt line (new name at version 0).

    Stores the prompt in S3.

    Args:
        name: New prompt name (must not already exist)
        content: Prompt content

    Returns:
        Dict with keys: name, version, s3_uri

    Raises:
        ValueError: If prompt name already exists or name is invalid
    """
    # Validate name (alphanumeric and underscores only)
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", name):
        raise ValueError(
            f"Invalid prompt name: {name}. "
            "Must start with letter and contain only alphanumeric characters and underscores."
        )

    # Check if name already exists (in S3 or local)
    s3_prompts = _list_s3_prompts()
    local_prompts = _list_local_prompts()

    if name in s3_prompts or name in local_prompts:
        raise ValueError(f"Prompt name '{name}' already exists. Use push_prompt to add a new version.")

    bucket = _get_prompts_bucket()
    if not bucket:
        raise ValueError("No prompts bucket configured. Set PROMPTS_BUCKET or RESULTS_BUCKET environment variable.")

    key = f"{S3_PROMPTS_PREFIX}prompt_{name}_0.txt"
    s3 = _get_s3_client()
    s3.put_object(Bucket=bucket, Key=key, Body=content.encode("utf-8"))

    return {
        "name": name,
        "version": 0,
        "s3_uri": f"s3://{bucket}/{key}",
    }


def push_prompt(name: str, content: str) -> dict:
    """Push a new version of an existing prompt.

    Automatically increments the version number. Stores in S3.

    Args:
        name: Existing prompt name
        content: New prompt content

    Returns:
        Dict with keys: name, version, previous_version, s3_uri

    Raises:
        ValueError: If prompt name doesn't exist
    """
    s3_prompts = _list_s3_prompts()
    local_prompts = _list_local_prompts()
    merged = _merge_prompts(s3_prompts, local_prompts)

    if name not in merged:
        raise ValueError(
            f"Prompt name '{name}' doesn't exist. Use create_prompt_line to create a new prompt."
        )

    previous_version = max(merged[name])
    new_version = previous_version + 1

    bucket = _get_prompts_bucket()
    if not bucket:
        raise ValueError("No prompts bucket configured. Set PROMPTS_BUCKET or RESULTS_BUCKET environment variable.")

    key = f"{S3_PROMPTS_PREFIX}prompt_{name}_{new_version}.txt"
    s3 = _get_s3_client()
    s3.put_object(Bucket=bucket, Key=key, Body=content.encode("utf-8"))

    return {
        "name": name,
        "version": new_version,
        "previous_version": previous_version,
        "s3_uri": f"s3://{bucket}/{key}",
    }


def get_default_prompt() -> str:
    """Get the default prompt (latest version of 'default' prompt).

    Returns:
        Default prompt content
    """
    return get_prompt("default")
