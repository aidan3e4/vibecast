"""
LLM Image Analysis

Functions for analyzing images using multiple LLM providers via litellm.
"""

import json

from llm_inference.llm.inference import InferenceConfig, ModelConfig, llm_turn

from .models import DEFAULT_MODEL


async def analyze_image(
    image_base64: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
) -> dict | str:
    """
    Analyze an image using the specified LLM model.

    Supports multiple providers via litellm:
    - OpenAI (gpt-4o, gpt-4o-mini, etc.)
    - Anthropic (claude-sonnet-4, claude-opus-4, etc.)
    - Google (gemini-2.0-flash, gemini-2.5-pro, etc.)

    Args:
        image_base64: Base64-encoded image data
        prompt: Analysis prompt
        model: Model identifier (default: gpt-4o)

    Returns:
        Parsed JSON response or raw string if JSON parsing fails
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            ],
        }
    ]

    model_config = ModelConfig(model_name=model)
    inference_config = InferenceConfig(max_turns_llm_consecutive=1, max_turns_session=1)

    content = await llm_turn(
        messages=messages,
        model_config=model_config,
        inference_config=inference_config,
    )

    # Extract JSON from markdown code blocks if present
    if content and ("```JSON" in content or "```json" in content):
        content = content.split("```JSON", 1)[-1].split("```json", 1)[-1]
        content = content.rsplit("```", 1)[0]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


# Backwards compatibility alias
async def analyze_with_openai(
    image_base64: str,
    prompt: str,
    api_key: str = None,
    model: str = DEFAULT_MODEL,
) -> dict | str:
    """Legacy function - use analyze_image() instead."""
    return await analyze_image(
        image_base64=image_base64,
        prompt=prompt,
        model=model,
    )
