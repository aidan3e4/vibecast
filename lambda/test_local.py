#!/usr/bin/env python3
"""Local testing for the Lambda handler.

Usage:
    # Test with mocked S3 (no AWS needed)
    python test_local.py --mock

    # Test with real S3 (requires AWS credentials and buckets)
    python test_local.py --real s3://vibecast-input/test/fisheye.jpg

    # Test just the image processing (no S3, use local file)
    python test_local.py --local-file /path/to/fisheye.jpg
"""
import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set defaults for local testing
os.environ.setdefault("INPUT_BUCKET", "vibecast-input")
os.environ.setdefault("OUTPUT_BUCKET", "vibecast-output")
os.environ.setdefault("RESULTS_BUCKET", "vibecast-results")


def test_with_mock():
    """Test handler with mocked S3 - no AWS credentials needed."""
    import numpy as np

    # Create a fake fisheye image (black square)
    fake_image = np.zeros((1920, 1920, 3), dtype=np.uint8)

    # Mock S3 operations
    with patch("lambda.s3_utils.s3_client") as mock_s3:
        # Mock download to return our fake image
        import cv2
        _, encoded = cv2.imencode(".jpg", fake_image)

        mock_response = {"Body": MagicMock()}
        mock_response["Body"].read.return_value = encoded.tobytes()
        mock_s3.get_object.return_value = mock_response
        mock_s3.put_object.return_value = {}

        from lambda.handler import lambda_handler

        # Test basic unwarp
        event = {"input_s3_uri": "s3://vibecast-input/test/fisheye.jpg"}
        result = lambda_handler(event, None)

        print("Mock test result:")
        print(json.dumps(result, indent=2))

        assert result["statusCode"] == 200, f"Expected 200, got {result['statusCode']}"
        assert "unwarped_images" in result["body"]
        assert len(result["body"]["unwarped_images"]) == 5

        print("\nMock test PASSED - all 5 views generated")
        return result


def test_with_real_s3(input_uri: str, views: list[str] = None):
    """Test with real S3 buckets - requires AWS credentials."""
    from lambda.handler import lambda_handler

    event = {"input_s3_uri": input_uri}
    if views:
        event["views_to_analyze"] = views

    print(f"Testing with real S3: {input_uri}")
    result = lambda_handler(event, None)

    print("Result:")
    print(json.dumps(result, indent=2))
    return result


def test_with_local_file(filepath: str):
    """Test image processing with a local file (no S3)."""
    import cv2
    from vision_llm import get_room_views, image_to_base64

    print(f"Loading local file: {filepath}")
    img_bgr = cv2.imread(filepath)
    if img_bgr is None:
        print(f"ERROR: Could not load image from {filepath}")
        sys.exit(1)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    print(f"Image shape: {img_rgb.shape}")

    print("Generating perspective views...")
    views = get_room_views(img_rgb, fov=90, output_size=(1080, 810))

    print(f"Generated {len(views)} views:")
    for name, img in views.items():
        print(f"  - {name}: {img.shape}")

    # Optionally save to temp directory
    output_dir = Path("/tmp/vibecast_test")
    output_dir.mkdir(exist_ok=True)

    for name, img in views.items():
        out_path = output_dir / f"{name.lower()}.jpg"
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(out_path), img_bgr)
        print(f"  Saved: {out_path}")

    print(f"\nLocal test PASSED - views saved to {output_dir}")
    return views


def test_validation():
    """Test error handling."""
    from lambda.handler import lambda_handler

    # Missing required field
    result = lambda_handler({}, None)
    assert result["statusCode"] == 400
    print("Validation test PASSED")


def main():
    parser = argparse.ArgumentParser(description="Local Lambda testing")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--mock", action="store_true", help="Test with mocked S3")
    group.add_argument("--real", type=str, metavar="S3_URI", help="Test with real S3")
    group.add_argument("--local-file", type=str, metavar="PATH", help="Test with local image file")
    group.add_argument("--validate", action="store_true", help="Test validation/error handling")

    parser.add_argument("--views", nargs="+", help="Views to analyze (for --real)")

    args = parser.parse_args()

    if args.mock:
        test_with_mock()
    elif args.real:
        test_with_real_s3(args.real, args.views)
    elif args.local_file:
        test_with_local_file(args.local_file)
    elif args.validate:
        test_validation()


if __name__ == "__main__":
    main()
