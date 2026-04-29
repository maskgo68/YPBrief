from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
import os
from pathlib import Path
import shutil
import sys
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ypbrief.config import Settings, load_settings
from ypbrief.daily import DailyDigestService, DigestRunService
from ypbrief.database import Database
from ypbrief.delivery import DeliveryService
from ypbrief.llm import ConfigError
from ypbrief.provider_config import create_provider_from_database
from ypbrief.sources import SourceService
from ypbrief.transcripts import TranscriptFetcher
from ypbrief.utils import as_bool
from ypbrief.video_processor import VideoProcessor
from ypbrief.youtube import YouTubeDataClient


WINDOW_DAYS = {
    "last_1": 1,
    "last_3": 3,
    "last_7": 7,
    "all_time": None,
}

ACTIONS_EXPORT_DIR = "actions-exports"

ENV_KEYS = [
    "YPBRIEF_ACCESS_PASSWORD",
    "YOUTUBE_DATA_API_KEY",
    "YOUTUBE_PROXY_ENABLED",
    "YOUTUBE_PROXY_HTTP",
    "YOUTUBE_PROXY_HTTPS",
    "IPROYAL_PROXY_HOST",
    "IPROYAL_PROXY_PORT",
    "IPROYAL_PROXY_USERNAME",
    "IPROYAL_PROXY_PASSWORD",
    "YT_DLP_COOKIES_FROM_BROWSER",
    "YT_DLP_PROXY",
    "YT_DLP_SLEEP_INTERVAL",
    "YT_DLP_MAX_SLEEP_INTERVAL",
    "YT_DLP_RETRIES",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_BASE_URL",
    "GEMINI_MODEL",
    "SILICONFLOW_API_KEY",
    "SILICONFLOW_BASE_URL",
    "SILICONFLOW_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_MODEL",
    "XAI_API_KEY",
    "XAI_BASE_URL",
    "XAI_MODEL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_MODEL",
    "CUSTOM_OPENAI_API_KEY",
    "CUSTOM_OPENAI_BASE_URL",
    "CUSTOM_OPENAI_MODEL",
    "TELEGRAM_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_PARSE_MODE",
    "TELEGRAM_SEND_AS_FILE_IF_TOO_LONG",
    "FEISHU_ENABLED",
    "FEISHU_WEBHOOK_URL",
    "FEISHU_SECRET",
    "EMAIL_ENABLED",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
    "EMAIL_FROM",
    "EMAIL_TO",
    "EMAIL_SUBJECT_TEMPLATE",
    "EMAIL_ATTACH_MARKDOWN",
]


@dataclass(frozen=True)
class ActionsConfig:
    run_date: str
    window: str = "last_1"
    group: str = "all"
    language: str = "zh"
    max_videos_per_source: int | None = 10
    dry_run: bool = False
    send_empty_digest: bool = True
    timezone: str = "Asia/Shanghai"

    @property
    def window_days(self) -> int | None:
        return WINDOW_DAYS[self.window]

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ActionsConfig":
        env = env or dict(os.environ)
        timezone = _pick(env, "TIMEZONE", "Asia/Shanghai")
        run_date = _pick(env, "RUN_DATE", "") or _default_run_date(timezone)
        window = _pick(env, "WINDOW", "last_1")
        if window not in WINDOW_DAYS:
            raise ValueError("window must be one of: last_1, last_3, last_7, all_time")
        language = _pick(env, "LANGUAGE", "zh")
        if language not in {"zh", "en"}:
            raise ValueError("language must be zh or en")
        return cls(
            run_date=run_date,
            window=window,
            group=_pick(env, "GROUP", "all").strip() or "all",
            language=language,
            max_videos_per_source=_parse_max_videos(_pick(env, "MAX_VIDEOS_PER_SOURCE", "10")),
            dry_run=_as_bool(_pick(env, "DRY_RUN", "false")),
            send_empty_digest=_as_bool(_pick(env, "SEND_EMPTY_DIGEST", "true")),
            timezone=timezone,
        )


def write_temp_env(root: Path, env: dict[str, str] | None = None) -> Path:
    env = env or dict(os.environ)
    root = Path(root)
    action_dir = root / ".ypbrief-actions"
    action_dir.mkdir(parents=True, exist_ok=True)
    env_file = action_dir / "key.env"
    values = {
        "YPBRIEF_DATA_DIR": str(action_dir),
        "YPBRIEF_DB_PATH": str(action_dir / "ypbrief.db"),
        "YPBRIEF_EXPORT_DIR": str(root / ACTIONS_EXPORT_DIR),
        "YPBRIEF_LOG_DIR": str(action_dir / "logs"),
        "YPBRIEF_PROMPT_FILE": str(root / "prompts.yaml"),
        "SCHEDULER_ENABLED": "false",
        "YOUTUBE_PROXY_ENABLED": env.get("YOUTUBE_PROXY_ENABLED") or "false",
    }
    for key in ENV_KEYS:
        if key in values:
            continue
        value = env.get(key)
        if value is not None:
            values[key] = value
    lines = [f"{key}={value}" for key, value in values.items()]
    env_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return env_file


