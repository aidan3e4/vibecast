"""Image processing logic - unwarp fisheye and analyze with LLM."""
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to import vision_llm
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config, _get_openai_key
from s3_utils import (
    download_image_from_s3,
    generate_output_prefix,
    parse_s3_uri,
    upload_image_to_s3,
    upload_json_to_s3,
)

from vision_llm import analyze_with_openai, get_room_views, image_to_base64


def unwarp_fisheye_image(
    img_rgb,
    fov: int = None,
    view_angle: int = None,
) -> dict[str, Any]:
    """Unwarp a fisheye image into 5 perspective views.

    Args:
        img_rgb: Numpy array (RGB) of the fisheye image
        fov: Field of view in degrees
        view_angle: Elevation angle for cardinal directions

    Returns:
        Dict mapping direction name to numpy array (RGB)
    """
    fov = fov or Config.DEFAULT_FOV
    view_angle = view_angle or Config.DEFAULT_VIEW_ANGLE

    views = get_room_views(
        img_rgb,
        fov=fov,
        output_size=Config.DEFAULT_OUTPUT_SIZE,
        view_angle=view_angle,
        below_fraction=Config.DEFAULT_BELOW_FRACTION,
    )

    return views


def process_image(
    input_s3_uri: str,
    views_to_analyze: list[str] = None,
    prompt: str = None,
    output_bucket: str = None,
    results_bucket: str = None,
    fov: int = None,
    view_angle: int = None,
) -> dict[str, Any]:
    """Full processing pipeline for a fisheye image.

    Args:
        input_s3_uri: S3 URI of the input fisheye image (e.g., "s3://bucket/key")
        views_to_analyze: List of views to analyze with LLM (e.g., ["North", "South"])
                         Use shortcuts: "N", "S", "E", "W", "B"
                         If None, no LLM analysis is performed
        prompt: Custom prompt for LLM analysis
        output_bucket: Bucket for unwarped images (defaults to config)
        results_bucket: Bucket for analysis results (defaults to config)
        fov: Field of view in degrees
        view_angle: Elevation angle for cardinal directions

    Returns:
        Dict containing:
        - input_uri: Original input S3 URI
        - unwarped_images: Dict mapping direction to S3 URI of unwarped image
        - analysis_results: Dict mapping direction to LLM analysis (if requested)
        - results_uri: S3 URI of the full results JSON
        - processed_at: ISO timestamp
    """
    output_bucket = output_bucket or Config.OUTPUT_BUCKET
    results_bucket = results_bucket or Config.RESULTS_BUCKET
    prompt = prompt or Config.DEFAULT_PROMPT

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Normalize view names
    if views_to_analyze:
        views_to_analyze = [
            Config.VIEW_SHORTCUTS.get(v.upper(), v) for v in views_to_analyze
        ]
        # Validate views
        invalid = set(views_to_analyze) - set(Config.VALID_VIEWS)
        if invalid:
            raise ValueError(f"Invalid views: {invalid}. Valid: {Config.VALID_VIEWS}")

    # Parse input URI
    input_bucket, input_key = parse_s3_uri(input_s3_uri)

    # Download fisheye image
    fisheye_img = download_image_from_s3(input_bucket, input_key)

    # Generate output prefix
    output_unwarp_prefix = generate_output_prefix(input_key, "unwarped")
    output_results_prefix = generate_output_prefix(input_key, "results")

    # Unwarp to 5 perspective views
    views = unwarp_fisheye_image(fisheye_img, fov=fov, view_angle=view_angle)

    # Upload unwarped images to S3
    unwarped_uris = {}
    for direction, img in views.items():
        key = f"{output_unwarp_prefix}_{direction.lower()}.jpg"
        uri = upload_image_to_s3(img, output_bucket, key)
        unwarped_uris[direction] = uri

    # Analyze selected views with LLM
    analysis_results = {}
    if views_to_analyze:
        for direction in views_to_analyze:
            if direction in views:
                img_base64 = image_to_base64(views[direction])
                result = analyze_with_openai(
                    img_base64,
                    prompt,
                    _get_openai_key(),
                )
                analysis_results[direction] = result

    # Build final results
    processed_at = datetime.utcnow().isoformat() + "Z"
    results = {
        "input_uri": input_s3_uri,
        "unwarped_images": unwarped_uris,
        "analysis_results": analysis_results,
        "processed_at": processed_at,
        "config": {
            "fov": fov or Config.DEFAULT_FOV,
            "view_angle": view_angle or Config.DEFAULT_VIEW_ANGLE,
            "views_analyzed": views_to_analyze or [],
            "prompt": prompt if views_to_analyze else None,
        },
    }

    # Upload results JSON
    results_key = f"{output_results_prefix}_results_{timestamp}.json"
    results_uri = upload_json_to_s3(results, results_bucket, results_key)
    results["results_uri"] = results_uri

    return results
