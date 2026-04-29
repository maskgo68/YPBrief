import pytest

from ypbrief.config import Settings
from ypbrief.llm import ConfigError, OpenAICompatibleProvider, create_provider


def test_create_provider_supports_openai_compatible_routes() -> None:
    settings = Settings(
        llm_provider="siliconflow",
        siliconflow_api_key="sf-key",
        llm_model="Qwen/Qwen3",
    )

    provider = create_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "siliconflow"
    assert provider.base_url == "https://api.siliconflow.cn/v1"
    assert provider.api_key == "sf-key"
    assert provider.model == "Qwen/Qwen3"


def test_create_provider_supports_custom_openai_provider() -> None:
    settings = Settings(
        llm_provider="custom_openai",
        custom_openai_api_key="custom-key",
        custom_openai_base_url="https://llm.example.test/v1",
        custom_openai_model="custom-model",
    )

    provider = create_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "custom_openai"
    assert provider.base_url == "https://llm.example.test/v1"
    assert provider.model == "custom-model"


def test_create_provider_raises_helpful_error_when_key_missing() -> None:
    settings = Settings(llm_provider="openrouter")

    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        create_provider(settings)


def test_create_provider_requires_explicit_model_even_with_default_base_url() -> None:
    settings = Settings(llm_provider="openai", openai_api_key="openai-key")

    with pytest.raises(ConfigError, match="Model is required for openai"):
        create_provider(settings)


def test_create_provider_requires_explicit_gemini_model() -> None:
    settings = Settings(llm_provider="gemini", gemini_api_key="gemini-key")

    with pytest.raises(ConfigError, match="Model is required for gemini"):
        create_provider(settings)


def test_create_provider_uses_env_specific_openai_base_url_and_model() -> None:
    settings = Settings(
        llm_provider="openai",
        openai_api_key="openai-key",
        openai_base_url="https://api.openai.example/v1",
        openai_model="gpt-4.1-custom",
    )

    provider = create_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "openai"
    assert provider.base_url == "https://api.openai.example/v1"
    assert provider.model == "gpt-4.1-custom"


def test_create_provider_uses_env_specific_xai_base_url_and_model() -> None:
    settings = Settings(
        llm_provider="xai",
        xai_api_key="xai-key",
        xai_base_url="https://api.x.ai/v1",
        xai_model="grok-4.1",
    )

    provider = create_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "xai"
    assert provider.base_url == "https://api.x.ai/v1"
    assert provider.model == "grok-4.1"
