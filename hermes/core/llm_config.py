"""LLM configuration loader for Hermes.

Reads provider API keys and default model from environment variables / .env.
Supports a registry of providers so Hermes is not hard-coded to a single LLM.
"""

import os
from pathlib import Path
from typing import Any

import litellm
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
        "provider_type": "custom",
        "default_timeout": 120,
    },
    "local_cx": {
        "model_env": "HERMES_LOCAL_CX_MODEL",
        "model_env_fallbacks": ["CX_MODEL"],
        "base_url_env": "HERMES_LOCAL_CX_BASE_URL",
        "base_url_env_fallbacks": ["CX_BASE_URL"],
        "api_key_env": "HERMES_LOCAL_CX_API_KEY",
        "api_key_env_fallbacks": ["LLM_API_KEY", "CX_API_KEY"],
        "timeout_env": "HERMES_LOCAL_CX_TIMEOUT",
        "timeout_env_fallbacks": ["CX_TIMEOUT"],
        "litellm_prefix": "openai",
        "provider_type": "custom",
        "default_model": "cx/gpt-5.4",
        "default_base_url": "http://100.90.2.127:20128/v1",
        "default_timeout": 120,
    },
    "anthropic": {
        "model_env": "ANTHROPIC_MODEL",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "api_key_env": "ANTHROPIC_API_KEY",
        "timeout_env": "ANTHROPIC_TIMEOUT",
        "litellm_prefix": "anthropic",
        "provider_type": "anthropic",
        "default_timeout": 120,
    },
}


class HermesLLM:
    """Small LiteLLM wrapper used by manual connectivity checks and analyzer."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def call(self, prompt: str, **kwargs) -> str:
        response = litellm.completion(
            model=self.config["model"],
            api_base=self.config.get("base_url"),
            api_key=self.config.get("api_key"),
            timeout=self.config.get("timeout", 120),
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content

    def describe_image(self, image_url: str, prompt: str) -> str:
        response = litellm.completion(
            model=self.config["model"],
            api_base=self.config.get("base_url"),
            api_key=self.config.get("api_key"),
            timeout=self.config.get("timeout", 120),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        )
        return response.choices[0].message.content


def _read_env(primary: str | None, fallbacks: list[str] | None = None, default: str | None = None) -> str | None:
    names = []
    if primary:
        names.append(primary)
    names.extend(fallbacks or [])
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return default


def get_llm_config(provider: str | None = None) -> dict:
    """Return a dict of kwargs for CrewAI's LLM class.

    provider: key in PROVIDER_REGISTRY. If None, read from
    HERMES_LLM_PROVIDER (default 'opencode_go').
    """
    provider = provider or os.environ.get("HERMES_LLM_PROVIDER", "opencode_go")
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available: {list(PROVIDER_REGISTRY)}"
        )

    spec = PROVIDER_REGISTRY[provider]
    model = _read_env(
        spec.get("model_env"),
        spec.get("model_env_fallbacks"),
        spec.get("default_model"),
    )
    if not model:
        raise RuntimeError(
            f"Missing env var {spec['model_env']} for provider '{provider}'"
        )

    api_key = _read_env(spec.get("api_key_env"), spec.get("api_key_env_fallbacks"), "") or ""
    base_url = _read_env(
        spec.get("base_url_env"),
        spec.get("base_url_env_fallbacks"),
        spec.get("default_base_url"),
    )
    timeout = _parse_timeout(
        _read_env(spec.get("timeout_env"), spec.get("timeout_env_fallbacks"), ""),
        spec["default_timeout"],
    )

    # LiteLLM / CrewAI use the format "provider/model".
    full_model = f"{spec['litellm_prefix']}/{model}"

    max_tokens_env = f"{provider.upper()}_MAX_TOKENS"
    if provider == "local_cx":
        max_tokens = int(
            _read_env("HERMES_LOCAL_CX_MAX_TOKENS", ["CX_MAX_TOKENS", max_tokens_env], "4000")
        )
    else:
        max_tokens = int(os.environ.get(max_tokens_env, "4000"))

    config = {
        "provider": provider,
        "provider_type": spec.get("provider_type", spec["litellm_prefix"]),
        "model": full_model,
        "raw_model": model,
        "api_key": api_key,
        "timeout": timeout,
        "max_tokens": max_tokens,
    }
    if base_url:
        config["base_url"] = base_url
    return config


def get_llm(provider: str | None = None) -> HermesLLM:
    """Return a lightweight LLM client with `.call()` and vision support."""
    return HermesLLM(get_llm_config(provider))


def _parse_timeout(raw: str | None, default: int) -> int:
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def list_providers() -> list[str]:
    """Return the names of all configured providers."""
    return list(PROVIDER_REGISTRY.keys())
