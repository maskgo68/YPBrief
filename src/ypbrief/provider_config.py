from __future__ import annotations

from copy import copy
from typing import Any

from .config import Settings
from .database import Database
from .llm import ClaudeProvider, ConfigError, GeminiProvider, OpenAICompatibleProvider, SummaryProvider, create_provider
from .provider_defaults import BUILTIN_PROVIDER_DEFAULTS, normalize_provider as _normalize_provider_name


PROVIDER_ENV_KEYS: dict[str, dict[str, str]] = {
    "openai": {"api_key": "OPENAI_API_KEY", "base_url": "OPENAI_BASE_URL", "default_model": "OPENAI_MODEL"},
    "gemini": {"api_key": "GEMINI_API_KEY", "base_url": "GEMINI_BASE_URL", "default_model": "GEMINI_MODEL"},
    "claude": {"api_key": "ANTHROPIC_API_KEY", "base_url": "ANTHROPIC_BASE_URL", "default_model": "CLAUDE_MODEL"},
    "siliconflow": {"api_key": "SILICONFLOW_API_KEY", "base_url": "SILICONFLOW_BASE_URL", "default_model": "SILICONFLOW_MODEL"},
    "openrouter": {"api_key": "OPENROUTER_API_KEY", "base_url": "OPENROUTER_BASE_URL", "default_model": "OPENROUTER_MODEL"},
    "xai": {"api_key": "XAI_API_KEY", "base_url": "XAI_BASE_URL", "default_model": "XAI_MODEL"},
    "deepseek": {"api_key": "DEEPSEEK_API_KEY", "base_url": "DEEPSEEK_BASE_URL", "default_model": "DEEPSEEK_MODEL"},
    "custom_openai": {
        "api_key": "CUSTOM_OPENAI_API_KEY",
        "base_url": "CUSTOM_OPENAI_BASE_URL",
        "default_model": "CUSTOM_OPENAI_MODEL",
    },
}


PROVIDER_SETTINGS_FIELDS: dict[str, tuple[str, str, str]] = {
    "openai": ("openai_api_key", "openai_base_url", "openai_model"),
    "gemini": ("gemini_api_key", "gemini_base_url", "gemini_model"),
    "claude": ("anthropic_api_key", "anthropic_base_url", "claude_model"),
    "siliconflow": ("siliconflow_api_key", "siliconflow_base_url", "siliconflow_model"),
    "openrouter": ("openrouter_api_key", "openrouter_base_url", "openrouter_model"),
    "xai": ("xai_api_key", "xai_base_url", "xai_model"),
    "deepseek": ("deepseek_api_key", "deepseek_base_url", "deepseek_model"),
    "custom_openai": ("custom_openai_api_key", "custom_openai_base_url", "custom_openai_model"),
}


def create_provider_from_database(db: Database, settings: Settings) -> SummaryProvider:
    active = active_model(db)
    effective = copy(settings)
    if active:
        provider_name = normalize_provider(active["provider"])
        config = get_effective_provider_config(db, settings, provider_name)
        if config:
            return provider_from_config(config, active["model_name"])
        effective.llm_provider = provider_name
        effective.llm_model = active["model_name"]
    return create_provider(effective)


def active_model(db: Database) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM ModelProfiles WHERE is_active = 1 ORDER BY model_id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_effective_provider_config(db: Database, settings: Settings, provider: str) -> dict[str, Any] | None:
    provider = normalize_provider(provider)
    row = get_provider_config_row(db, provider)
    if row:
        defaults = env_provider_config(settings, provider) or {
            **BUILTIN_PROVIDER_DEFAULTS.get(provider, {}),
            "provider": provider,
            "enabled": 1,
            "notes": "",
            "source": "default",
            "is_builtin": provider in BUILTIN_PROVIDER_DEFAULTS,
        }
        row_values = {
            key: value
            for key, value in row.items()
            if value is not None and (value != "" or key == "default_model")
        }
        return {
            **defaults,
            **row_values,
            "provider": provider,
            "source": "database",
            "is_builtin": provider in BUILTIN_PROVIDER_DEFAULTS,
        }
    return env_provider_config(settings, provider)


