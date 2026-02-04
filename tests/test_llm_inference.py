import base64
from pathlib import Path

from vibecast import analyze_image

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def get_test_image(name: str = "standardboard.png") -> str:
    """Load a test image from fixtures and return base64 encoded string."""
    image_path = FIXTURES_DIR / name
    if not image_path.exists():
        raise FileNotFoundError(f"Test image not found: {image_path}")
    return base64.b64encode(image_path.read_bytes()).decode()

async def test_analyze_image():
    img_b64 = get_test_image()
    result = await analyze_image(img_b64, "Describe this image", model="gpt-4o")
    assert isinstance(result, str)