def load_env_file_values(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_file.exists():
        raise FileNotFoundError(f"env file not found: {env_file}")
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


def merge_env_file_values(env: dict[str, str], env_file: Path | None) -> dict[str, str]:
    if env_file is None:
        return dict(env)
    file_values = load_env_file_values(env_file)
    return {**file_values, **env}


def sync_delivery_settings_from_env(db: Database, settings: Settings) -> dict:
    payload = {
        "telegram_enabled": as_bool(settings.telegram_enabled),
        "telegram_bot_token": settings.telegram_bot_token,
        "telegram_chat_id": settings.telegram_chat_id,
        "telegram_parse_mode": settings.telegram_parse_mode or "Markdown",
        "telegram_send_as_file_if_too_long": as_bool(settings.telegram_send_as_file_if_too_long),
        "feishu_enabled": as_bool(settings.feishu_enabled),
        "feishu_webhook_url": settings.feishu_webhook_url,
        "feishu_secret": settings.feishu_secret,
        "email_enabled": as_bool(settings.email_enabled),
        "smtp_host": settings.smtp_host,
        "smtp_port": int(settings.smtp_port or 587),
        "smtp_username": settings.smtp_username,
        "smtp_password": settings.smtp_password,
        "smtp_use_tls": as_bool(settings.smtp_use_tls),
        "smtp_use_ssl": as_bool(settings.smtp_use_ssl),
        "email_from": settings.email_from,
        "email_to": settings.email_to,
        "email_subject_template": settings.email_subject_template,
        "email_attach_markdown": as_bool(settings.email_attach_markdown),
    }
    return DeliveryService(db, settings).update_settings(payload)


def resolve_source_ids(db: Database, group: str) -> list[int]:
    normalized = (group or "all").strip()
    if normalized.lower() == "all":
        return [int(source["source_id"]) for source in db.list_sources(enabled_only=True)]
    groups = db.list_source_groups()
    matched = next((item for item in groups if item["group_name"] == normalized), None)
    if matched is None:
        raise ValueError(f"Source group not found: {normalized}")
    source_ids = [
        int(source["source_id"])
        for source in db.list_sources(enabled_only=True)
        if source.get("group_id") == matched["group_id"]
    ]
    if not source_ids:
        raise ValueError(f"Source group has no enabled sources: {normalized}")
    return source_ids


def prune_outputs(root: Path) -> None:
    root = Path(root)
    for pattern in [
        f"{ACTIONS_EXPORT_DIR}/videos/**/source.vtt",
        f"{ACTIONS_EXPORT_DIR}/videos/**/transcript.md",
        f"{ACTIONS_EXPORT_DIR}/videos/**/metadata.json",
    ]:
        for path in root.glob(pattern):
            if path.is_file():
                path.unlink()
    shutil.rmtree(root / ".ypbrief-actions", ignore_errors=True)


def git_add_allowlist_commands() -> list[str]:
    return [
        "git add -f sources.yaml",
        "git add -f prompts.yaml",
        f"git add -f {ACTIONS_EXPORT_DIR}/daily/**/*.md",
        f"git add -f {ACTIONS_EXPORT_DIR}/videos/**/summary.md",
    ]


def delivery_result_lines(deliveries: list[dict]) -> list[str]:
    lines = []
    for delivery in deliveries:
        channel = str(delivery.get("channel") or "unknown")
        status = str(delivery.get("status") or "unknown")
        target = _mask_target(str(delivery.get("target") or ""))
        line = f"delivery {channel} {status} target={target}"
        error = str(delivery.get("error_message") or "").strip()
        if error:
            line = f"{line} error={error}"
        lines.append(line)
    return lines


def is_failed_without_summary(run_result: dict) -> bool:
    return (
        not run_result.get("summary_id")
        and (
            run_result.get("status") == "failed"
            or int(run_result.get("failed_count") or 0) > 0
        )
    )


def is_no_updates(run_result: dict) -> bool:
    return (
        not run_result.get("summary_id")
        and int(run_result.get("included_count") or 0) == 0
        and int(run_result.get("failed_count") or 0) == 0
        and int(run_result.get("skipped_count") or 0) == 0
    )


def run(config: ActionsConfig, root: Path | None = None, env: dict[str, str] | None = None) -> dict:
    root = Path(root or Path.cwd())
    sources_path = root / "sources.yaml"
    if not sources_path.exists():
        raise FileNotFoundError("sources.yaml is required for GitHub Actions Lite")
    env_file = write_temp_env(root, env)
    try:
        settings = load_settings(env_file)
        db = Database(settings.db_path)
        db.initialize()
        sync_delivery_settings_from_env(db, settings)
        if not settings.youtube_data_api_key:
            raise RuntimeError("YOUTUBE_DATA_API_KEY is required")

        youtube = YouTubeDataClient(settings.youtube_data_api_key)
        source_service = SourceService(db=db, youtube=youtube)
        imported = source_service.import_yaml(sources_path)
        source_ids = resolve_source_ids(db, config.group)

        try:
            provider = create_provider_from_database(db, settings)
        except ConfigError as exc:
            raise RuntimeError(str(exc)) from exc
        processor = VideoProcessor.from_api_key(
            db=db,
            youtube_api_key=settings.youtube_data_api_key,
            transcripts=TranscriptFetcher.from_settings(settings),
            provider=provider,
            export_dir=settings.export_dir,
            settings=settings,
        )
        digest_service = DailyDigestService(db=db, provider=provider, export_dir=settings.export_dir, settings=settings)
        runner = DigestRunService(db=db, youtube=youtube, processor=processor, digest_service=digest_service)

        run_result = runner.run(
            source_ids=source_ids,
            run_date=config.run_date,
            window_days=config.window_days,
            max_videos_per_source=config.max_videos_per_source,
            reuse_existing_summaries=True,
            process_missing_videos=True,
            retry_failed_once=True,
            digest_language=config.language,
        )
        deliveries = []
        summary_id = run_result.get("summary_id")
        if summary_id and not config.dry_run:
            deliveries = DeliveryService(db, settings).send_summary(
                int(summary_id),
                run_id=int(run_result["run_id"]),
            )
        elif is_failed_without_summary(run_result) and not config.dry_run:
            deliveries = DeliveryService(db, settings).send_failure_notice(
                int(run_result["run_id"]),
                config.run_date,
                config.language,
            )
        elif is_no_updates(run_result) and config.send_empty_digest and not config.dry_run:
            deliveries = DeliveryService(db, settings).send_no_updates(
                config.run_date,
                config.language,
                run_id=int(run_result["run_id"]),
            )
        return {
            "imported_sources": imported,
            "source_ids": source_ids,
            "run": run_result,
            "deliveries": deliveries,
            "dry_run": config.dry_run,
        }
    finally:
        prune_outputs(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run YPBrief GitHub Actions Lite.")
    parser.add_argument("--run-date")
    parser.add_argument("--window", choices=sorted(WINDOW_DAYS))
    parser.add_argument("--group")
    parser.add_argument("--language", choices=["zh", "en"])
    parser.add_argument("--max-videos-per-source")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", type=Path, help="Load local key.env values for local dry-run testing.")
    args = parser.parse_args(argv)
    env = merge_env_file_values(dict(os.environ), args.env_file)
    for key, value in {
        "ACTION_INPUT_RUN_DATE": args.run_date,
        "ACTION_INPUT_WINDOW": args.window,
        "ACTION_INPUT_GROUP": args.group,
        "ACTION_INPUT_LANGUAGE": args.language,
        "ACTION_INPUT_MAX_VIDEOS_PER_SOURCE": args.max_videos_per_source,
    }.items():
        if value:
            env[key] = value
    if args.dry_run:
        env["ACTION_INPUT_DRY_RUN"] = "true"
    config = ActionsConfig.from_env(env)
    result = run(config, env=env)
    run_data = result["run"]
    print(
        "YPBrief Actions Lite completed: "
        f"status={run_data.get('status')} "
        f"included={run_data.get('included_count')} "
        f"failed={run_data.get('failed_count')} "
        f"skipped={run_data.get('skipped_count')} "
        f"dry_run={result['dry_run']}"
    )
    deliveries = result.get("deliveries") or []
    if deliveries:
        for line in delivery_result_lines(deliveries):
            print(line)
    elif not result["dry_run"]:
        print("delivery skipped no delivery channel reported a result")
    return 0


def _pick(env: dict[str, str], name: str, default: str) -> str:
    for key in (f"ACTION_INPUT_{name}", f"INPUT_{name}", f"YPBRIEF_ACTIONS_{name}"):
        if key in env:
            return str(env[key])
    return default


def _parse_max_videos(value: str) -> int | None:
    normalized = str(value).strip().lower()
    if normalized in {"all", "none", "0", "unlimited"}:
        return None
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise ValueError("max_videos_per_source must be a positive integer, 0, or all") from exc
    if parsed < 0:
        raise ValueError("max_videos_per_source must not be negative")
    return parsed


def _as_bool(value: str) -> bool:
    return as_bool(value)


def _default_run_date(timezone: str) -> str:
    tz = ZoneInfo(timezone)
    return (datetime.now(tz).date() - timedelta(days=1)).isoformat()


def _mask_target(value: str) -> str:
    value = value.strip()
    if not value:
        return "***"
    if len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


if __name__ == "__main__":
    raise SystemExit(main())
