from pathlib import Path

from click.testing import CliRunner

import ypbrief.cli as cli_module
from ypbrief.cleaner import TranscriptSegment
from ypbrief.cli import cli
from ypbrief.database import Database
from ypbrief.youtube import ChannelInfo


def test_cli_init_db_uses_key_env_paths(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    db_path = tmp_path / "data" / "cli.db"
    env_file.write_text(f"YPBRIEF_DB_PATH={db_path}\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["--env-file", str(env_file), "init-db"])

    assert result.exit_code == 0
    assert db_path.exists()
    assert "Initialized database" in result.output


def test_cli_search_prints_database_matches(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "cli.db"
    db = Database(db_path)
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )
    env_file = tmp_path / "key.env"
    env_file.write_text(f"YPBRIEF_DB_PATH={db_path}\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["--env-file", str(env_file), "search", "hello"])

    assert result.exit_code == 0
    assert "Episode 1" in result.output
    assert "hello world" in result.output


def test_cli_channel_list_prints_saved_channels(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "cli.db"
    db = Database(db_path)
    db.initialize()
    db.upsert_channel(
        "UC123",
        "Test Channel",
        "https://youtube.com/channel/UC123",
        handle="@test",
        uploads_playlist_id="UU123",
    )
    env_file = tmp_path / "key.env"
    env_file.write_text(f"YPBRIEF_DB_PATH={db_path}\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["--env-file", str(env_file), "channel", "list"])

    assert result.exit_code == 0
    assert "Test Channel" in result.output
    assert "UU123" in result.output


def test_cli_channel_add_uses_archive_service(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("YOUTUBE_DATA_API_KEY=yt-key\n", encoding="utf-8")

    class FakeArchive:
        def add_channel(self, channel_input: str) -> ChannelInfo:
            assert channel_input == "@test"
            return ChannelInfo(
                channel_id="UC123",
                channel_name="Test Channel",
                channel_url="https://youtube.com/channel/UC123",
                handle="@test",
                uploads_playlist_id="UU123",
            )

    monkeypatch.setattr(cli_module, "_make_archive", lambda ctx: FakeArchive())

    result = CliRunner().invoke(cli, ["--env-file", str(env_file), "channel", "add", "@test"])

    assert result.exit_code == 0
    assert "Added channel" in result.output
    assert "UC123" in result.output


def test_cli_update_prints_update_stats(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("YOUTUBE_DATA_API_KEY=yt-key\n", encoding="utf-8")

    class FakeArchive:
        def update_channel(self, channel_ref: str, languages: list[str] | None = None) -> dict[str, int]:
            assert channel_ref == "UC123"
            return {"videos_seen": 2, "transcripts_saved": 1, "failed": 1}

    monkeypatch.setattr(cli_module, "_make_archive", lambda ctx: FakeArchive())

    result = CliRunner().invoke(cli, ["--env-file", str(env_file), "update", "--channel", "UC123"])

    assert result.exit_code == 0
    assert "videos_seen=2" in result.output
    assert "transcripts_saved=1" in result.output
    assert "failed=1" in result.output


def test_cli_channel_delete_removes_saved_channel(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "cli.db"
    db = Database(db_path)
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    env_file = tmp_path / "key.env"
    env_file.write_text(f"YPBRIEF_DB_PATH={db_path}\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["--env-file", str(env_file), "channel", "delete", "UC123"])

    assert result.exit_code == 0
    assert "Deleted channel" in result.output
    assert db.list_channels() == []


def test_cli_export_transcript_writes_markdown_file(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "cli.db"
    export_dir = tmp_path / "exports"
    db = Database(db_path)
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    db.save_transcript(
        video_id="vid1",
        raw_json='{"source": "fake"}',
        raw_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )
    with db.connect() as conn:
        conn.execute(
            "UPDATE Videos SET fetched_at = ? WHERE video_id = ?",
            ("2026-04-25 13:14:15", "vid1"),
        )
    env_file = tmp_path / "key.env"
    env_file.write_text(
        f"YPBRIEF_DB_PATH={db_path}\nYPBRIEF_EXPORT_DIR={export_dir}\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["--env-file", str(env_file), "export", "transcript", "--video-id", "vid1", "--format", "md"],
    )

    output_file = export_dir / "videos" / "Test Channel" / "2026-04-25 - vid1 - Episode 1" / "transcript.md"
    source_file = export_dir / "videos" / "Test Channel" / "2026-04-25 - vid1 - Episode 1" / "source.vtt"
    assert result.exit_code == 0
    assert output_file.exists()
    assert source_file.exists()
    assert "Exported source" in result.output
    assert "Exported transcript" in result.output
    body = output_file.read_text(encoding="utf-8")
    assert body.startswith(
        "# Test Channel\n\n"
        "## Episode 1\n\n"
        "Podcast Date: 2026-04-25\n"
        "Downloaded At: 2026-04-25 13:14:15\n"
    )
    assert "hello world" in body
    assert source_file.read_text(encoding="utf-8").startswith("WEBVTT")


def test_cli_export_summary_writes_markdown_file(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "cli.db"
    export_dir = tmp_path / "exports"
    db = Database(db_path)
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        raw_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary\n\nhello summary",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    env_file = tmp_path / "key.env"
    env_file.write_text(
        f"YPBRIEF_DB_PATH={db_path}\nYPBRIEF_EXPORT_DIR={export_dir}\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["--env-file", str(env_file), "export", "summary", "--video-id", "vid1"],
    )

    output_file = export_dir / "videos" / "Test Channel" / "2026-04-25 - vid1 - Episode 1" / "summary.md"
    assert result.exit_code == 0
    assert output_file.exists()
    assert "Exported summary" in result.output
    assert "hello summary" in output_file.read_text(encoding="utf-8")


def test_cli_summarize_video_uses_summarizer(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("OPENAI_API_KEY=openai-key\nLLM_PROVIDER=openai\n", encoding="utf-8")

    class FakeSummarizer:
        def summarize_video(self, video_id: str) -> int:
            assert video_id == "vid1"
            return 42

    monkeypatch.setattr(cli_module, "_make_summarizer", lambda ctx: FakeSummarizer())

    result = CliRunner().invoke(cli, ["--env-file", str(env_file), "summarize", "video", "vid1"])

    assert result.exit_code == 0
    assert "Saved summary: 42" in result.output


def test_cli_daily_summarize_uses_daily_service(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("GEMINI_API_KEY=gemini-key\nLLM_PROVIDER=gemini\n", encoding="utf-8")

    class FakeResult:
        summary_id = 77
        video_count = 2
        daily_summary = tmp_path / "daily-summary.md"
        videos_manifest = tmp_path / "videos.md"
        failed_manifest = tmp_path / "failed.md"

    class FakeDailyService:
        def summarize_videos(self, video_ids: list[str], run_date: str) -> FakeResult:
            assert video_ids == ["vid1", "vid2"]
            assert run_date == "2026-04-25"
            return FakeResult()

    monkeypatch.setattr(cli_module, "_make_daily_service", lambda ctx: FakeDailyService())

    result = CliRunner().invoke(
        cli,
        [
            "--env-file",
            str(env_file),
            "daily",
            "summarize",
            "--date",
            "2026-04-25",
            "--video-id",
            "vid1",
            "--video-id",
            "vid2",
        ],
    )

    assert result.exit_code == 0
    assert "Saved daily summary: 77" in result.output
    assert "Videos included: 2" in result.output


def test_cli_source_import_list_disable_enable_export_delete(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "data" / "cli.db"
    env_file = tmp_path / "key.env"
    import_file = tmp_path / "sources.yaml"
    export_file = tmp_path / "exported.yaml"
    env_file.write_text(
        f"YPBRIEF_DB_PATH={db_path}\nYOUTUBE_DATA_API_KEY=yt-key\n",
        encoding="utf-8",
    )
    import_file.write_text(
        """
sources:
  - type: channel
    url: "@test"
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    class FakeSourceService:
        def __init__(self) -> None:
            self.disabled = False

        def import_yaml(self, path: Path) -> int:
            assert path == import_file
            return 1

        def export_yaml(self, path: Path) -> None:
            path.write_text("sources: []\n", encoding="utf-8")

        def list(self):
            return [
                {
                    "source_id": 1,
                    "source_type": "channel",
                    "source_name": "Test Channel",
                    "youtube_id": "UC123",
                    "enabled": 1,
                }
            ]

        def disable(self, source_id: int) -> None:
            assert source_id == 1

        def enable(self, source_id: int) -> None:
            assert source_id == 1

        def delete(self, source_id: int) -> None:
            assert source_id == 1

    fake = FakeSourceService()
    monkeypatch.setattr(cli_module, "_make_source_service", lambda ctx: fake)

    import_result = CliRunner().invoke(cli, ["--env-file", str(env_file), "source", "import", str(import_file)])
    list_result = CliRunner().invoke(cli, ["--env-file", str(env_file), "source", "list"])
    disable_result = CliRunner().invoke(cli, ["--env-file", str(env_file), "source", "disable", "1"])
    enable_result = CliRunner().invoke(cli, ["--env-file", str(env_file), "source", "enable", "1"])
    export_result = CliRunner().invoke(cli, ["--env-file", str(env_file), "source", "export", str(export_file)])
    delete_result = CliRunner().invoke(cli, ["--env-file", str(env_file), "source", "delete", "1"])

    assert import_result.exit_code == 0
    assert "Imported sources: 1" in import_result.output
    assert "Test Channel" in list_result.output
    assert disable_result.exit_code == 0
    assert enable_result.exit_code == 0
    assert export_result.exit_code == 0
    assert export_file.exists()
    assert delete_result.exit_code == 0
