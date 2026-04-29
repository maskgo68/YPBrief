from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

import pytest

from ypbrief.config import load_settings
from ypbrief.database import Database
from ypbrief.delivery import DeliveryService

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("github_actions_daily", ROOT / "scripts" / "github_actions_daily.py")
assert SPEC and SPEC.loader
actions_daily = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = actions_daily
SPEC.loader.exec_module(actions_daily)


def test_config_uses_inputs_over_variables_and_parses_window() -> None:
    config = actions_daily.ActionsConfig.from_env(
        {
            "YPBRIEF_ACTIONS_WINDOW": "last_7",
            "YPBRIEF_ACTIONS_GROUP": "invest",
            "YPBRIEF_ACTIONS_LANGUAGE": "en",
            "YPBRIEF_ACTIONS_MAX_VIDEOS_PER_SOURCE": "all",
            "YPBRIEF_ACTIONS_DRY_RUN": "false",
            "ACTION_INPUT_WINDOW": "last_3",
            "ACTION_INPUT_DRY_RUN": "true",
            "ACTION_INPUT_RUN_DATE": "2026-04-28",
        }
    )

    assert config.window == "last_3"
    assert config.window_days == 3
    assert config.group == "invest"
    assert config.language == "en"
    assert config.max_videos_per_source is None
    assert config.dry_run is True
    assert config.run_date == "2026-04-28"


@pytest.mark.parametrize("window", ["last_2", "", "yesterday"])
def test_config_rejects_invalid_window(window: str) -> None:
    with pytest.raises(ValueError, match="window"):
        actions_daily.ActionsConfig.from_env({"ACTION_INPUT_WINDOW": window, "ACTION_INPUT_RUN_DATE": "2026-04-28"})


def test_write_temp_env_keeps_secrets_in_actions_dir(tmp_path: Path) -> None:
    env_file = actions_daily.write_temp_env(
        tmp_path,
        {
            "YOUTUBE_DATA_API_KEY": "yt-key",
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "gemini-key",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_CHAT_ID": "123",
        },
    )

    text = env_file.read_text(encoding="utf-8")
    assert env_file == tmp_path / ".ypbrief-actions" / "key.env"
    assert f"YPBRIEF_DB_PATH={tmp_path / '.ypbrief-actions' / 'ypbrief.db'}" in text
    assert f"YPBRIEF_EXPORT_DIR={tmp_path / 'actions-exports'}" in text
    assert "YOUTUBE_DATA_API_KEY=yt-key" in text
    assert "GEMINI_API_KEY=gemini-key" in text
    assert "YOUTUBE_PROXY_ENABLED=false" in text


def test_load_env_file_values_reads_local_key_env(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "# local test config",
                "YOUTUBE_DATA_API_KEY=yt-from-file",
                "LLM_PROVIDER='gemini'",
                'GEMINI_API_KEY="gemini-from-file"',
                "INVALID_LINE",
                "=ignored",
            ]
        ),
        encoding="utf-8",
    )

    values = actions_daily.load_env_file_values(env_file)

    assert values["YOUTUBE_DATA_API_KEY"] == "yt-from-file"
    assert values["LLM_PROVIDER"] == "gemini"
    assert values["GEMINI_API_KEY"] == "gemini-from-file"
    assert "INVALID_LINE" not in values
    assert "" not in values


def test_merge_env_file_values_keeps_process_env_priority(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "YOUTUBE_DATA_API_KEY=yt-from-file",
                "LLM_PROVIDER=gemini",
                "GEMINI_API_KEY=gemini-from-file",
            ]
        ),
        encoding="utf-8",
    )

    values = actions_daily.merge_env_file_values(
        {
            "YOUTUBE_DATA_API_KEY": "yt-from-env",
            "ACTION_INPUT_WINDOW": "last_3",
        },
        env_file,
    )

    assert values["YOUTUBE_DATA_API_KEY"] == "yt-from-env"
    assert values["LLM_PROVIDER"] == "gemini"
    assert values["GEMINI_API_KEY"] == "gemini-from-file"
    assert values["ACTION_INPUT_WINDOW"] == "last_3"


def test_sync_delivery_settings_from_env_enables_delivery(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "TELEGRAM_ENABLED=true",
                "TELEGRAM_BOT_TOKEN=123456:secret",
                "TELEGRAM_CHAT_ID=1234567890",
                "FEISHU_ENABLED=true",
                "FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/test-token",
                "FEISHU_SECRET=sign-secret",
                "EMAIL_ENABLED=true",
                "SMTP_HOST=smtp.example.test",
                "SMTP_PORT=587",
                "SMTP_USERNAME=user",
                "SMTP_PASSWORD=pass",
                "EMAIL_FROM=from@example.test",
                "EMAIL_TO=to@example.test,team@example.test",
            ]
        ),
        encoding="utf-8",
    )
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    settings = load_settings(env_file)

    actions_daily.sync_delivery_settings_from_env(db, settings)
    delivery = DeliveryService(db, settings).get_settings()

    assert delivery["telegram_enabled"] is True
    assert delivery["telegram_bot_token_configured"] is True
    assert delivery["feishu_enabled"] is True
    assert delivery["feishu_webhook_url_configured"] is True
    assert delivery["feishu_secret_configured"] is True
    assert delivery["email_enabled"] is True
    assert delivery["email_to"] == ["to@example.test", "team@example.test"]


