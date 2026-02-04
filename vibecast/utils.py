"""
Image Processing Utilities

Helper functions for image conversion and saving.
"""

import base64

import cv2


def image_to_base64(img_np):
    """Convert numpy array (RGB) to base64 JPEG."""
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    _, encoded = cv2.imencode(".jpg", img_bgr)
    return base64.b64encode(encoded.tobytes()).decode("utf-8")


def save_image(img_np, filepath):
    """Save numpy array (RGB) to file."""
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(filepath), img_bgr)
