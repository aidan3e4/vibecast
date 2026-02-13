# Image Rotation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `rotate` operation to the Lambda that rotates an image by a given angle and saves it alongside the original with a `_rotated` suffix.

**Architecture:** New `rotate=true` + `rotation_angle` params alongside existing `unwarp`/`analyze` booleans. The rotation logic lives in `processor.py` using OpenCV's `cv2.rotate()`. The rotated image is saved to the same S3 bucket/path as the input, with `_rotated` appended to the filename.

**Tech Stack:** OpenCV (`cv2.rotate`), existing S3 utilities

---

### Task 1: Add rotate_image function to processor.py

**Files:**
- Modify: `vibecast/processor.py`
- Test: `tests/test_rotate.py`

**Step 1: Write the failing test**

Create `tests/test_rotate.py`:

```python
import numpy as np

from vibecast.processor import rotate_image


def test_rotate_image_90():
    """Rotating a 2x3 image by 90 degrees produces a 3x2 image."""
    img = np.zeros((2, 3, 3), dtype=np.uint8)
    img[0, 0] = [255, 0, 0]  # Red pixel at top-left

    rotated = rotate_image(img, 90)

    assert rotated.shape == (3, 2, 3)
    # After 90° clockwise rotation, top-left goes to top-right
    np.testing.assert_array_equal(rotated[0, 1], [255, 0, 0])


def test_rotate_image_180():
    img = np.zeros((2, 3, 3), dtype=np.uint8)
    img[0, 0] = [255, 0, 0]

    rotated = rotate_image(img, 180)

    assert rotated.shape == (2, 3, 3)
    # After 180° rotation, top-left goes to bottom-right
    np.testing.assert_array_equal(rotated[1, 2], [255, 0, 0])


def test_rotate_image_270():
    img = np.zeros((2, 3, 3), dtype=np.uint8)
    img[0, 0] = [255, 0, 0]

    rotated = rotate_image(img, 270)

    assert rotated.shape == (3, 2, 3)
    # After 270° clockwise rotation, top-left goes to bottom-left
    np.testing.assert_array_equal(rotated[2, 0], [255, 0, 0])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rotate.py -v`
Expected: FAIL with `ImportError: cannot import name 'rotate_image'`

**Step 3: Write minimal implementation**

Add to `vibecast/processor.py` (after the `unwarp_fisheye_image` function, before `process_image_async`):

```python
def rotate_image(img_rgb, angle: int):
    """Rotate an image by the given angle (90, 180, or 270 degrees clockwise).

    Args:
        img_rgb: Numpy array (RGB) of the image
        angle: Rotation angle in degrees. Must be 90, 180, or 270.

    Returns:
        Rotated numpy array (RGB)
    """
    rotation_map = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    if angle not in rotation_map:
        raise ValueError(f"Invalid rotation angle: {angle}. Must be 90, 180, or 270.")
    return cv2.rotate(img_rgb, rotation_map[angle])
```

Also add `import cv2` at the top of `processor.py`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rotate.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add tests/test_rotate.py vibecast/processor.py
git commit -m "feat: add rotate_image function"
```

---

### Task 2: Wire rotation into process_image_async

**Files:**
- Modify: `vibecast/processor.py`
- Test: `tests/test_rotate.py`

**Step 1: Write the failing test**

Add to `tests/test_rotate.py`:

```python
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_s3():
    """Mock all S3 operations."""
    with (
        patch("vibecast.processor.download_image_from_s3") as mock_download,
        patch("vibecast.processor.upload_image_to_s3") as mock_upload,
        patch("vibecast.processor.upload_json_to_s3") as mock_upload_json,
    ):
        # Return a simple 10x10 RGB image
        mock_download.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
        mock_upload.return_value = "s3://bucket/rotated/image_rotated.jpg"
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
        rotation_angle=90,
    )

    assert "rotated_image" in result
    assert result["config"]["rotate"] is True
    assert result["config"]["rotation_angle"] == 90
    mock_s3["download"].assert_called_once_with("bucket", "path/image.jpg")
    # Verify upload key ends with _rotated.jpg
    upload_call = mock_s3["upload"].call_args
    assert upload_call[0][1] == "bucket"  # same bucket as input
    assert upload_call[0][2] == "path/image_rotated.jpg"  # same path, _rotated suffix


