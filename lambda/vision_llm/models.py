"""LLM model definitions for multiple providers via litellm."""

from dataclasses import dataclass
from enum import Enum


class Provider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    NOVITA = "novita"


@dataclass
class ModelInfo:
    """Model metadata."""
    id: str  # litellm model identifier
    name: str
    provider: Provider
    description: str
    tier: str  # standard, premium, economy, legacy
    supports_vision: bool = True


# Available models with vision support
MODELS: dict[str, ModelInfo] = {
    # OpenAI models
    "gpt-4o": ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        provider=Provider.OPENAI,
        description="Capable GPT-4o model for vision analysis",
        tier="standard",
    ),
    "gpt-4o-mini": ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=Provider.OPENAI,
        description="Smaller, faster, and cheaper GPT-4o variant",
        tier="economy",
    ),
    "gpt-4-turbo": ModelInfo(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        provider=Provider.OPENAI,
        description="Legacy GPT-4 Turbo with vision",
        tier="legacy",
    ),
    # Anthropic models
    "claude-sonnet-4-20250514": ModelInfo(
        id="claude-sonnet-4-20250514",
        name="Claude Sonnet 4",
        provider=Provider.ANTHROPIC,
        description="Anthropic's balanced model with vision capabilities",
        tier="standard",
    ),
    "claude-opus-4-20250514": ModelInfo(
        id="claude-opus-4-20250514",
        name="Claude Opus 4",
        provider=Provider.ANTHROPIC,
        description="Anthropic's most capable model",
        tier="premium",
    ),
    # Google models
    "gemini/gemini-2.0-flash": ModelInfo(
        id="gemini/gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider=Provider.GOOGLE,
        description="Google's fast multimodal model",
        tier="economy",
    ),
    "gemini/gemini-2.5-pro": ModelInfo(
        id="gemini/gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        provider=Provider.GOOGLE,
        description="Google's advanced multimodal model",
        tier="standard",
    ),
    # Novita models
    "novita/moonshotai/kimi-k2.5": ModelInfo(
        id="novita/moonshotai/kimi-k2.5",
        name="Kimi K2.5",
        provider=Provider.NOVITA,
        description="Moonshot AI's Kimi K2.5 via Novita",
        tier="standard",
    ),
}

DEFAULT_MODEL = "gpt-4o"


def list_models() -> list[dict]:
    """Return all available models with metadata for API consumers."""
    return [
        {
            "id": model.id,
            "name": model.name,
            "provider": model.provider.value,
            "description": model.description,
            "tier": model.tier,
            "supports_vision": model.supports_vision,
        }
        for model in MODELS.values()
    ]


def get_model(model_id: str) -> ModelInfo | None:
    """Get model info by ID."""
    return MODELS.get(model_id)


def get_provider_for_model(model_id: str) -> Provider | None:
    """Get the provider for a given model ID."""
    model = MODELS.get(model_id)
    return model.provider if model else None


# Backwards compatibility - keep OpenAIModel for existing code
class OpenAIModel(str, Enum):
    """Available OpenAI models for vision analysis (deprecated - use MODELS dict)."""
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4_TURBO = "gpt-4-turbo"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def list_models(cls) -> list[dict]:
        """Return OpenAI models only (for backwards compatibility)."""
        return [m for m in list_models() if m["provider"] == Provider.OPENAI.value]
