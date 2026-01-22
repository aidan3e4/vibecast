"""
LLM Image Analysis

Functions for analyzing images using LLM APIs.
"""

import json


def analyze_with_openai(image_base64, prompt, api_key):
    """Send image to OpenAI for analysis."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
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
    content = json.loads(content)
    return content
