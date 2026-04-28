"""S3 utilities for reading and writing images and results."""

import json
import re
from datetime import datetime, timedelta
from typing import Any

import boto3
import cv2
import numpy as np

s3_client = boto3.client("s3")


def download_image_from_s3(bucket: str, key: str) -> np.ndarray:
    """Download an image from S3 and return as numpy array (RGB)."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    image_bytes = response["Body"].read()

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"Failed to decode image from s3://{bucket}/{key}")

    # Convert BGR to RGB
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return img_rgb


def upload_image_to_s3(img_rgb: np.ndarray, bucket: str, key: str, quality: int = 90) -> str:
    """Upload a numpy array (RGB) as JPEG to S3. Returns the S3 URI."""
    # Convert RGB to BGR for OpenCV
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    # Encode to JPEG
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    success, encoded = cv2.imencode(".jpg", img_bgr, encode_params)
    if not success:
        raise ValueError("Failed to encode image to JPEG")

    # Upload to S3
    s3_client.put_object(Bucket=bucket, Key=key, Body=encoded.tobytes(), ContentType="image/jpeg")

    return f"s3://{bucket}/{key}"


def upload_json_to_s3(data: dict[str, Any], bucket: str, key: str) -> str:
    """Upload a JSON object to S3. Returns the S3 URI."""
    json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")

    s3_client.put_object(Bucket=bucket, Key=key, Body=json_bytes, ContentType="application/json")

    return f"s3://{bucket}/{key}"


def append_json_to_s3(entry: dict[str, Any], bucket: str, key: str) -> str:
    """Append an entry to a JSON list stored at key in S3.

    If the file doesn't exist, creates it as a single-element list.
    If the file exists and contains a dict (legacy), converts it to a list first.
    Returns the S3 URI.
    """
    existing: list[dict] = []
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        if isinstance(data, list):
            existing = data
        else:
            existing = [data]
    except s3_client.exceptions.NoSuchKey:
        pass
    except Exception:
        pass

    existing.append(entry)
    json_bytes = json.dumps(existing, indent=2, default=str).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=key, Body=json_bytes, ContentType="application/json")
    return f"s3://{bucket}/{key}"


def generate_output_prefix(input_key: str, main_dir: str) -> str:
    """Generate an output prefix based on input key and timestamp.

    Example: input "images/camera1/2026-01-27/img001.jpg"
             output "processed/2026/01/27/img001_20260127_143052/"
    """
    # Extract filename without extension
    dir, filename = input_key.split("/", 1)
    name_without_ext = filename.rsplit(".", 1)[0]

    assembled_path = f"{main_dir}/{name_without_ext}"

    return assembled_path


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse an S3 URI into bucket and key.

    Example: "s3://my-bucket/path/to/file.jpg" -> ("my-bucket", "path/to/file.jpg")
    """
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")

    path = uri[5:]  # Remove "s3://"
    parts = path.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 URI: {uri}")

    return parts[0], parts[1]


_DATETIME_RE = re.compile(r"_(\d{14})(?:_|\.(jpg|jpeg|png))", re.IGNORECASE)


def _parse_filename_datetime(key: str) -> datetime | None:
    """Extract datetime from a filename ending in _YYYYMMDDHHMMSS.ext."""
    match = _DATETIME_RE.search(key)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None


_VALID_VIEWS = {"below", "north", "south", "east", "west"}


def _list_candidates(bucket: str, prefix: str, delta_seconds: int, target: datetime) -> list[tuple[float, str]]:
    """List S3 objects under prefix whose filename datetime is within delta_seconds of target."""
    paginator = s3_client.get_paginator("list_objects_v2")
    candidates = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            file_dt = _parse_filename_datetime(key)
            if file_dt is None:
                continue
            diff = abs((file_dt - target).total_seconds())
            if diff <= delta_seconds:
                candidates.append((diff, key))
    return candidates


async def find_images_in_bucket(
    bucket_suffix: str,
    timestamp: datetime,
    interval_seconds: int,
    num_images: int,
    view: str = "below",
    delta_seconds: int = 300,
) -> list[str] | None:
    """Find images in a vibecast bucket by stepping back from a timestamp.

    For each slot, first looks in unwarped/YYYY/MM/DD/ for a file matching
    *_{view}.jpg. If not found, falls back to ftp_uploads/YYYY/MM/DD/, triggers
    unwarping via process_image, then resolves the resulting unwarped key.

    Args:
        bucket_suffix: Appended to "vibecast-" to form the bucket name.
        timestamp: Starting datetime; first image should be closest to this.
        interval_seconds: Seconds between each slot stepping backward.
        num_images: Maximum number of images to retrieve.
        view: One of "below", "north", "south", "east", "west".
        delta_seconds: Maximum allowed difference (in seconds) between target
                       and actual image datetime.

    Returns:
        None if the first slot has no match within delta_seconds.
        Otherwise a list of S3 keys (may be shorter than num_images if a later
        slot has no match).
    """
    view = view.lower()
    if view not in _VALID_VIEWS:
        raise ValueError(f"Invalid view '{view}'. Must be one of: {sorted(_VALID_VIEWS)}")

    bucket = f"vibecast-{bucket_suffix}"
    results = []
    used_keys: set[str] = set()

    for i in range(num_images):
        target = timestamp - timedelta(seconds=i * interval_seconds)
        date_path = target.strftime("%Y/%m/%d")

        # 1. Find the closest unused image in ftp_uploads/YYYY/MM/DD/
        ftp_prefix = f"ftp_uploads/{date_path}/"
        ftp_candidates = [
            (diff, key)
            for diff, key in _list_candidates(bucket, ftp_prefix, delta_seconds, target)
            if key not in used_keys
        ]

        if not ftp_candidates:
            if i == 0:
                return None
            break

        ftp_candidates.sort(key=lambda x: x[0])
        ftp_key = ftp_candidates[0][1]
        ftp_dt = _parse_filename_datetime(ftp_key)

        # 2. Check if the corresponding unwarped view already exists
        unwarped_prefix = f"unwarped/{date_path}/"
        unwarped_candidates = [
            (diff, key)
            for diff, key in _list_candidates(bucket, unwarped_prefix, delta_seconds, ftp_dt or target)
            if key.endswith(f"_{view}.jpg") and key not in used_keys
        ]
        unwarped_candidates.sort(key=lambda x: x[0])
        # Only accept an unwarped file if it matches the exact same datetime as the ftp file
        unwarped_key = None
        if unwarped_candidates and ftp_dt is not None:
            best_diff, best_key = unwarped_candidates[0]
            if best_diff == 0:
                unwarped_key = best_key

        if unwarped_key is None:
            # 3. Unwarp the fisheye image
            from vibecast.processor import process_image_async

            await process_image_async(
                input_s3_uri=f"s3://{bucket}/{ftp_key}",
                unwarp=True,
                output_bucket=bucket,
                results_bucket=bucket,
            )

            # 4. Look for the freshly unwarped view
            unwarped_candidates = [
                (diff, key)
                for diff, key in _list_candidates(bucket, unwarped_prefix, delta_seconds, ftp_dt or target)
                if key.endswith(f"_{view}.jpg") and key not in used_keys
            ]
            unwarped_candidates.sort(key=lambda x: x[0])

            if not unwarped_candidates:
                if i == 0:
                    return None
                break

            unwarped_key = unwarped_candidates[0][1]

        used_keys.add(ftp_key)
        used_keys.add(unwarped_key)
        results.append(unwarped_key)

    return results
