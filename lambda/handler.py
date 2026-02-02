"""AWS Lambda handler for fisheye image processing."""

import json
import logging
import traceback
from typing import Any

from processor import process_image

from vision_llm import (
    create_prompt_line,
    get_prompt,
    get_prompt_names,
    list_models,
    list_prompts,
    push_prompt,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for processing fisheye images.

    Event schema:
    {
        "input_s3_uri": "s3://bucket/path/to/image.jpg",    # Required
        "unwarp": true,                                      # Perform fisheye unwarping
        "analyze": true,                                     # Perform LLM analysis
        "views_to_analyze": ["N", "S", "E", "W", "B"],      # Which views to analyze (unwarp mode only)
        "prompt": "Custom analysis prompt...",              # Optional
        "model": "gpt-4o",                                  # Optional, OpenAI model
        "output_bucket": "custom-output-bucket",            # Optional, override default
        "results_bucket": "custom-results-bucket",          # Optional, override default
        "fov": 90,                                          # Optional, field of view (unwarp mode)
        "view_angle": 45                                    # Optional, elevation angle (unwarp mode)
    }

    Use cases:
    1. Unwarp only: unwarp=true, analyze=false
       - Input: fisheye image
       - Output: 5 unwarped perspective views (N, S, E, W, Below)

    2. Analyze only: unwarp=false, analyze=true
       - Input: already unwarped image
       - Output: LLM analysis of the image

    3. Unwarp + Analyze: unwarp=true, analyze=true
       - Input: fisheye image
       - Output: 5 unwarped views + LLM analysis of specified views

    Returns:
    {
        "statusCode": 200,
        "body": {
            "input_uri": "s3://...",
            "unwarped_images": {...},        # Only if unwarp=true
            "analysis_results": {...},       # Only if analyze=true
            "results_uri": "s3://...",
            "processed_at": "2026-01-27T14:30:52Z"
        }
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # Route to models_handler if this is a GET /models request
    if event.get("rawPath") == "/models" or event.get("routeKey") == "GET /models":
        return models_handler(event, context)

    # Route to prompts handlers
    raw_path = event.get("rawPath", "")
    route_key = event.get("routeKey", "")

    if raw_path.startswith("/prompts") or "prompts" in route_key:
        return prompts_handler(event, context)

    try:
        # Parse event - handle both direct invocation and API Gateway
        if "body" in event and isinstance(event["body"], str):
            # API Gateway v2 format - body is a JSON string
            params = json.loads(event["body"])
        else:
            # Direct Lambda invocation - parameters at top level
            params = event

        # Extract parameters from event
        input_s3_uri = params.get("input_s3_uri")
        if not input_s3_uri:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required parameter: input_s3_uri"})}

        unwarp = params.get("unwarp", False)
        analyze = params.get("analyze", False)

        # Validate: at least one operation must be specified
        if not unwarp and not analyze:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "At least one operation must be specified: unwarp=true or analyze=true"}),
            }

        views_to_analyze = params.get("views_to_analyze")
        prompt = params.get("prompt")
        model = params.get("model")
        output_bucket = params.get("output_bucket")
        results_bucket = params.get("results_bucket")
        fov = params.get("fov")
        view_angle = params.get("view_angle")

        # Process the image
        result = process_image(
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

        logger.info(f"Processing complete. Results: {result['results_uri']}")

        return {"statusCode": 200, "body": json.dumps(result)}

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    except Exception as e:
        logger.error(f"Processing error: {str(e)}\n{traceback.format_exc()}")
        return {"statusCode": 500, "body": json.dumps({"error": f"Internal error: {str(e)}"})}


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

    return {"statusCode": 200, "body": {"processed": len(results), "results": results}}


def models_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Return available models for the UI.

    Can be mapped to GET /models in API Gateway.

    Returns:
    {
        "statusCode": 200,
        "body": {
            "models": [
                {"id": "gpt-4o", "name": "GPT_4O", "description": "...", "tier": "standard"},
                ...
            ],
            "default": "gpt-4o"
        }
    }
    """
    from vision_llm import DEFAULT_MODEL

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "models": list_models(),
                "default": str(DEFAULT_MODEL),
            }
        ),
    }


def prompts_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle prompt versioning API requests.

    Endpoints:
        GET  /prompts              - List all prompts (names with latest versions)
        GET  /prompts?all=true     - List all prompts with all versions
        GET  /prompts/{name}       - Get latest version of a prompt
        GET  /prompts/{name}/{ver} - Get specific version of a prompt
        POST /prompts              - Create new prompt line or push new version

    POST body for creating new prompt line:
    {
        "name": "my_prompt",
        "content": "Analyze this image..."
    }

    POST body for pushing new version (name must already exist):
    {
        "name": "existing_prompt",
        "content": "Updated prompt content..."
    }
    """
    raw_path = event.get("rawPath", "")
    route_key = event.get("routeKey", "")
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "")

    # Determine HTTP method
    if "GET" in route_key:
        http_method = "GET"
    elif "POST" in route_key:
        http_method = "POST"

    # Parse path parameters
    path_parts = [p for p in raw_path.split("/") if p and p != "prompts"]
    query_params = event.get("queryStringParameters") or {}

    try:
        if http_method == "GET":
            if len(path_parts) == 0:
                # GET /prompts - list all prompt names (or all versions if ?all=true)
                if query_params.get("all") == "true":
                    return {"statusCode": 200, "body": json.dumps({"prompts": list_prompts()})}
                return {"statusCode": 200, "body": json.dumps({"prompts": get_prompt_names()})}

            elif len(path_parts) == 1:
                # GET /prompts/{name} - get latest version
                name = path_parts[0]
                content = get_prompt(name)
                return {"statusCode": 200, "body": json.dumps({"name": name, "content": content})}

            elif len(path_parts) == 2:
                # GET /prompts/{name}/{version}
                name = path_parts[0]
                version = int(path_parts[1])
                content = get_prompt(name, version)
                return {"statusCode": 200, "body": json.dumps({"name": name, "version": version, "content": content})}

        elif http_method == "POST":
            # Parse body
            if "body" in event and isinstance(event["body"], str):
                body = json.loads(event["body"])
            else:
                body = event.get("body", {})

            name = body.get("name")
            content = body.get("content")

            if not name or not content:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing required fields: name, content"})}

            # Try to push (if name exists) or create (if name doesn't exist)
            try:
                result = push_prompt(name, content)
                return {"statusCode": 200, "body": json.dumps({"action": "pushed", **result})}
            except ValueError as e:
                if "doesn't exist" in str(e):
                    # Name doesn't exist, create new line
                    result = create_prompt_line(name, content)
                    return {"statusCode": 201, "body": json.dumps({"action": "created", **result})}
                raise

        return {"statusCode": 405, "body": json.dumps({"error": f"Method not allowed: {http_method}"})}

    except FileNotFoundError as e:
        return {"statusCode": 404, "body": json.dumps({"error": str(e)})}
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


