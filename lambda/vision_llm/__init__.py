"""
Image Processor Service

Handles fisheye image processing, perspective view generation,
and LLM-based image analysis.
"""

from .fisheye import (
    create_perspective_map,
    extract_center_view,
    fisheye_to_perspective_fast,
    get_room_views,
)
from .llm import analyze_image, analyze_with_openai
from .models import (
    DEFAULT_MODEL,
    MODELS,
    OpenAIModel,
    Provider,
    get_model,
    get_provider_for_model,
    list_models,
)
from .prompts import (
    create_prompt_line,
    get_default_prompt,
    get_prompt,
    get_prompt_names,
    list_prompts,
    push_prompt,
)
from .utils import (
    image_to_base64,
    save_image,
)

__all__ = [
    'create_perspective_map',
    'fisheye_to_perspective_fast',
    'extract_center_view',
    'get_room_views',
    'analyze_image',
    'analyze_with_openai',
    'image_to_base64',
    'save_image',
    'OpenAIModel',
    'DEFAULT_MODEL',
    'MODELS',
    'Provider',
    'list_models',
    'get_model',
    'get_provider_for_model',
    'list_prompts',
    'get_prompt_names',
    'get_prompt',
    'create_prompt_line',
    'push_prompt',
    'get_default_prompt',
]
