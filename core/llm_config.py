"""
LLM configuration loader for Hermes.

Reads provider API keys and default model from environment variables / .env.
Raises a clear error if required keys are missing so that failures happen early.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the workspace root or the repo root if present.
load_dotenv()


def get_llm_config():
    """Return a dictionary with the active LLM configuration.

    Supports multiple providers via environment variables:
      - Anthropic: ANTHROPIC_API_KEY + optional HERMES_DEFAULT_MODEL
      - OpenAI/OpenRouter/local: LLM_API_KEY + LLM_MODEL + LLM_BASE_URL
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Thieu ANTHROPIC_API_KEY trong .env hoac bien moi truong. "
                "Hay tao file .env voi noi dung: ANTHROPIC_API_KEY=sk-ant-xxxxx"
            )
        return {
            "provider": "anthropic",
            "model": os.environ.get("HERMES_DEFAULT_MODEL", "claude-sonnet-4-6"),
            "api_key": api_key,
        }

    # Generic OpenAI-compatible provider (OpenRouter, local LLM server, etc.)
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")
    model = os.environ.get("LLM_MODEL")

    if not api_key or not base_url or not model:
        raise RuntimeError(
            "Khi dung LLM_PROVIDER != anthropic, can cung cap LLM_API_KEY, "
            "LLM_BASE_URL va LLM_MODEL trong .env"
        )

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "timeout": int(os.environ.get("LLM_TIMEOUT", "120")),
    }
