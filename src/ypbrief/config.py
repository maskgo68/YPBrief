from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .utils import as_bool


def _resolve_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


@dataclass
class Settings:
    access_password: str = ""
    youtube_data_api_key: str = ""
    llm_provider: str = "gemini"
    llm_model: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    gemini_api_key: str = ""
    gemini_base_url: str = ""
    gemini_model: str = ""
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = ""
    siliconflow_model: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    claude_model: str = ""
    xai_api_key: str = ""
    xai_base_url: str = ""
    xai_model: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = ""
    deepseek_model: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = ""
    openrouter_model: str = ""
    custom_openai_api_key: str = ""
    custom_openai_base_url: str = ""
    custom_openai_model: str = ""
    youtube_proxy_enabled: str = "false"
    youtube_proxy_http: str = ""
    youtube_proxy_https: str = ""
    iproyal_proxy_host: str = ""
    iproyal_proxy_port: str = ""
    iproyal_proxy_username: str = ""
    iproyal_proxy_password: str = ""
    yt_dlp_cookies_file: str = ""
    yt_dlp_cookies_from_browser: str = ""
    yt_dlp_proxy: str = ""
    yt_dlp_sleep_interval: str = "2"
    yt_dlp_max_sleep_interval: str = "8"
    yt_dlp_retries: str = "3"
    scheduler_enabled: str = "false"
    scheduler_timezone: str = "Asia/Shanghai"
    scheduler_run_time: str = "07:00"
    scheduler_digest_language: str = "zh"
    scheduler_source_scope: str = "all_enabled"
    scheduler_source_ids: str = ""
    scheduler_max_videos_per_source: str = "10"
    scheduler_send_empty_digest: str = "true"
    telegram_enabled: str = "false"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_parse_mode: str = "Markdown"
    telegram_send_as_file_if_too_long: str = "true"
    telegram_bot_inbox_enabled: str = "false"
    telegram_bot_webhook_secret: str = ""
    telegram_bot_header_secret: str = ""
    telegram_bot_allowed_chat_ids: str = ""
    telegram_bot_allowed_user_ids: str = ""
    telegram_bot_public_base_url: str = ""
    telegram_bot_max_links_per_message: str = "1"
    telegram_bot_reuse_existing_summary: str = "true"
    email_enabled: str = "false"
    smtp_host: str = ""
    smtp_port: str = "587"
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: str = "true"
    smtp_use_ssl: str = "false"
    email_from: str = ""
    email_to: str = ""
    email_subject_template: str = "YPBrief 每日播客日报 - {{ run_date }}"
    email_attach_markdown: str = "true"
    data_dir: Path | str = Path("./data")
    db_path: Path | str = Path("./data/ypbrief.db")
    export_dir: Path | str = Path("./exports")
    log_dir: Path | str = Path("./logs")
    prompt_file: Path | str = Path("./prompts.yaml")

    def with_base_dir(self, base_dir: Path) -> "Settings":
        self.data_dir = _resolve_path(self.data_dir, base_dir)
        self.db_path = _resolve_path(self.db_path, base_dir)
        self.export_dir = _resolve_path(self.export_dir, base_dir)
        self.log_dir = _resolve_path(self.log_dir, base_dir)
        self.prompt_file = _resolve_path(self.prompt_file, base_dir)
        if self.yt_dlp_cookies_file:
            self.yt_dlp_cookies_file = str(_resolve_path(self.yt_dlp_cookies_file, base_dir))
        return self

    @property
    def proxy_enabled(self) -> bool:
        return as_bool(self.youtube_proxy_enabled)

    @property
    def iproyal_proxy_url(self) -> str:
        if not all(
            [
                self.iproyal_proxy_host,
                self.iproyal_proxy_port,
                self.iproyal_proxy_username,
                self.iproyal_proxy_password,
            ]
        ):
            return ""
        username = quote(self.iproyal_proxy_username, safe="")
        password = quote(self.iproyal_proxy_password, safe="")
        return f"http://{username}:{password}@{self.iproyal_proxy_host}:{self.iproyal_proxy_port}"

    @property
    def youtube_proxy_url(self) -> str:
        if not self.proxy_enabled:
            return ""
        return self.youtube_proxy_https or self.youtube_proxy_http or self.iproyal_proxy_url

    @property
    def requests_proxies(self) -> dict[str, str] | None:
        proxy_url = self.youtube_proxy_url
        if not proxy_url:
            return None
        return {
            "http": self.youtube_proxy_http or proxy_url,
            "https": self.youtube_proxy_https or proxy_url,
        }

    @property
    def yt_dlp_proxy_url(self) -> str:
        if not self.proxy_enabled:
            return ""
        return self.yt_dlp_proxy or self.youtube_proxy_url


