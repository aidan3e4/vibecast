#!/usr/bin/env python3
"""Local testing script for the Lambda handler.

This script simulates Lambda invocation locally for testing.
Requires AWS credentials configured and S3 buckets to exist.

Usage:
    python test_local.py
"""
import json
import os
import sys

# Add parent directory to path for vision_llm import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables for local testing
os.environ.setdefault("INPUT_BUCKET", "vibecast-input")
os.environ.setdefault("OUTPUT_BUCKET", "vibecast-output")
os.environ.setdefault("RESULTS_BUCKET", "vibecast-results")
# os.environ.setdefault("OPENAI_API_KEY", "your-key-here")

from handler import lambda_handler


def test_basic_unwarp():
    """Test basic unwarping without LLM analysis."""
    event = {
        "input_s3_uri": "s3://vibecast-input/test/fisheye.jpg",
    }

    result = lambda_handler(event, None)
    print("Basic unwarp result:")
    print(json.dumps(result, indent=2))
    return result


def test_with_analysis():
    """Test with LLM analysis on selected views."""
    event = {
        "input_s3_uri": "s3://vibecast-input/test/fisheye.jpg",
        "views_to_analyze": ["N", "S"],
        "prompt": "Describe what you see in this image. Return JSON with 'description' key.",
    }

    result = lambda_handler(event, None)
    print("Analysis result:")
    print(json.dumps(result, indent=2))
    return result


def test_validation_error():
    """Test validation error handling."""
    event = {
        # Missing input_s3_uri
    }

    result = lambda_handler(event, None)
    print("Validation error result:")
    print(json.dumps(result, indent=2))
    assert result["statusCode"] == 400
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Lambda handler locally")
    print("=" * 60)

    # Test validation
    print("\n--- Test: Validation Error ---")
    test_validation_error()

    # Uncomment to test with real S3 buckets:
    # print("\n--- Test: Basic Unwarp ---")
    # test_basic_unwarp()
    #
    # print("\n--- Test: With LLM Analysis ---")
    # test_with_analysis()

    print("\nAll tests passed!")