# ============================================================================
# CLI - run this file directly to invoke the Lambda
# ============================================================================
if __name__ == "__main__":
    import argparse
    import os
    import sys

    # Fix imports when running as script
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    parser = argparse.ArgumentParser(
        description="Invoke vibecast image processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Unwarp fisheye image only (no analysis)
  python handler.py s3://bucket/fisheye.jpg --unwarp

  # Analyze an already unwarped image
  python handler.py s3://bucket/unwarped.jpg --analyze

  # Unwarp + analyze specific views
  python handler.py s3://bucket/fisheye.jpg --unwarp --analyze --views N S E

  # Unwarp + analyze all views
  python handler.py s3://bucket/fisheye.jpg --unwarp --analyze

  # Invoke deployed Lambda instead of running locally
  python handler.py s3://bucket/image.jpg --unwarp --analyze --remote
        """,
    )
    parser.add_argument(
        "input_s3_uri",
        help="S3 URI of the image",
    )
    parser.add_argument(
        "--unwarp",
        action="store_true",
        help="Unwarp fisheye image into 5 perspective views",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze image(s) with LLM",
    )
    parser.add_argument(
        "--views",
        nargs="+",
        help="Views to analyze (N, S, E, W, B) - only for unwarp+analyze mode",
    )
    parser.add_argument(
        "--prompt",
        help="Custom prompt for LLM analysis",
    )
    parser.add_argument(
        "--model",
        help="OpenAI model to use for analysis (default: gpt-4o)",
    )
    parser.add_argument(
        "--fov",
        type=int,
        help="Field of view in degrees (for unwarp)",
    )
    parser.add_argument(
        "--view-angle",
        type=int,
        help="Elevation angle for cardinal directions (for unwarp)",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Invoke deployed Lambda instead of running locally",
    )
    parser.add_argument(
        "--function-name",
        default="vibecast-process-image",
        help="Lambda function name (for --remote)",
    )

    args = parser.parse_args()

    # Validate: at least one operation must be specified
    if not args.unwarp and not args.analyze:
        parser.error("At least one operation must be specified: --unwarp or --analyze")

    event = {
        "input_s3_uri": args.input_s3_uri,
        "unwarp": args.unwarp,
        "analyze": args.analyze,
    }
    if args.views:
        event["views_to_analyze"] = args.views
    if args.prompt:
        event["prompt"] = args.prompt
    if args.model:
        event["model"] = args.model
    if args.fov:
        event["fov"] = args.fov
    if args.view_angle:
        event["view_angle"] = args.view_angle

    if args.remote:
        import boto3

        print(f"Invoking Lambda: {args.function_name}")
        client = boto3.client("lambda")
        response = client.invoke(
            FunctionName=args.function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )
        result = json.loads(response["Payload"].read())
    else:
        print(f"Running locally: {args.input_s3_uri}")
        result = lambda_handler(event, None)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("statusCode") == 200 else 1)