def test_resolve_source_ids_supports_all_and_single_group(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    invest = db.save_source_group(group_name="invest", display_name="Invest")
    tech = db.save_source_group(group_name="tech", display_name="Tech")
    first = db.upsert_source(
        source_type="channel",
        source_name="Invest Channel",
        youtube_id="UCINVEST",
        url="https://www.youtube.com/channel/UCINVEST",
    )
    db.update_source(first, group_id=invest["group_id"])
    disabled = db.upsert_source(
        source_type="channel",
        source_name="Disabled Invest",
        youtube_id="UCDISABLED",
        url="https://www.youtube.com/channel/UCDISABLED",
        enabled=False,
    )
    db.update_source(disabled, group_id=invest["group_id"])
    second = db.upsert_source(
        source_type="playlist",
        source_name="Tech Playlist",
        youtube_id="PLTECH",
        url="https://www.youtube.com/playlist?list=PLTECH",
    )
    db.update_source(second, group_id=tech["group_id"])

    assert actions_daily.resolve_source_ids(db, "all") == [first, second]
    assert actions_daily.resolve_source_ids(db, "invest") == [first]


def test_resolve_source_ids_fails_for_missing_group(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()

    with pytest.raises(ValueError, match="Source group not found"):
        actions_daily.resolve_source_ids(db, "missing")


def test_prune_outputs_keeps_only_allowed_markdown(tmp_path: Path) -> None:
    exports = tmp_path / "actions-exports"
    video_dir = exports / "videos" / "Channel" / "2026-04-28 - vid1 - Title"
    daily_dir = exports / "daily" / "2026-04-28"
    video_dir.mkdir(parents=True)
    daily_dir.mkdir(parents=True)
    keep_summary = video_dir / "summary.md"
    keep_daily = daily_dir / "daily-summary.md"
    keep_videos = daily_dir / "videos.md"
    keep_failed = daily_dir / "failed.md"
    for path in [keep_summary, keep_daily, keep_videos, keep_failed]:
        path.write_text("ok", encoding="utf-8")
    for name in ["source.vtt", "transcript.md", "metadata.json"]:
        (video_dir / name).write_text("remove", encoding="utf-8")
    work_dir = tmp_path / ".ypbrief-actions"
    work_dir.mkdir()
    (work_dir / "key.env").write_text("SECRET=value", encoding="utf-8")

    actions_daily.prune_outputs(tmp_path)

    assert keep_summary.exists()
    assert keep_daily.exists()
    assert keep_videos.exists()
    assert keep_failed.exists()
    assert not (video_dir / "source.vtt").exists()
    assert not (video_dir / "transcript.md").exists()
    assert not (video_dir / "metadata.json").exists()
    assert not work_dir.exists()


def test_allowed_git_add_paths_are_force_added() -> None:
    commands = actions_daily.git_add_allowlist_commands()

    assert "git add -f sources.yaml" in commands
    assert "git add -f prompts.yaml" in commands
    assert "git add -f actions-exports/daily/**/*.md" in commands
    assert "git add -f actions-exports/videos/**/summary.md" in commands


def test_delivery_result_lines_mask_target_and_include_failure_detail() -> None:
    lines = actions_daily.delivery_result_lines(
        [
            {
                "channel": "telegram",
                "status": "failed",
                "target": "123456789",
                "error_message": "Bad Request: chat not found",
            },
            {
                "channel": "email",
                "status": "success",
                "target": "person@example.test",
                "error_message": None,
            },
        ]
    )

    assert lines == [
        "delivery telegram failed target=***6789 error=Bad Request: chat not found",
        "delivery email success target=***test",
    ]


def test_delivery_notice_classification_prioritizes_failures_over_no_updates() -> None:
    assert actions_daily.is_failed_without_summary(
        {"summary_id": None, "status": "failed", "included_count": 0, "failed_count": 1, "skipped_count": 0}
    )
    assert not actions_daily.is_no_updates(
        {"summary_id": None, "status": "failed", "included_count": 0, "failed_count": 1, "skipped_count": 0}
    )
    assert actions_daily.is_no_updates(
        {"summary_id": None, "status": "failed", "included_count": 0, "failed_count": 0, "skipped_count": 0}
    )
