"""
LLM configuration loader for Hermes.

Reads provider API keys and default model from environment variables / .env.
Supports a registry of providers so Hermes is not hard-coded to a single LLM.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the workspace root if present.
load_dotenv()

# Each provider maps env vars to a CrewAI/LiteLLM-compatible model string.
# OpenAI-compatible endpoints must use base_url WITHOUT /chat/completions
# because the OpenAI SDK appends that path automatically.
PROVIDER_REGISTRY = {
    "opencode_go": {
        "model_env": "OPENCODE_MODEL",
        "base_url_env": "OPENCODE_BASE_URL",
        "api_key_env": "OPENCODE_API_KEY",
        "timeout_env": "OPENCODE_TIMEOUT",
        "litellm_prefix": "openai",
        "default_timeout": 120,
    },
    "local_cx": {
        "model_env": "CX_MODEL",
        "base_url_env": "CX_BASE_URL",
        "api_key_env": "CX_API_KEY",
        "timeout_env": "CX_TIMEOUT",
        "litellm_prefix": "openai",
        "default_timeout": 120,
    },
    "anthropic": {
        "model_env": "ANTHROPIC_MODEL",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "api_key_env": "ANTHROPIC_API_KEY",
        "timeout_env": "ANTHROPIC_TIMEOUT",
        "litellm_prefix": "anthropic",
        "default_timeout": 120,
    },
}


def get_llm_config(provider: str | None = None) -> dict:
    """Return a dict of kwargs for CrewAI's LLM class.

    provider: key in PROVIDER_REGISTRY.  If None, read from
    HERMES_LLM_PROVIDER (default 'opencode_go').
    """
    provider = provider or os.environ.get("HERMES_LLM_PROVIDER", "opencode_go")
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available: {list(PROVIDER_REGISTRY)}"
        )

    spec = PROVIDER_REGISTRY[provider]
    model = os.environ.get(spec["model_env"])
    if not model:
        raise RuntimeError(
            f"Missing env var {spec['model_env']} for provider '{provider}'"
        )

    api_key = os.environ.get(spec["api_key_env"], "") if spec["api_key_env"] else ""
    base_url = os.environ.get(spec["base_url_env"]) if spec["base_url_env"] else None
    timeout = _parse_timeout(
        os.environ.get(spec["timeout_env"], ""),
        spec["default_timeout"],
    )

    # LiteLLM / CrewAI use the format "provider/model".
    full_model = f"{spec['litellm_prefix']}/{model}"

    config = {
        "provider": provider,
        "model": full_model,
        "api_key": api_key,
        "timeout": timeout,
        "max_tokens": int(os.environ.get(f"{provider.upper()}_MAX_TOKENS", "4000")),
    }
    if base_url:
        config["base_url"] = base_url
    return config


def _parse_timeout(raw: str, default: int) -> int:
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def list_providers() -> list[str]:
    """Return the names of all configured providers."""
    return list(PROVIDER_REGISTRY.keys())
