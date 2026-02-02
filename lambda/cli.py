#!/usr/bin/env python3
"""CLI for invoking the deployed Lambda remotely."""

import argparse
import json
import sys

import boto3


def main():
    parser = argparse.ArgumentParser(
        description="Invoke deployed vibecast Lambda",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py s3://vibecast-ftp/path/image.jpg
  python cli.py s3://bucket/image.jpg --views N S E
        """,
    )
    parser.add_argument(
        "input_s3_uri",
        help="S3 URI of the fisheye image",
    )
    parser.add_argument(
        "--views",
        nargs="+",
        help="Views to analyze with LLM (N, S, E, W, B)",
    )
    parser.add_argument(
        "--prompt",
        help="Custom prompt for LLM analysis",
    )
    parser.add_argument(
        "--function-name",
        default="vibecast-process-image",
        help="Lambda function name",
    )

    args = parser.parse_args()

    event = {"input_s3_uri": args.input_s3_uri}
    if args.views:
        event["views_to_analyze"] = args.views
    if args.prompt:
        event["prompt"] = args.prompt

    print(f"Invoking Lambda: {args.function_name}")
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=args.function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(event),
    )
    result = json.loads(response["Payload"].read())

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("statusCode") == 200 else 1)


if __name__ == "__main__":
    main()