async def test_process_image_rotate_missing_angle(mock_s3):
    from vibecast.processor import process_image_async

    with pytest.raises(ValueError, match="rotation_angle is required"):
        await process_image_async(
            input_s3_uri="s3://bucket/path/image.jpg",
            rotate=True,
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rotate.py::test_process_image_rotate tests/test_rotate.py::test_process_image_rotate_missing_angle -v`
Expected: FAIL with `TypeError: process_image_async() got an unexpected keyword argument 'rotate'`

**Step 3: Write minimal implementation**

Modify `process_image_async` in `vibecast/processor.py`:

1. Add `rotate` and `rotation_angle` parameters to the function signature:

```python
async def process_image_async(
    input_s3_uri: str,
    unwarp: bool = False,
    analyze: bool = False,
    rotate: bool = False,
    views_to_analyze: list[str] = None,
    prompt: str = None,
    model: str = None,
    output_bucket: str = None,
    results_bucket: str = None,
    fov: int = None,
    view_angle: int = None,
    rotation_angle: int = None,
) -> dict[str, Any]:
```

2. Update the validation (around line 92) to include `rotate`:

```python
    if not unwarp and not analyze and not rotate:
        raise ValueError("At least one operation must be specified: unwarp=True, analyze=True, or rotate=True")
```

3. Add rotation mode block after the existing MODE 3 block (after line 172), before the "Build final results" section:

```python
    rotated_uri = None

    # MODE 4: Rotate image
    if rotate:
        if not rotation_angle:
            raise ValueError("rotation_angle is required when rotate=True")
        input_img = download_image_from_s3(input_bucket, input_key)
        rotated_img = rotate_image(input_img, rotation_angle)

        # Save to same bucket/path as input, with _rotated suffix
        name_without_ext, ext = input_key.rsplit(".", 1)
        rotated_key = f"{name_without_ext}_rotated.{ext}"
        rotated_uri = upload_image_to_s3(rotated_img, input_bucket, rotated_key)
```

4. Add to the results building section (after `analysis_results` inclusion):

```python
    if rotated_uri is not None:
        results["rotated_image"] = rotated_uri
        results["config"]["rotate"] = True
        results["config"]["rotation_angle"] = rotation_angle
```

Also update the `process_image` sync wrapper to pass through `rotate` and `rotation_angle`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rotate.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add vibecast/processor.py tests/test_rotate.py
git commit -m "feat: wire rotation into process_image pipeline"
```

---

### Task 3: Wire rotation into Lambda handler and CLI

**Files:**
- Modify: `vibecast/handler.py`
- Test: `tests/test_rotate.py`

**Step 1: Write the failing test**

Add to `tests/test_rotate.py`:

```python
def test_lambda_handler_rotate():
    with patch("vibecast.handler.process_image") as mock_process:
        mock_process.return_value = {
            "input_uri": "s3://bucket/image.jpg",
            "rotated_image": "s3://bucket/image_rotated.jpg",
            "processed_at": "2026-02-12T00:00:00Z",
            "config": {"rotate": True, "rotation_angle": 90},
            "results_uri": "s3://bucket/results.json",
        }

        from vibecast.handler import lambda_handler

        result = lambda_handler(
            {"input_s3_uri": "s3://bucket/image.jpg", "rotate": True, "rotation_angle": 90},
            None,
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "rotated_image" in body
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["rotate"] is True
        assert call_kwargs["rotation_angle"] == 90
```

Add the required import at the top of the test file:

```python
import json
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rotate.py::test_lambda_handler_rotate -v`
Expected: FAIL because `handler.py` doesn't pass `rotate`/`rotation_angle` to `process_image`

**Step 3: Write minimal implementation**

Modify `vibecast/handler.py`:

1. Update the validation block (lines 121-126). Change:

```python
        if not unwarp and not analyze:
```

to:

```python
        rotate = params.get("rotate", False)
        rotation_angle = params.get("rotation_angle")

        if not unwarp and not analyze and not rotate:
```

And update the error message to include `rotate=true`.

2. Pass `rotate` and `rotation_angle` to `process_image` (around line 137):

```python
        result = process_image(
            input_s3_uri=input_s3_uri,
            unwarp=unwarp,
            analyze=analyze,
            rotate=rotate,
            views_to_analyze=views_to_analyze,
            prompt=prompt,
            model=model,
            output_bucket=output_bucket,
            results_bucket=results_bucket,
            fov=fov,
            view_angle=view_angle,
            rotation_angle=rotation_angle,
        )
```

3. Update the CLI argument parser section (after the `--view-angle` argument, around line 380) to add:

```python
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Rotate the image by the specified angle",
    )
    parser.add_argument(
        "--rotation-angle",
        type=int,
        choices=[90, 180, 270],
        help="Rotation angle in degrees (90, 180, or 270)",
    )
```

4. Update the CLI validation (around line 394):

```python
    if not args.unwarp and not args.analyze and not args.rotate:
        parser.error("At least one operation must be specified: --unwarp, --analyze, or --rotate")
```

5. Add to the event building:

```python
    if args.rotate:
        event["rotate"] = True
    if args.rotation_angle:
        event["rotation_angle"] = args.rotation_angle
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rotate.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add vibecast/handler.py tests/test_rotate.py
git commit -m "feat: wire rotation into Lambda handler and CLI"
```

---

### Task 4: Run full test suite and lint

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 2: Run linter**

Run: `ruff check vibecast/ tests/`
Expected: No errors (or fix any that appear)

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "lint: fix any linting issues"
```
