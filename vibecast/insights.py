"""Insights - higher-level analysis functions built on top of vibecast primitives."""

import asyncio
import json
from datetime import datetime, timedelta

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
                        if isinstance(entry, dict):
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


async def _analyze_view(
    bucket: str,
    key: str,
    image_dt: datetime,
    view: str,
    model_id: str,
    prompt: str,
    cache: dict[str, dict],
    claimed: set[str],
) -> dict:
    """Analyze a single view image, using cache if available."""
    cache_key, cached_result = _find_cache_hit(image_dt, model_id, prompt, cache, claimed)
    if cached_result is not None and cached_result.get("view") == view:
        claimed.add(cache_key)
        return cached_result

    img = download_image_from_s3(bucket, key)
    img_b64 = image_to_base64(img)
    analysis = await analyze_image(img_b64, prompt, model=model_id)

    return {
        "bucket": bucket,
        "key": key,
        "view": view,
        "image_datetime": image_dt.isoformat(),
        "model": model_id,
        "prompt": prompt,
        "analysis": analysis,
    }


async def get_crowd(
    bucket_suffix: str,
    timestamp: datetime,
    interval_seconds: int,
    num_images: int,
    model_id: str,
    views: list[str] = None,
) -> dict[str, dict]:
    """Retrieve images for multiple views, analyze each for crowd info, and save results to S3.

    For each timestamp slot, fetches images for all requested views, analyzes them
    in parallel, and saves a single JSON file per slot containing all view results.

    Args:
        bucket_suffix: Appended to "vibecast-" to form the bucket name.
        timestamp: Starting datetime for image retrieval.
        interval_seconds: Seconds between each image slot stepping backward.
        num_images: Maximum number of slots to retrieve and analyze.
        model_id: Vision LLM model identifier to use for analysis.
        views: List of views to analyze: "below", "north", "south", "east", "west".
               Defaults to ["below"].

    Returns:
        Dict mapping image_datetime (ISO string) -> {
            "summary": None,
            "results": list of per-view result dicts, each containing:
                - bucket, key, view, image_datetime, model, analysis, results_uri
        }
    """
    if views is None:
        views = ["below"]

    bucket = f"vibecast-{bucket_suffix}"
    prompt = get_prompt("Crowd")
    cache = _load_insights_cache(bucket, timestamp)
    claimed: set[str] = set()

    # Fetch image keys for all views in parallel per slot
    view_keys_list = await asyncio.gather(*[
        find_images_in_bucket(
            bucket_suffix=bucket_suffix,
            timestamp=timestamp,
            interval_seconds=interval_seconds,
            num_images=num_images,
            view=view,
        )
        for view in views
    ])

    # Build per-slot structure: slot_index -> {view -> key}
    # Use the first view that has results to determine how many slots there are
    num_slots = max((len(keys) for keys in view_keys_list if keys), default=0)

    output: dict[str, dict] = {}

    for slot_idx in range(num_slots):
        # Collect (view, key) pairs available for this slot
        slot_view_keys = []
        for view, keys in zip(views, view_keys_list):
            if keys and slot_idx < len(keys):
                slot_view_keys.append((view, keys[slot_idx]))

        if not slot_view_keys:
            continue

        # Determine the slot datetime from the first available key
        first_key = slot_view_keys[0][1]
        file_dt = _parse_filename_datetime(first_key)
        image_dt = file_dt if file_dt else (timestamp - timedelta(seconds=slot_idx * interval_seconds))

        # Analyze all views for this slot in parallel
        view_results = await asyncio.gather(*[
            _analyze_view(bucket, key, image_dt, view, model_id, prompt, cache, claimed)
            for view, key in slot_view_keys
        ])

        # Save all view results for this slot into one JSON file
        date_path = image_dt.strftime("%Y/%m/%d")
        dt_str = image_dt.strftime("%Y%m%d_%H%M%S")
        results_key = f"insights/{date_path}/crowd_{dt_str}.json"

        results_with_uri = []
        for result in view_results:
            result = dict(result)
            result["results_uri"] = f"s3://{bucket}/{results_key}"
            results_with_uri.append(result)

        append_json_to_s3(results_with_uri, bucket, results_key)

        crowdedness_pairs = [
            (r["analysis"]["crowdedness_level"], r["analysis"]["crowdedness"])
            for r in results_with_uri
            if isinstance(r.get("analysis"), dict)
            and "crowdedness_level" in r["analysis"]
            and "crowdedness" in r["analysis"]
        ]
        if crowdedness_pairs:
            level, crowd = max(crowdedness_pairs, key=lambda x: x[0])
            summary = {"crowd_level": level, "crowd": crowd}
        else:
            summary = None

        output[image_dt.isoformat()] = {
            "summary": summary,
            "results": results_with_uri,
        }

    return output


def get_crowd_sync(
    bucket_suffix: str,
    timestamp: datetime,
    interval_seconds: int,
    num_images: int,
    model_id: str,
    views: list[str] = None,
) -> dict[str, dict]:
    """Sync wrapper for get_crowd."""
    return asyncio.run(
        get_crowd(
            bucket_suffix=bucket_suffix,
            timestamp=timestamp,
            interval_seconds=interval_seconds,
            num_images=num_images,
            model_id=model_id,
            views=views,
        )
    )