def get_provider_config_row(db: Database, provider: str) -> dict[str, Any] | None:
    provider = normalize_provider(provider)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM LLMProviderConfigs WHERE provider = ?", (provider,)).fetchone()
    return dict(row) if row else None


def env_provider_config(settings: Settings, provider: str) -> dict[str, Any] | None:
    provider = normalize_provider(provider)
    keys = {
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
        "claude": settings.anthropic_api_key,
        "siliconflow": settings.siliconflow_api_key,
        "openrouter": settings.openrouter_api_key,
        "xai": settings.xai_api_key,
        "deepseek": settings.deepseek_api_key,
        "custom_openai": settings.custom_openai_api_key,
    }
    if provider not in keys:
        return None
    config = dict(
        BUILTIN_PROVIDER_DEFAULTS.get(
            provider,
            {
                "provider": provider,
                "provider_type": "openai_compatible",
                "display_name": provider,
                "base_url": "",
                "default_model": "",
            },
        )
    )
    config["api_key"] = keys[provider]
    env_overrides = {
        "openai": (settings.openai_base_url, settings.openai_model),
        "gemini": (settings.gemini_base_url, settings.gemini_model),
        "claude": (settings.anthropic_base_url, settings.claude_model),
        "siliconflow": (settings.siliconflow_base_url, settings.siliconflow_model),
        "openrouter": (settings.openrouter_base_url, settings.openrouter_model),
        "xai": (settings.xai_base_url, settings.xai_model),
        "deepseek": (settings.deepseek_base_url, settings.deepseek_model),
    }
    if provider == "custom_openai":
        config["base_url"] = settings.custom_openai_base_url
    else:
        override_base_url, override_model = env_overrides.get(provider, ("", ""))
        if override_base_url:
            config["base_url"] = override_base_url
    config["enabled"] = 1
    config["notes"] = ""
    config["source"] = "key.env"
    config["is_builtin"] = provider in BUILTIN_PROVIDER_DEFAULTS
    return config


def sync_provider_config_to_settings(settings: Settings, provider: str, config: dict[str, Any]) -> None:
    fields = PROVIDER_SETTINGS_FIELDS.get(normalize_provider(provider))
    if not fields:
        return
    api_key_field, base_url_field, model_field = fields
    if "api_key" in config:
        setattr(settings, api_key_field, str(config.get("api_key") or ""))
    if "base_url" in config:
        setattr(settings, base_url_field, str(config.get("base_url") or ""))
    if "default_model" in config:
        setattr(settings, model_field, str(config.get("default_model") or ""))


def provider_from_config(config: dict[str, Any], model_name: str) -> SummaryProvider:
    provider_type = config["provider_type"]
    provider_name = config["provider"]
    model = model_name or config.get("default_model") or ""
    api_key = config.get("api_key") or ""
    if provider_type == "gemini":
        if not api_key:
            raise ConfigError(f"API key is required for {provider_name}")
        if not model:
            raise ConfigError(f"Model is required for {provider_name}")
        return GeminiProvider(name=provider_name, api_key=api_key, model=model)
    if provider_type == "claude":
        if not api_key:
            raise ConfigError(f"API key is required for {provider_name}")
        if not model:
            raise ConfigError(f"Model is required for {provider_name}")
        return ClaudeProvider(name=provider_name, api_key=api_key, model=model)
    if provider_type == "openai_compatible":
        base_url = config.get("base_url") or ""
        if not api_key:
            raise ConfigError(f"API key is required for {provider_name}")
        if not base_url:
            raise ConfigError(f"Base URL is required for {provider_name}")
        if not model:
            raise ConfigError(f"Model is required for {provider_name}")
        return OpenAICompatibleProvider(name=provider_name, api_key=api_key, base_url=base_url, model=model)
    raise ConfigError(f"Unsupported provider type: {provider_type}")


def normalize_provider(provider: str) -> str:
    return _normalize_provider_name(provider)
