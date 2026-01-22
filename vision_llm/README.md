# Image Processor Service

Self-contained service for processing fisheye camera images and analyzing them with LLMs.

## Components

- **fisheye.py**: Fisheye image processing and perspective view generation
  - `create_perspective_map()`: Create remap arrays for perspective conversion
  - `fisheye_to_perspective_fast()`: Convert fisheye to perspective view
  - `extract_center_view()`: Extract center (below) view from fisheye
  - `get_room_views()`: Generate all directional views (N, S, E, W, Below)

- **llm.py**: LLM-based image analysis
  - `analyze_with_openai()`: Send images to OpenAI GPT-4o for analysis

- **utils.py**: Image utilities
  - `image_to_base64()`: Convert numpy array to base64 JPEG
  - `save_image()`: Save numpy array as image file

- **default_prompt.txt**: Default prompt for LLM image analysis

## Usage

```python
from vision_llm import get_room_views, analyze_with_openai, image_to_base64

# Generate perspective views from fisheye image
views = get_room_views(fisheye_image, fov=90, output_size=(1080, 810))

# Analyze a view with LLM
image_b64 = image_to_base64(views['North'])
result = analyze_with_openai(image_b64, prompt, api_key)
```

## Dependencies

- opencv-python (cv2)
- numpy
- openai (for LLM analysis)
