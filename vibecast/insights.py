"""Insights - higher-level analysis functions built on top of vibecast primitives."""

import asyncio
import json
from datetime import datetime

from vibecast.llm import analyze_image
from vibecast.prompts import get_prompt
from vibecast.s3_utils import (
    _parse_filename_datetime,
    append_json_to_s3,
    download_image_from_s3,
    find_images_in_bucket,
    s3_client,
)
from vibecast.utils import image_to_base64

_CACHE_DELTA_SECONDS = 300


def _load_insights_cache(bucket: str, date: datetime) -> dict[str, dict]:
    """Load all existing crowd JSON files for a given day from S3.

    Returns a dict mapping S3 key -> parsed JSON content, for all
    insights/YYYY/MM/DD/crowd_*.json objects on that date.
    """
    prefix = f"insights/{date.strftime('%Y/%m/%d')}/crowd_"
    cache = {}
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                try:
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    data = json.loads(response["Body"].read().decode("utf-8"))
                    entries = data if isinstance(data, list) else [data]
                    for idx, entry in enumerate(entries):
                        cache[f"{key}#{idx}"] = entry
                except Exception:
                    pass
    except Exception:
        pass
    return cache


def _find_cache_hit(
    image_dt: datetime,
    model_id: str,
    prompt: str,
    cache: dict[str, dict],
    claimed: set[str],
) -> tuple[str | None, dict | None]:
    """Return the closest cached result within _CACHE_DELTA_SECONDS, if unclaimed
    and matching model and prompt."""
    best_key = None
    best_diff = None

    for s3_key, data in cache.items():
        if s3_key in claimed:
            continue
        if data.get("model") != model_id:
            continue
        if data.get("prompt") != prompt:
            continue
        cached_dt_str = data.get("image_datetime")
        if not cached_dt_str:
            continue
        try:
            cached_dt = datetime.fromisoformat(cached_dt_str)
        except ValueError:
            continue
        diff = abs((cached_dt - image_dt).total_seconds())
        if diff <= _CACHE_DELTA_SECONDS and (best_diff is None or diff < best_diff):
            best_key = s3_key
            best_diff = diff

    if best_key is not None:
        return best_key, cache[best_key]
    return None, None


async def get_crowd(
    bucket_suffix: str,
    timestamp: datetime,
    interval_seconds: int,
    num_images: int,
    model_id: str,
    view: str = "below",
) -> list[dict]:
    """Retrieve images, analyze each for crowd info, and save results to S3.

    Fetches up to num_images images stepping back from timestamp by
    interval_seconds, analyzes each with the latest Crowd prompt, and saves
    the results JSON to:
        s3://vibecast-{bucket_suffix}/insights/YYYY/MM/DD/crowd_{datetime}.json

    Args:
        bucket_suffix: Appended to "vibecast-" to form the bucket name.
        timestamp: Starting datetime for image retrieval.
        interval_seconds: Seconds between each image slot stepping backward.
        num_images: Maximum number of images to retrieve and analyze.
        model_id: Vision LLM model identifier to use for analysis.
        view: Which unwarped view to analyze: "below", "north", "south", "east", "west".

    Returns:
        List of per-image result dicts, each containing:
        - bucket: the full bucket name
        - key: S3 key of the source image
        - image_datetime: ISO timestamp parsed from the filename
        - model: model_id used
        - analysis: LLM response (parsed JSON or raw string)
        - results_uri: S3 URI where that image's JSON was saved
    """
    bucket = f"vibecast-{bucket_suffix}"

    # Retrieve image keys
    image_keys = await find_images_in_bucket(
        bucket_suffix=bucket_suffix,
        timestamp=timestamp,
        interval_seconds=interval_seconds,
        num_images=num_images,
        view=view,
    )
    if image_keys is None:
        image_keys = []

    # Fetch the latest Crowd prompt
    prompt = get_prompt("Crowd")

    # Load existing insights cache for today's date (covers most common case)
    cache = _load_insights_cache(bucket, timestamp)
    claimed: set[str] = set()

    # Analyze each image and save a result per image
    image_results = []
    for key in image_keys:
        file_dt = _parse_filename_datetime(key)
        image_dt = file_dt if file_dt else timestamp

        # Check cache before calling the LLM
        cache_key, cached_result = _find_cache_hit(image_dt, model_id, prompt, cache, claimed)
        if cached_result is not None:
            claimed.add(cache_key)
            image_results.append(cached_result)
            continue

        img = download_image_from_s3(bucket, key)
        img_b64 = image_to_base64(img)
        analysis = await analyze_image(img_b64, prompt, model=model_id)

        result = {
            "bucket": bucket,
            "key": key,
            "image_datetime": image_dt.isoformat(),
            "model": model_id,
            "prompt": prompt,
            "analysis": analysis,
        }

        date_path = image_dt.strftime("%Y/%m/%d")
        dt_str = image_dt.strftime("%Y%m%d_%H%M%S")
        results_key = f"insights/{date_path}/crowd_{dt_str}.json"
        results_uri = append_json_to_s3(result, bucket, results_key)
        result["results_uri"] = results_uri

        image_results.append(result)

    return image_results


def get_crowd_sync(
    bucket_suffix: str,
    timestamp: datetime,
    interval_seconds: int,
    num_images: int,
    model_id: str,
    view: str = "below",
) -> list[dict]:
    """Sync wrapper for get_crowd."""
    return asyncio.run(
        get_crowd(
            bucket_suffix=bucket_suffix,
            timestamp=timestamp,
            interval_seconds=interval_seconds,
            num_images=num_images,
            model_id=model_id,
            view=view,
        )
    )
