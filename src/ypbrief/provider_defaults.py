from __future__ import annotations


def normalize_provider(provider: str) -> str:
    return (provider or "").strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")


BUILTIN_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "provider": "openai",
        "provider_type": "openai_compatible",
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "",
    },
    "gemini": {
        "provider": "gemini",
        "provider_type": "gemini",
        "display_name": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "",
    },
    "claude": {
        "provider": "claude",
        "provider_type": "claude",
        "display_name": "Claude",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "",
    },
    "siliconflow": {
        "provider": "siliconflow",
        "provider_type": "openai_compatible",
        "display_name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "",
    },
    "openrouter": {
        "provider": "openrouter",
        "provider_type": "openai_compatible",
        "display_name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "",
    },
    "xai": {
        "provider": "xai",
        "provider_type": "openai_compatible",
        "display_name": "xAI",
        "base_url": "https://api.x.ai/v1",
        "default_model": "",
    },
    "deepseek": {
        "provider": "deepseek",
        "provider_type": "openai_compatible",
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "",
    },
}
