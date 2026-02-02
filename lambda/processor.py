"""Image processing logic - unwarp fisheye and analyze with LLM."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to import vision_llm
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from s3_utils import (
    download_image_from_s3,
    generate_output_prefix,
    parse_s3_uri,
    upload_image_to_s3,
    upload_json_to_s3,
)

from vision_llm import analyze_image, get_room_views, image_to_base64


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


async def process_image_async(
    input_s3_uri: str,
    unwarp: bool = False,
    analyze: bool = False,
    views_to_analyze: list[str] = None,
    prompt: str = None,
    model: str = None,
    output_bucket: str = None,
    results_bucket: str = None,
    fov: int = None,
    view_angle: int = None,
) -> dict[str, Any]:
    """Full processing pipeline for fisheye images.

    Args:
        input_s3_uri: S3 URI of the input image
        unwarp: If True, unwarp fisheye image into 5 perspective views
        analyze: If True, perform LLM analysis on the image(s)
        views_to_analyze: List of views to analyze (e.g., ["North", "South"])
                         Use shortcuts: "N", "S", "E", "W", "B"
                         Only used when unwarp=True and analyze=True
                         If None when both flags are set, all views are analyzed
        prompt: Custom prompt for LLM analysis
        model: LLM model to use for analysis (defaults to config)
        output_bucket: Bucket for unwarped images (defaults to config)
        results_bucket: Bucket for analysis results (defaults to config)
        fov: Field of view in degrees (for unwarping)
        view_angle: Elevation angle for cardinal directions (for unwarping)

    Returns:
        Dict containing:
        - input_uri: Original input S3 URI
        - unwarped_images: Dict mapping direction to S3 URI (only if unwarp=True)
        - analysis_results: Dict mapping view name to LLM analysis (only if analyze=True)
        - results_uri: S3 URI of the full results JSON
        - processed_at: ISO timestamp
    """
    output_bucket = output_bucket or Config.OUTPUT_BUCKET
    results_bucket = results_bucket or Config.RESULTS_BUCKET
    prompt = prompt or Config.DEFAULT_PROMPT
    model = model or Config.DEFAULT_MODEL

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Validate: at least one operation must be specified
    if not unwarp and not analyze:
        raise ValueError("At least one operation must be specified: unwarp=True or analyze=True")

    # Normalize and validate view names
    if views_to_analyze:
        views_to_analyze = [Config.VIEW_SHORTCUTS.get(v.upper(), v) for v in views_to_analyze]
        # Validate views
        invalid = set(views_to_analyze) - set(Config.VALID_VIEWS)
        if invalid:
            raise ValueError(f"Invalid views: {invalid}. Valid: {Config.VALID_VIEWS}")

    # Parse input URI
    input_bucket, input_key = parse_s3_uri(input_s3_uri)

    # Generate output prefix
    output_results_prefix = generate_output_prefix(input_key, "results")

    unwarped_uris = None
    analysis_results = {}

    # MODE 1: Unwarp only (no analysis)
    if unwarp and not analyze:
        fisheye_img = download_image_from_s3(input_bucket, input_key)
        output_unwarp_prefix = generate_output_prefix(input_key, "unwarped")

        # Unwarp to 5 perspective views
        views = unwarp_fisheye_image(fisheye_img, fov=fov, view_angle=view_angle)

        # Upload unwarped images to S3
        unwarped_uris = {}
        for direction, img in views.items():
            key = f"{output_unwarp_prefix}_{direction.lower()}.jpg"
            uri = upload_image_to_s3(img, output_bucket, key)
            unwarped_uris[direction] = uri

    # MODE 2: Analyze only (input is already unwarped)
    elif analyze and not unwarp:
        input_img = download_image_from_s3(input_bucket, input_key)

        # Analyze the single input image
        img_base64 = image_to_base64(input_img)
        result = await analyze_image(
            img_base64,
            prompt,
            model=model,
        )
        analysis_results["Image"] = result

    # MODE 3: Unwarp + Analyze
    elif unwarp and analyze:
        fisheye_img = download_image_from_s3(input_bucket, input_key)
        output_unwarp_prefix = generate_output_prefix(input_key, "unwarped")

        # Unwarp to 5 perspective views
        views = unwarp_fisheye_image(fisheye_img, fov=fov, view_angle=view_angle)

        # Upload unwarped images to S3
        unwarped_uris = {}
        for direction, img in views.items():
            key = f"{output_unwarp_prefix}_{direction.lower()}.jpg"
            uri = upload_image_to_s3(img, output_bucket, key)
            unwarped_uris[direction] = uri

        # Determine which views to analyze
        if views_to_analyze:
            # Analyze only specified views
            analyze_views = views_to_analyze
        else:
            # Analyze all views by default
            analyze_views = list(views.keys())

        # Analyze selected views with LLM
        for direction in analyze_views:
            if direction in views:
                img_base64 = image_to_base64(views[direction])
                result = await analyze_image(
                    img_base64,
                    prompt,
                    model=model,
                )
                analysis_results[direction] = result

    # Build final results
    processed_at = datetime.utcnow().isoformat() + "Z"
    results = {
        "input_uri": input_s3_uri,
        "processed_at": processed_at,
        "config": {
            "unwarp": unwarp,
            "analyze": analyze,
        },
    }

    # Include unwarped_images if unwarp was performed
    if unwarped_uris is not None:
        results["unwarped_images"] = unwarped_uris
        results["config"]["fov"] = fov or Config.DEFAULT_FOV
        results["config"]["view_angle"] = view_angle or Config.DEFAULT_VIEW_ANGLE

    # Include analysis_results if analysis was performed
    if analysis_results:
        results["analysis_results"] = analysis_results
        results["config"]["prompt"] = prompt
        results["config"]["model"] = model

    # Upload results JSON
    results_key = f"{output_results_prefix}_results_{timestamp}.json"
    results_uri = upload_json_to_s3(results, results_bucket, results_key)
    results["results_uri"] = results_uri

    return results


def process_image(
    input_s3_uri: str,
    unwarp: bool = False,
    analyze: bool = False,
    views_to_analyze: list[str] = None,
    prompt: str = None,
    model: str = None,
    output_bucket: str = None,
    results_bucket: str = None,
    fov: int = None,
    view_angle: int = None,
) -> dict[str, Any]:
    """Sync wrapper for process_image_async."""
    return asyncio.run(
        process_image_async(
            input_s3_uri=input_s3_uri,
            unwarp=unwarp,
            analyze=analyze,
            views_to_analyze=views_to_analyze,
            prompt=prompt,
            model=model,
            output_bucket=output_bucket,
            results_bucket=results_bucket,
            fov=fov,
            view_angle=view_angle,
        )
    )
