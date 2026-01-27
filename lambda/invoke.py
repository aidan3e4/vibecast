#!/usr/bin/env python3
"""CLI to invoke the Lambda function directly.

Usage:
    # Invoke deployed Lambda
    python invoke.py s3://my-bucket/path/to/image.jpg
    python invoke.py s3://my-bucket/image.jpg --views N S E
    python invoke.py s3://my-bucket/image.jpg --views N --prompt "Count people"

    # Local mode (no Lambda, runs processing directly)
    python invoke.py s3://my-bucket/image.jpg --local
"""
import argparse
import json
import os
import sys

import boto3


def invoke_lambda(
    input_s3_uri: str,
    views: list[str] = None,
    prompt: str = None,
    function_name: str = "vibecast-process-image",
) -> dict:
    """Invoke the Lambda function and return the result."""
    lambda_client = boto3.client("lambda")

    payload = {"input_s3_uri": input_s3_uri}
    if views:
        payload["views_to_analyze"] = views
    if prompt:
        payload["prompt"] = prompt

    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )

    result = json.loads(response["Payload"].read())
    return result


def invoke_local(
    input_s3_uri: str,
    views: list[str] = None,
    prompt: str = None,
) -> dict:
    """Run processing locally without Lambda."""
    # Add paths for local imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from lambda.handler import lambda_handler

    event = {"input_s3_uri": input_s3_uri}
    if views:
        event["views_to_analyze"] = views
    if prompt:
        event["prompt"] = prompt

    return lambda_handler(event, None)


def main():
    parser = argparse.ArgumentParser(
        description="Invoke vibecast image processing Lambda"
    )
    parser.add_argument(
        "input_s3_uri",
        help="S3 URI of the fisheye image (e.g., s3://bucket/path/image.jpg)",
    )
    parser.add_argument(
        "--views",
        nargs="+",
        choices=["N", "S", "E", "W", "B", "North", "South", "East", "West", "Below"],
        help="Views to analyze with LLM (default: none, just unwarp)",
    )
    parser.add_argument(
        "--prompt",
        help="Custom prompt for LLM analysis",
    )
    parser.add_argument(
        "--function-name",
        default="vibecast-process-image",
        help="Lambda function name (default: vibecast-process-image)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run locally instead of invoking Lambda",
    )

    args = parser.parse_args()

    if args.local:
        print(f"Processing locally: {args.input_s3_uri}")
        result = invoke_local(args.input_s3_uri, args.views, args.prompt)
    else:
        print(f"Invoking Lambda: {args.function_name}")
        result = invoke_lambda(
            args.input_s3_uri, args.views, args.prompt, args.function_name
        )

    print(json.dumps(result, indent=2))

    if result.get("statusCode") != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
