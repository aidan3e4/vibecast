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
