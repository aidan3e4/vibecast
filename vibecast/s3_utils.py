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


_DATETIME_RE = re.compile(r"_(\d{14})\.\w+$")


def _parse_filename_datetime(key: str) -> datetime | None:
    """Extract datetime from a filename ending in _YYYYMMDDHHMMSS.ext."""
    match = _DATETIME_RE.search(key)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def find_images_in_bucket(
    bucket_suffix: str,
    timestamp: datetime,
    interval_seconds: int,
    num_images: int,
    delta_seconds: int = 300,
) -> list[str] | None:
    """Find images in a vibecast bucket by stepping back from a timestamp.

    Looks in s3://vibecast-{bucket_suffix}/ftp_uploads/YYYY/MM/DD/ for files
    whose embedded datetime (_YYYYMMDDHHMMSS) is closest to each target time,
    within delta_seconds tolerance.

    Args:
        bucket_suffix: Appended to "vibecast-" to form the bucket name.
        timestamp: Starting datetime; first image should be closest to this.
        interval_seconds: How far back each subsequent slot steps.
        num_images: Maximum number of images to retrieve.
        delta_seconds: Maximum allowed difference (in seconds) between target
                       and actual image datetime.

    Returns:
        None if the first slot has no match within delta_seconds.
        Otherwise a list of S3 keys (may be shorter than num_images if a later
        slot has no match).
    """
    bucket = f"vibecast-{bucket_suffix}"
    results = []

    for i in range(num_images):
        target = timestamp - timedelta(seconds=i * interval_seconds)
        prefix = f"ftp_uploads/{target.strftime('%Y/%m/%d')}/"

        # List all objects under that day's prefix
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

        if not candidates:
            if i == 0:
                return None
            break

        candidates.sort(key=lambda x: x[0])
        results.append(candidates[0][1])

    return results
