import json
from unittest.mock import patch

import numpy as np
import pytest

from vibecast.processor import rotate_image


def test_rotate_image_90():
    """Rotating a 100x200 image by 90 degrees produces ~200x100 image."""
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    img[10, 20] = [255, 0, 0]

    rotated = rotate_image(img, 90)

    # For 90° rotation, dimensions swap
    assert rotated.shape[0] == 200
    assert rotated.shape[1] == 100


def test_rotate_image_180():
    """Rotating by 180 degrees preserves dimensions."""
    img = np.zeros((100, 200, 3), dtype=np.uint8)

    rotated = rotate_image(img, 180)

    assert rotated.shape == (100, 200, 3)


def test_rotate_image_270():
    """Rotating a 100x200 image by 270 degrees produces ~200x100 image."""
    img = np.zeros((100, 200, 3), dtype=np.uint8)

    rotated = rotate_image(img, 270)

    assert rotated.shape[0] == 200
    assert rotated.shape[1] == 100


def test_rotate_image_arbitrary_angle():
    """Rotating by an arbitrary angle expands the canvas."""
    img = np.zeros((100, 200, 3), dtype=np.uint8)

    rotated = rotate_image(img, 45)

    # Canvas should be larger than original for non-90-multiple angles
    assert rotated.shape[0] > 100
    assert rotated.shape[1] > 200


def test_rotate_image_zero():
    """Rotating by 0 degrees returns same-sized image."""
    img = np.ones((50, 100, 3), dtype=np.uint8) * 128

    rotated = rotate_image(img, 0)

    assert rotated.shape == (50, 100, 3)
    np.testing.assert_array_equal(rotated, img)


def test_rotate_image_negative_angle():
    """Rotating by a negative angle works (counter-clockwise)."""
    img = np.zeros((100, 200, 3), dtype=np.uint8)

    rotated = rotate_image(img, -30)

    # Should expand canvas
    assert rotated.shape[0] > 100
    assert rotated.shape[1] > 200


@pytest.fixture
def mock_s3():
    """Mock all S3 operations."""
    with (
        patch("vibecast.processor.download_image_from_s3") as mock_download,
        patch("vibecast.processor.upload_image_to_s3") as mock_upload,
        patch("vibecast.processor.upload_json_to_s3") as mock_upload_json,
    ):
        mock_download.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
        mock_upload.return_value = "s3://bucket/path/image_rotated.jpg"
        mock_upload_json.return_value = "s3://bucket/results/image_results.json"
        yield {
            "download": mock_download,
            "upload": mock_upload,
            "upload_json": mock_upload_json,
        }


async def test_process_image_rotate(mock_s3):
    from vibecast.processor import process_image_async

    result = await process_image_async(
        input_s3_uri="s3://bucket/path/image.jpg",
        rotate=True,
        rotation_angle=15,
    )

    assert "rotated_image" in result
    assert result["config"]["rotate"] is True
    assert result["config"]["rotation_angle"] == 15
    mock_s3["download"].assert_called_once_with("bucket", "path/image.jpg")
    upload_call = mock_s3["upload"].call_args
    assert upload_call[0][1] == "bucket"
    assert upload_call[0][2] == "path/image_rotated.jpg"


async def test_process_image_rotate_missing_angle(mock_s3):
    from vibecast.processor import process_image_async

    with pytest.raises(ValueError, match="rotation_angle is required"):
        await process_image_async(
            input_s3_uri="s3://bucket/path/image.jpg",
            rotate=True,
        )


def test_lambda_handler_rotate():
    with patch("vibecast.handler.process_image") as mock_process:
        mock_process.return_value = {
            "input_uri": "s3://bucket/image.jpg",
            "rotated_image": "s3://bucket/image_rotated.jpg",
            "processed_at": "2026-02-12T00:00:00Z",
            "config": {"rotate": True, "rotation_angle": 15},
            "results_uri": "s3://bucket/results.json",
        }

        from vibecast.handler import lambda_handler

        result = lambda_handler(
            {"input_s3_uri": "s3://bucket/image.jpg", "rotate": True, "rotation_angle": 15},
            None,
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "rotated_image" in body
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["rotate"] is True
        assert call_kwargs["rotation_angle"] == 15