_ENV_TO_FIELD = {
    "YPBRIEF_ACCESS_PASSWORD": "access_password",
    "YOUTUBE_DATA_API_KEY": "youtube_data_api_key",
    "LLM_PROVIDER": "llm_provider",
    "LLM_MODEL": "llm_model",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "OPENAI_MODEL": "openai_model",
    "GEMINI_API_KEY": "gemini_api_key",
    "GEMINI_BASE_URL": "gemini_base_url",
    "GEMINI_MODEL": "gemini_model",
    "SILICONFLOW_API_KEY": "siliconflow_api_key",
    "SILICONFLOW_BASE_URL": "siliconflow_base_url",
    "SILICONFLOW_MODEL": "siliconflow_model",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "ANTHROPIC_BASE_URL": "anthropic_base_url",
    "CLAUDE_MODEL": "claude_model",
    "XAI_API_KEY": "xai_api_key",
    "XAI_BASE_URL": "xai_base_url",
    "XAI_MODEL": "xai_model",
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "DEEPSEEK_BASE_URL": "deepseek_base_url",
    "DEEPSEEK_MODEL": "deepseek_model",
    "OPENROUTER_API_KEY": "openrouter_api_key",
    "OPENROUTER_BASE_URL": "openrouter_base_url",
    "OPENROUTER_MODEL": "openrouter_model",
    "CUSTOM_OPENAI_API_KEY": "custom_openai_api_key",
    "CUSTOM_OPENAI_BASE_URL": "custom_openai_base_url",
    "CUSTOM_OPENAI_MODEL": "custom_openai_model",
    "YOUTUBE_PROXY_ENABLED": "youtube_proxy_enabled",
    "YOUTUBE_PROXY_HTTP": "youtube_proxy_http",
    "YOUTUBE_PROXY_HTTPS": "youtube_proxy_https",
    "IPROYAL_PROXY_HOST": "iproyal_proxy_host",
    "IPROYAL_PROXY_PORT": "iproyal_proxy_port",
    "IPROYAL_PROXY_USERNAME": "iproyal_proxy_username",
    "IPROYAL_PROXY_PASSWORD": "iproyal_proxy_password",
    "YT_DLP_COOKIES_FILE": "yt_dlp_cookies_file",
    "YT_DLP_COOKIES_FROM_BROWSER": "yt_dlp_cookies_from_browser",
    "YT_DLP_PROXY": "yt_dlp_proxy",
    "YT_DLP_SLEEP_INTERVAL": "yt_dlp_sleep_interval",
    "YT_DLP_MAX_SLEEP_INTERVAL": "yt_dlp_max_sleep_interval",
    "YT_DLP_RETRIES": "yt_dlp_retries",
    "SCHEDULER_ENABLED": "scheduler_enabled",
    "SCHEDULER_TIMEZONE": "scheduler_timezone",
    "SCHEDULER_RUN_TIME": "scheduler_run_time",
    "SCHEDULER_DIGEST_LANGUAGE": "scheduler_digest_language",
    "SCHEDULER_SOURCE_SCOPE": "scheduler_source_scope",
    "SCHEDULER_SOURCE_IDS": "scheduler_source_ids",
    "SCHEDULER_MAX_VIDEOS_PER_SOURCE": "scheduler_max_videos_per_source",
    "SCHEDULER_SEND_EMPTY_DIGEST": "scheduler_send_empty_digest",
    "TELEGRAM_ENABLED": "telegram_enabled",
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
    "TELEGRAM_PARSE_MODE": "telegram_parse_mode",
    "TELEGRAM_SEND_AS_FILE_IF_TOO_LONG": "telegram_send_as_file_if_too_long",
    "TELEGRAM_BOT_INBOX_ENABLED": "telegram_bot_inbox_enabled",
    "TELEGRAM_BOT_WEBHOOK_SECRET": "telegram_bot_webhook_secret",
    "TELEGRAM_BOT_HEADER_SECRET": "telegram_bot_header_secret",
    "TELEGRAM_BOT_ALLOWED_CHAT_IDS": "telegram_bot_allowed_chat_ids",
    "TELEGRAM_BOT_ALLOWED_USER_IDS": "telegram_bot_allowed_user_ids",
    "TELEGRAM_BOT_PUBLIC_BASE_URL": "telegram_bot_public_base_url",
    "TELEGRAM_BOT_MAX_LINKS_PER_MESSAGE": "telegram_bot_max_links_per_message",
    "TELEGRAM_BOT_REUSE_EXISTING_SUMMARY": "telegram_bot_reuse_existing_summary",
    "EMAIL_ENABLED": "email_enabled",
    "SMTP_HOST": "smtp_host",
    "SMTP_PORT": "smtp_port",
    "SMTP_USERNAME": "smtp_username",
    "SMTP_PASSWORD": "smtp_password",
    "SMTP_USE_TLS": "smtp_use_tls",
    "SMTP_USE_SSL": "smtp_use_ssl",
    "EMAIL_FROM": "email_from",
    "EMAIL_TO": "email_to",
    "EMAIL_SUBJECT_TEMPLATE": "email_subject_template",
    "EMAIL_ATTACH_MARKDOWN": "email_attach_markdown",
    "YPBRIEF_DATA_DIR": "data_dir",
    "YPBRIEF_DB_PATH": "db_path",
    "YPBRIEF_EXPORT_DIR": "export_dir",
    "YPBRIEF_LOG_DIR": "log_dir",
    "YPBRIEF_PROMPT_FILE": "prompt_file",
}

def _parse_env_file(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_file.exists():
        return values

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def load_settings(env_file: str | Path = "key.env") -> Settings:
    env_path = Path(env_file)
    base_dir = env_path.resolve().parent if env_path.exists() else Path.cwd()
    file_values = _parse_env_file(env_path)

    settings_kwargs: dict[str, str] = {}
    for env_key, field_name in _ENV_TO_FIELD.items():
        if env_key in file_values:
            settings_kwargs[field_name] = file_values[env_key]
        if env_key in os.environ and os.environ[env_key]:
            settings_kwargs[field_name] = os.environ[env_key]

    return Settings(**settings_kwargs).with_base_dir(base_dir)
