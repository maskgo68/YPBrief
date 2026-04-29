from pathlib import Path

from ypbrief.config import Settings
from ypbrief.database import Database
from ypbrief.llm import OpenAICompatibleProvider
from ypbrief.provider_config import (
    BUILTIN_PROVIDER_DEFAULTS,
    PROVIDER_ENV_KEYS,
    env_provider_config,
    create_provider_from_database,
    get_effective_provider_config,
    normalize_provider,
)


def test_create_provider_from_database_prefers_active_model_database_config(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO LLMProviderConfigs(provider, provider_type, display_name, base_url, api_key, default_model, enabled)
            VALUES ('xai', 'openai_compatible', 'xAI', 'https://api.x.ai/v1', 'xai-db-key', 'grok-4', 1)
            """
        )
        conn.execute(
            """
            INSERT INTO ModelProfiles(provider, model_name, display_name, is_active)
            VALUES ('xai', 'grok-4.20-0309-non-reasoning', 'xAI current', 1)
            """
        )

    provider = create_provider_from_database(db, Settings(llm_provider="xai", llm_model="grok-4.20-0309-non-reasoning"))

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "xai"
    assert provider.api_key == "xai-db-key"
    assert provider.base_url == "https://api.x.ai/v1"
    assert provider.model == "grok-4.20-0309-non-reasoning"


def test_normalize_provider_unifies_spaces_and_hyphens() -> None:
    assert normalize_provider("custom-openai") == "custom_openai"
    assert normalize_provider("test gateway") == "test_gateway"
    assert normalize_provider("DeepSeek") == "deepseek"
    assert normalize_provider("xAI") == "xai"


def test_effective_provider_config_exposes_builtin_default_urls(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()

    gemini = get_effective_provider_config(db, Settings(gemini_api_key="test-key"), "gemini")
    claude = get_effective_provider_config(db, Settings(anthropic_api_key="test-key"), "claude")

    assert gemini is not None
    assert claude is not None
    assert gemini["base_url"] == "https://generativelanguage.googleapis.com/v1beta"
    assert claude["base_url"] == "https://api.anthropic.com/v1"
    assert gemini["default_model"] == ""
    assert claude["default_model"] == ""
    assert BUILTIN_PROVIDER_DEFAULTS["gemini"]["base_url"] == "https://generativelanguage.googleapis.com/v1beta"
    assert BUILTIN_PROVIDER_DEFAULTS["gemini"]["default_model"] == ""


def test_initialize_clears_legacy_builtin_default_models(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO LLMProviderConfigs(provider, provider_type, display_name, base_url, api_key, default_model, enabled)
            VALUES ('xai', 'openai_compatible', 'xAI', 'https://api.x.ai/v1', 'xai-key', 'grok-4', 1)
            """
        )

    db.initialize()

    xai = get_effective_provider_config(db, Settings(xai_api_key="xai-key"), "xai")
    assert xai is not None
    assert xai["default_model"] == ""


def test_provider_env_key_map_includes_supported_providers() -> None:
    assert PROVIDER_ENV_KEYS["gemini"]["api_key"] == "GEMINI_API_KEY"
    assert PROVIDER_ENV_KEYS["xai"]["api_key"] == "XAI_API_KEY"
    assert PROVIDER_ENV_KEYS["deepseek"]["base_url"] == "DEEPSEEK_BASE_URL"
    assert set(PROVIDER_ENV_KEYS).issuperset(BUILTIN_PROVIDER_DEFAULTS)


def test_env_provider_config_prefers_env_specific_base_url_without_exposing_model_as_default() -> None:
    openai = env_provider_config(
        Settings(
            llm_provider="openai",
            openai_api_key="openai-key",
            openai_base_url="https://api.openai.example/v1",
            openai_model="gpt-4.1-custom",
        ),
        "openai",
    )
    claude = env_provider_config(
        Settings(
            llm_provider="claude",
            anthropic_api_key="anthropic-key",
            anthropic_base_url="https://api.anthropic.com/v1",
            claude_model="claude-3-7-sonnet-latest",
        ),
        "claude",
    )

    assert openai is not None
    assert openai["base_url"] == "https://api.openai.example/v1"
    assert openai["default_model"] == ""
    assert claude is not None
    assert claude["base_url"] == "https://api.anthropic.com/v1"
    assert claude["default_model"] == ""


def test_env_provider_config_supports_other_openai_compatible_env_overrides() -> None:
    xai = env_provider_config(
        Settings(
            llm_provider="xai",
            xai_api_key="xai-key",
            xai_base_url="https://api.x.ai/v1",
            xai_model="grok-4.1",
        ),
        "xai",
    )
    deepseek = env_provider_config(
        Settings(
            llm_provider="deepseek",
            deepseek_api_key="deepseek-key",
            deepseek_base_url="https://api.deepseek.com/v1",
            deepseek_model="deepseek-reasoner",
        ),
        "deepseek",
    )

    assert xai is not None
    assert xai["base_url"] == "https://api.x.ai/v1"
    assert xai["default_model"] == ""
    assert deepseek is not None
    assert deepseek["base_url"] == "https://api.deepseek.com/v1"
    assert deepseek["default_model"] == ""
