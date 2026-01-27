"""AWS Lambda handler for fisheye image processing."""
import json
import logging
import traceback
from typing import Any

from .processor import process_image

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for processing fisheye images.

    Event schema:
    {
        "input_s3_uri": "s3://bucket/path/to/fisheye.jpg",  # Required
        "views_to_analyze": ["N", "S", "E", "W", "B"],      # Optional, which views to send to LLM
        "prompt": "Custom analysis prompt...",              # Optional
        "output_bucket": "custom-output-bucket",            # Optional, override default
        "results_bucket": "custom-results-bucket",          # Optional, override default
        "fov": 90,                                          # Optional, field of view
        "view_angle": 45                                    # Optional, elevation angle
    }

    Returns:
    {
        "statusCode": 200,
        "body": {
            "input_uri": "s3://...",
            "unwarped_images": {
                "North": "s3://output-bucket/processed/.../north.jpg",
                "South": "s3://output-bucket/processed/.../south.jpg",
                ...
            },
            "analysis_results": {
                "North": {"mood": "...", "number_of_people": 0, ...},
                ...
            },
            "results_uri": "s3://results-bucket/processed/.../results.json",
            "processed_at": "2026-01-27T14:30:52Z"
        }
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Extract parameters from event
        input_s3_uri = event.get("input_s3_uri")
        if not input_s3_uri:
            return {
                "statusCode": 400,
                "body": {"error": "Missing required parameter: input_s3_uri"}
            }

        views_to_analyze = event.get("views_to_analyze")
        prompt = event.get("prompt")
        output_bucket = event.get("output_bucket")
        results_bucket = event.get("results_bucket")
        fov = event.get("fov")
        view_angle = event.get("view_angle")

        # Process the image
        result = process_image(
            input_s3_uri=input_s3_uri,
            views_to_analyze=views_to_analyze,
            prompt=prompt,
            output_bucket=output_bucket,
            results_bucket=results_bucket,
            fov=fov,
            view_angle=view_angle,
        )

        logger.info(f"Processing complete. Results: {result['results_uri']}")

        return {
            "statusCode": 200,
            "body": result
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return {
            "statusCode": 400,
            "body": {"error": str(e)}
        }

    except Exception as e:
        logger.error(f"Processing error: {str(e)}\n{traceback.format_exc()}")
        return {
            "statusCode": 500,
            "body": {"error": f"Internal error: {str(e)}"}
        }


def s3_trigger_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handler for S3 event triggers (when new image is uploaded).

    This handler is triggered when a new image is uploaded to the input bucket.
    It extracts the S3 URI from the event and calls the main handler.

    To use: configure S3 bucket notifications to trigger this Lambda.
    """
    logger.info(f"S3 trigger event: {json.dumps(event)}")

    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        input_s3_uri = f"s3://{bucket}/{key}"

        # Create a standard event and process
        standard_event = {
            "input_s3_uri": input_s3_uri,
            # Add default views to analyze if desired
            # "views_to_analyze": ["N", "S", "E", "W"],
        }

        result = lambda_handler(standard_event, context)
        results.append(result)

    return {
        "statusCode": 200,
        "body": {"processed": len(results), "results": results}
    }
