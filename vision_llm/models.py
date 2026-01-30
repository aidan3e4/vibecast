"""OpenAI model definitions."""

from enum import Enum


class OpenAIModel(str, Enum):
    """Available OpenAI models for vision analysis."""

    # GPT-5 family
    GPT_5_2 = "gpt-5.2"
    GPT_5_2_PRO = "gpt-5.2-pro"

    # GPT-4o family
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"

    # GPT-4 Turbo (legacy vision)
    GPT_4_TURBO = "gpt-4-turbo"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def list_models(cls) -> list[dict]:
        """Return all available models with metadata for API consumers."""
        metadata = {
            cls.GPT_5_2: {
                "description": "Complex reasoning, broad world knowledge, and code-heavy or multi-step agentic tasks",
                "tier": "standard",
            },
            cls.GPT_5_2_PRO: {
                "description": "Tough problems that may take longer to solve but require harder thinking",
                "tier": "premium",
            },
            cls.GPT_4O: {
                "description": "Capable GPT-4o model for vision analysis",
                "tier": "standard",
            },
            cls.GPT_4O_MINI: {
                "description": "Smaller, faster, and cheaper GPT-4o variant",
                "tier": "economy",
            },
            cls.GPT_4_TURBO: {
                "description": "Legacy GPT-4 Turbo with vision (deprecated)",
                "tier": "legacy",
            },
        }
        return [
            {
                "id": model.value,
                "name": model.name,
                **metadata.get(model, {}),
            }
            for model in cls
        ]


# Default model for analysis
DEFAULT_MODEL = OpenAIModel.GPT_4O
