"""
LLM Image Analysis

Functions for analyzing images using LLM APIs.
"""

import json

from .models import DEFAULT_MODEL, OpenAIModel


def analyze_with_openai(image_base64, prompt, api_key, model: OpenAIModel | str = DEFAULT_MODEL):
    """Send image to OpenAI for analysis."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    },
                ],
            }
        ],
    )

    content = response.choices[0].message.content
    content = content.split("```JSON", 1)[-1].rsplit("```", 1)[0]
    try:
        content = json.loads(content)
    except json.JSONDecodeError:
        pass
    return content # TODO: fix since now it's either a dict or a string
