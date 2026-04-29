from pathlib import Path

from ypbrief.config import Settings, _parse_env_file, load_settings


def test_load_settings_reads_key_env_and_runtime_paths(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "YOUTUBE_DATA_API_KEY=yt-key",
                "LLM_PROVIDER=openrouter",
                "LLM_MODEL=openrouter-model",
                "OPENROUTER_API_KEY=or-key",
                "YPBRIEF_ACCESS_PASSWORD=12345678901234567890123456789012",
                "YPBRIEF_DATA_DIR=./local-data",
                "YPBRIEF_DB_PATH=./local-data/test.db",
                "YPBRIEF_EXPORT_DIR=./local-exports",
                "YPBRIEF_LOG_DIR=./local-logs",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert isinstance(settings, Settings)
    assert settings.youtube_data_api_key == "yt-key"
    assert settings.llm_provider == "openrouter"
    assert settings.llm_model == "openrouter-model"
    assert settings.openrouter_api_key == "or-key"
    assert settings.access_password == "12345678901234567890123456789012"
    assert settings.data_dir == tmp_path / "local-data"
    assert settings.db_path == tmp_path / "local-data" / "test.db"
    assert settings.export_dir == tmp_path / "local-exports"
    assert settings.log_dir == tmp_path / "local-logs"


def test_load_settings_ignores_comments_and_preserves_empty_values(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "LLM_PROVIDER=gemini",
                "GEMINI_API_KEY=",
                "CUSTOM_OPENAI_BASE_URL=https://example.test/v1",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key == ""
    assert settings.custom_openai_base_url == "https://example.test/v1"


def test_parse_env_file_ignores_empty_keys(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("=\nLLM_PROVIDER=gemini\n", encoding="utf-8")

    values = _parse_env_file(env_file)

    assert "" not in values
    assert values["LLM_PROVIDER"] == "gemini"


def test_load_settings_does_not_let_empty_os_env_override_file_values(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("GEMINI_API_KEY=file-key\nLLM_PROVIDER=gemini\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    settings = load_settings(env_file)

    assert settings.gemini_api_key == "file-key"


def test_load_settings_reads_provider_base_urls_and_models(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://api.openai.example/v1",
                "OPENAI_MODEL=gpt-4.1-custom",
                "GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta",
                "GEMINI_MODEL=gemini-2.5-pro",
                "ANTHROPIC_BASE_URL=https://api.anthropic.com/v1",
                "CLAUDE_MODEL=claude-3-7-sonnet-latest",
                "SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1",
                "SILICONFLOW_MODEL=Qwen/Qwen2.5-72B-Instruct",
                "XAI_BASE_URL=https://api.x.ai/v1",
                "XAI_MODEL=grok-4",
                "DEEPSEEK_BASE_URL=https://api.deepseek.com/v1",
                "DEEPSEEK_MODEL=deepseek-chat",
                "OPENROUTER_BASE_URL=https://openrouter.ai/api/v1",
                "OPENROUTER_MODEL=openai/gpt-4.1",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.openai_base_url == "https://api.openai.example/v1"
    assert settings.openai_model == "gpt-4.1-custom"
    assert settings.gemini_base_url == "https://generativelanguage.googleapis.com/v1beta"
    assert settings.gemini_model == "gemini-2.5-pro"
    assert settings.anthropic_base_url == "https://api.anthropic.com/v1"
    assert settings.claude_model == "claude-3-7-sonnet-latest"
    assert settings.siliconflow_base_url == "https://api.siliconflow.cn/v1"
    assert settings.siliconflow_model == "Qwen/Qwen2.5-72B-Instruct"
    assert settings.xai_base_url == "https://api.x.ai/v1"
    assert settings.xai_model == "grok-4"
    assert settings.deepseek_base_url == "https://api.deepseek.com/v1"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.openrouter_model == "openai/gpt-4.1"


def test_load_settings_builds_iproyal_proxy_urls(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "YOUTUBE_PROXY_ENABLED=true",
                "IPROYAL_PROXY_HOST=geo.iproyal.com",
                "IPROYAL_PROXY_PORT=12321",
                "IPROYAL_PROXY_USERNAME=user-token",
                "IPROYAL_PROXY_PASSWORD=pass-token_country-us_city-losangeles",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.iproyal_proxy_url == (
        "http://user-token:pass-token_country-us_city-losangeles@geo.iproyal.com:12321"
    )
    assert settings.youtube_proxy_url == settings.iproyal_proxy_url
    assert settings.requests_proxies == {
        "http": settings.iproyal_proxy_url,
        "https": settings.iproyal_proxy_url,
    }


def test_load_settings_keeps_proxy_disabled_by_default(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "IPROYAL_PROXY_HOST=geo.iproyal.com",
                "IPROYAL_PROXY_PORT=12321",
                "IPROYAL_PROXY_USERNAME=user-token",
                "IPROYAL_PROXY_PASSWORD=pass-token",
                "YT_DLP_PROXY=http://explicit.example.test:8080",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.proxy_enabled is False
    assert settings.youtube_proxy_url == ""
    assert settings.requests_proxies is None
    assert settings.yt_dlp_proxy_url == ""


def test_proxy_enabled_treats_empty_and_none_like_false() -> None:
    assert Settings(youtube_proxy_enabled="").proxy_enabled is False
    assert Settings(youtube_proxy_enabled="none").proxy_enabled is False


def test_load_settings_can_disable_proxy_with_switch(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "YOUTUBE_PROXY_ENABLED=false",
                "IPROYAL_PROXY_HOST=geo.iproyal.com",
                "IPROYAL_PROXY_PORT=12321",
                "IPROYAL_PROXY_USERNAME=user-token",
                "IPROYAL_PROXY_PASSWORD=pass-token",
                "YT_DLP_PROXY=http://explicit.example.test:8080",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.youtube_proxy_url == ""
    assert settings.requests_proxies is None
    assert settings.yt_dlp_proxy_url == ""
