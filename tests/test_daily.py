import json
from pathlib import Path

from ypbrief.config import Settings
from ypbrief.daily import DailyDigestService, DigestRunService
from ypbrief.database import Database
from ypbrief.delivery import DeliveryService
from ypbrief.prompts import PromptFileService
from ypbrief.scheduler import SchedulerService
from ypbrief.youtube import ChannelInfo


class FakeProvider:
    name = "gemini"
    model = "fake-daily-model"

    def summarize(self, prompt: str, transcript: str) -> str:
        assert "正式日报提示词" in prompt
        assert "Episode 1" in transcript
        assert "Episode 2" in transcript
        return "# 每日播客综合日报 - 2026-04-25\n\n## 今日核心结论\n\n- useful digest"


class LenientFakeProvider:
    name = "gemini"
    model = "fake-daily-model"

    def summarize(self, prompt: str, transcript: str) -> str:
        assert "正式日报提示词" in prompt
        assert "Episode 1" in transcript
        return "# 每日播客综合日报 - 2026-04-25\n\n- useful digest"


def test_daily_digest_service_saves_and_exports_digest(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    export_dir = tmp_path / "exports"
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    db.upsert_video("vid2", "UC123", "Episode 2", "https://youtu.be/vid2", video_date="2026-04-25")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary 1\n\npoint 1",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary 2\n\npoint 2",
        provider="gemini",
        model="gemini-test",
        video_id="vid2",
        channel_id="UC123",
    )

    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )

    result = DailyDigestService(
        db,
        FakeProvider(),
        export_dir,
        settings=Settings(prompt_file=prompt_file),
    ).summarize_videos(
        ["vid1", "vid2"],
        run_date="2026-04-25",
    )

    summary = db.get_summary(result.summary_id)

    assert summary["summary_type"] == "digest"
    assert summary["range_start"] == "2026-04-25"
    assert result.video_count == 2
    assert result.daily_summary.exists()
    assert result.videos_manifest.exists()
    assert result.failed_manifest.exists()
    assert result.daily_summary.read_text(encoding="utf-8").startswith("# 每日播客综合日报")
    assert "`vid1`" in result.videos_manifest.read_text(encoding="utf-8")


def test_daily_digest_service_keeps_same_day_exports_without_overwrite(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    export_dir = tmp_path / "exports"
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    db.upsert_video("vid2", "UC123", "Episode 2", "https://youtu.be/vid2", video_date="2026-04-25")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary 1\n\npoint 1",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary 2\n\npoint 2",
        provider="gemini",
        model="gemini-test",
        video_id="vid2",
        channel_id="UC123",
    )

    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    service = DailyDigestService(
        db,
        FakeProvider(),
        export_dir,
        settings=Settings(prompt_file=prompt_file),
    )

    first = service.summarize_videos(["vid1", "vid2"], run_date="2026-04-25")
    first.daily_summary.write_text("# first digest\n", encoding="utf-8")
    first.videos_manifest.write_text("# first videos\n", encoding="utf-8")
    first.failed_manifest.write_text("# first failed\n", encoding="utf-8")
    second = service.summarize_videos(["vid1", "vid2"], run_date="2026-04-25")

    assert first.daily_summary.name == "daily-summary.md"
    assert first.videos_manifest.name == "videos.md"
    assert first.failed_manifest.name == "failed.md"
    assert second.daily_summary.name.startswith("daily-summary-")
    assert second.videos_manifest.stem.removeprefix("videos") == second.failed_manifest.stem.removeprefix("failed")
    assert second.daily_summary.stem.removeprefix("daily-summary") == second.videos_manifest.stem.removeprefix("videos")
    assert first.daily_summary.read_text(encoding="utf-8") == "# first digest\n"
    assert first.videos_manifest.read_text(encoding="utf-8") == "# first videos\n"
    assert first.failed_manifest.read_text(encoding="utf-8") == "# first failed\n"


def test_daily_digest_service_cleans_common_llm_artifacts_before_export(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    export_dir = tmp_path / "exports"
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary 1\n\npoint 1",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )

    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )

    class ArtifactProvider:
        name = "gemini"
        model = "fake-daily-model"

        def summarize(self, prompt: str, transcript: str) -> str:
            return "# Digest\n\n＊ item\n※watch〞\nrange 10每20%"

    result = DailyDigestService(
        db,
        ArtifactProvider(),
        export_dir,
        settings=Settings(prompt_file=prompt_file),
    ).summarize_videos(
        ["vid1"],
        run_date="2026-04-25",
    )

    summary = db.get_summary(result.summary_id)
    exported = result.daily_summary.read_text(encoding="utf-8")

    assert "* item" in summary["content_markdown"]
    assert "※" not in summary["content_markdown"]
    assert "〞" not in summary["content_markdown"]
    assert "10-20%" in summary["content_markdown"]
    assert "* item" in exported


def test_daily_digest_service_fallback_prompt_uses_default_language_template(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    export_dir = tmp_path / "exports"
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary 1\n\npoint 1",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )

    class CapturePromptProvider:
        name = "gemini"
        model = "fake-daily-model"
        prompt = ""
        transcript = ""

        def summarize(self, prompt: str, transcript: str) -> str:
            self.prompt = prompt
            self.transcript = transcript
            return "# Daily Digest - 2026-04-25\n\n- useful digest"

    provider = CapturePromptProvider()
    DailyDigestService(db, provider, export_dir).summarize_videos(
        ["vid1"],
        run_date="2026-04-25",
        digest_language="en",
    )

    assert "professional industry content editor" in provider.prompt
    assert "Target Output Language: en" in provider.transcript
    assert "中文财经/科技播客日报编辑" not in provider.prompt


def test_daily_digest_service_uses_playlist_source_title_in_digest_input(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Morgan Stanley", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Can Stock Momentum Continue?", "https://youtu.be/vid1", video_date="2026-04-27")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary\n\nUseful point.",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Thoughts on the Market",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Morgan Stanley",
        playlist_id="PL123",
    )

    class CaptureProvider:
        name = "gemini"
        model = "fake-daily-model"
        transcript = ""

        def summarize(self, prompt: str, transcript: str) -> str:
            self.transcript = transcript
            return "# Digest"

    provider = CaptureProvider()
    DailyDigestService(db, provider, tmp_path / "exports").summarize_videos(
        ["vid1"],
        run_date="2026-04-28",
        source_ids_by_video={"vid1": source_id},
    )

    assert "Source Title: Morgan Stanley | Thoughts on the Market | Can Stock Momentum Continue?" in provider.transcript
    assert "## Morgan Stanley | Thoughts on the Market | Can Stock Momentum Continue?" in provider.transcript


def test_daily_digest_service_uses_channel_source_title_in_digest_input(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Morgan Stanley", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Can Stock Momentum Continue?", "https://youtu.be/vid1", video_date="2026-04-27")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary\n\nUseful point.",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    source_id = db.upsert_source(
        source_type="channel",
        source_name="Morgan Stanley",
        youtube_id="UC123",
        url="https://www.youtube.com/@morganstanley",
        channel_id="UC123",
        channel_name="Morgan Stanley",
    )

    class CaptureProvider:
        name = "gemini"
        model = "fake-daily-model"
        transcript = ""

        def summarize(self, prompt: str, transcript: str) -> str:
            self.transcript = transcript
            return "# Digest"

    provider = CaptureProvider()
    DailyDigestService(db, provider, tmp_path / "exports").summarize_videos(
        ["vid1"],
        run_date="2026-04-28",
        source_ids_by_video={"vid1": source_id},
    )

    assert "Source Title: Morgan Stanley | Can Stock Momentum Continue?" in provider.transcript
    assert "Thoughts on the Market" not in provider.transcript


class FakeYouTube:
    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        assert playlist_input == "https://www.youtube.com/playlist?list=PL123"
        videos = [
            type("Video", (), {
                "video_id": "vid1",
                "title": "Episode 1",
                "url": "https://youtu.be/vid1",
                "published_at": "2026-04-24T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
            })(),
            type("Video", (), {
                "video_id": "vid2",
                "title": "Episode 2",
                "url": "https://youtu.be/vid2",
                "published_at": "2026-04-23T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
            })(),
        ]
        return videos[:limit]


class FakeYouTubeWithPrivateVideo:
    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        videos = [
            type("Video", (), {
                "video_id": "private1",
                "title": "Private video",
                "url": "https://youtu.be/private1",
                "published_at": "2026-04-24T11:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
            })(),
            type("Video", (), {
                "video_id": "vid1",
                "title": "Episode 1",
                "url": "https://youtu.be/vid1",
                "published_at": "2026-04-24T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
            })(),
        ]
        return videos[:limit]


class FakeYouTubeUnsortedWithPrivateVideo:
    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        videos = [
            type("Video", (), {
                "video_id": "older1",
                "title": "Older Episode",
                "url": "https://youtu.be/older1",
                "published_at": "2026-04-23T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
            })(),
            type("Video", (), {
                "video_id": "private1",
                "title": "Private video",
                "url": "https://youtu.be/private1",
                "published_at": "2026-04-25T11:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
            })(),
            type("Video", (), {
                "video_id": "newest1",
                "title": "Episode 1",
                "url": "https://youtu.be/newest1",
                "published_at": "2026-04-24T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
            })(),
        ]
        return videos[:limit]


class FakeYouTubeWithShortVideo:
    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        videos = [
            type("Video", (), {
                "video_id": "short1",
                "title": "Quick clip",
                "url": "https://youtu.be/short1",
                "published_at": "2026-04-24T11:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
                "duration_seconds": 299,
            })(),
            type("Video", (), {
                "video_id": "vid1",
                "title": "Episode 1",
                "url": "https://youtu.be/vid1",
                "published_at": "2026-04-24T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
                "duration_seconds": 301,
            })(),
        ]
        return videos[:limit]


class FakeYouTubeManyVideos:
    def __init__(self) -> None:
        self.last_limit: int | None = None

    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        self.last_limit = limit
        videos = [
            type("Video", (), {
                "video_id": f"vid{index}",
                "title": f"Episode {index}",
                "url": f"https://youtu.be/vid{index}",
                "published_at": f"2026-04-{25 - index:02d}T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
                "duration_seconds": 600,
            })()
            for index in range(12)
        ]
        return videos if limit is None else videos[:limit]


class FlakyDiscoveryYouTube:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        self.calls += 1
        if self.calls <= self.failures:
            raise TimeoutError("Google API read timed out")
        return [
            type("Video", (), {
                "video_id": "vid1",
                "title": "Episode 1",
                "url": "https://youtu.be/vid1",
                "published_at": "2026-04-29T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
                "duration_seconds": 600,
            })(),
        ]


class FakeProcessor:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.processed: list[str] = []

    def process(self, video_id: str):
        self.processed.append(video_id)
        self.db.save_summary(
            summary_type="video",
            content_markdown=f"# Summary {video_id}",
            provider="gemini",
            model="gemini-test",
            video_id=video_id,
            channel_id="UC123",
        )
        return object()


class FakeChannelYouTube:
    def __init__(self) -> None:
        self.resolved: list[str] = []
        self.uploads: list[str] = []

    def resolve_channel(self, channel_input: str):
        self.resolved.append(channel_input)
        return ChannelInfo(
            channel_id="UC123",
            channel_name="Test Channel",
            channel_url="https://youtube.com/channel/UC123",
            handle=None,
            uploads_playlist_id="UU123",
        )

    def iter_uploads(self, uploads_playlist_id: str, limit: int | None = None):
        self.uploads.append(uploads_playlist_id)
        return [
            type("Video", (), {
                "video_id": "vid1",
                "title": "Episode 1",
                "url": "https://youtu.be/vid1",
                "published_at": "2026-04-24T10:00:00Z",
                "channel_id": "UC123",
                "channel_name": "Test Channel",
                "duration_seconds": 600,
            })(),
        ]

    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        raise AssertionError("playlist source was not expected")

    def get_video(self, video_input: str):
        raise AssertionError("video source was not expected")


def test_digest_run_service_refreshes_missing_uploads_playlist_for_channel_source(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="channel",
        source_name="Test Channel",
        youtube_id="UC123",
        url="https://www.youtube.com/channel/UC123",
        channel_id="UC123",
        channel_name="Test Channel",
    )
    youtube = FakeChannelYouTube()

    result = DigestRunService(
        db=db,
        youtube=youtube,
        processor=FakeProcessor(db),
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-25",
        window_days=3,
        max_videos_per_source=10,
    )

    with db.connect() as conn:
        channel = conn.execute("SELECT uploads_playlist_id FROM Channels WHERE channel_id = 'UC123'").fetchone()

    assert result["status"] == "completed"
    assert youtube.resolved == ["UC123"]
    assert youtube.uploads == ["UU123"]
    assert channel["uploads_playlist_id"] == "UU123"


def test_digest_run_service_discovers_sources_processes_missing_and_records_run(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    processor = FakeProcessor(db)

    result = DigestRunService(
        db=db,
        youtube=FakeYouTube(),
        processor=processor,
        digest_service=DailyDigestService(db, FakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-25",
        window_days=3,
        max_videos_per_source=10,
    )

    with db.connect() as conn:
        source_videos = conn.execute("SELECT * FROM SourceVideos ORDER BY video_id").fetchall()
        run_videos = conn.execute("SELECT * FROM DailyRunVideos WHERE run_id = ? ORDER BY video_id", (result["run_id"],)).fetchall()

    assert result["status"] == "completed"
    assert result["included_count"] == 2
    assert result["failed_count"] == 0
    assert processor.processed == ["vid1", "vid2"]
    assert [row["video_id"] for row in source_videos] == ["vid1", "vid2"]
    assert [row["status"] for row in run_videos] == ["included", "included"]


def test_digest_run_service_marks_no_updates_when_no_videos_match_window(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )

    result = DigestRunService(
        db=db,
        youtube=FakeYouTube(),
        processor=FakeProcessor(db),
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports"),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-20",
        window_days=1,
        max_videos_per_source=10,
    )

    assert result["status"] == "no_updates"
    assert result["included_count"] == 0
    assert result["failed_count"] == 0
    assert result["summary_id"] is None
    assert result["error_message"] is None


def test_digest_run_service_filters_private_video_and_continues_with_public_video(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    processor = FakeProcessor(db)

    result = DigestRunService(
        db=db,
        youtube=FakeYouTubeWithPrivateVideo(),
        processor=processor,
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-25",
        window_days=3,
        max_videos_per_source=2,
    )

    with db.connect() as conn:
        run_videos = conn.execute("SELECT * FROM DailyRunVideos WHERE run_id = ? ORDER BY video_id", (result["run_id"],)).fetchall()

    assert result["status"] == "completed"
    assert result["included_count"] == 1
    assert result["skipped_count"] == 0
    assert [row["status"] for row in run_videos] == ["included"]
    assert [row["video_id"] for row in run_videos] == ["vid1"]


def test_digest_run_service_selects_newest_usable_videos_after_filtering_private_entries(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    processor = FakeProcessor(db)

    result = DigestRunService(
        db=db,
        youtube=FakeYouTubeUnsortedWithPrivateVideo(),
        processor=processor,
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-26",
        window_days=4,
        max_videos_per_source=1,
    )

    with db.connect() as conn:
        run_videos = conn.execute("SELECT * FROM DailyRunVideos WHERE run_id = ? ORDER BY video_id", (result["run_id"],)).fetchall()

    assert result["status"] == "completed"
    assert result["included_count"] == 1
    assert result["skipped_count"] == 0
    assert processor.processed == ["newest1"]
    assert [row["video_id"] for row in run_videos] == ["newest1"]


def test_digest_run_service_filters_videos_under_five_minutes(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    processor = FakeProcessor(db)

    result = DigestRunService(
        db=db,
        youtube=FakeYouTubeWithShortVideo(),
        processor=processor,
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-25",
        window_days=2,
        max_videos_per_source=2,
    )

    with db.connect() as conn:
        run_videos = conn.execute("SELECT * FROM DailyRunVideos WHERE run_id = ? ORDER BY video_id", (result["run_id"],)).fetchall()

    assert result["status"] == "completed"
    assert result["included_count"] == 1
    assert result["skipped_count"] == 0
    assert processor.processed == ["vid1"]
    assert [row["video_id"] for row in run_videos] == ["vid1"]


def test_digest_run_service_allows_unlimited_videos_per_source(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    youtube = FakeYouTubeManyVideos()
    processor = FakeProcessor(db)

    result = DigestRunService(
        db=db,
        youtube=youtube,
        processor=processor,
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-26",
        window_days=30,
        max_videos_per_source=None,
    )

    assert youtube.last_limit is None
    assert result["status"] == "completed"
    assert result["included_count"] == 12
    assert len(processor.processed) == 12


def test_digest_run_service_allows_all_history_window(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Archive Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )

    class FakeYouTubeArchive:
        def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
            assert limit is None
            return [
                type("Video", (), {
                    "video_id": "new1",
                    "title": "New Episode",
                    "url": "https://youtu.be/new1",
                    "published_at": "2026-04-24T10:00:00Z",
                    "channel_id": "UC123",
                    "channel_name": "Test Channel",
                    "duration_seconds": 600,
                })(),
                type("Video", (), {
                    "video_id": "old1",
                    "title": "Archive Episode",
                    "url": "https://youtu.be/old1",
                    "published_at": "2024-01-10T10:00:00Z",
                    "channel_id": "UC123",
                    "channel_name": "Test Channel",
                    "duration_seconds": 600,
                })(),
            ]

    class ArchiveProvider:
        name = "gemini"
        model = "fake-daily-model"

        def summarize(self, prompt: str, transcript: str) -> str:
            assert "正式日报提示词" in prompt
            assert "New Episode" in transcript
            assert "Archive Episode" in transcript
            return "# 每日播客综合日报 - 2026-04-26\n\n- useful digest"

    processor = FakeProcessor(db)
    result = DigestRunService(
        db=db,
        youtube=FakeYouTubeArchive(),
        processor=processor,
        digest_service=DailyDigestService(db, ArchiveProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-26",
        window_days=None,
        max_videos_per_source=None,
    )

    with db.connect() as conn:
        run = conn.execute("SELECT window_start, window_end FROM DailyRuns WHERE run_id = ?", (result["run_id"],)).fetchone()

    assert result["status"] == "completed"
    assert result["included_count"] == 2
    assert processor.processed == ["new1", "old1"]
    assert run["window_start"] is None
    assert run["window_end"] == "2026-04-26"


def test_digest_run_service_can_force_resummarizing_existing_summaries(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    db.save_summary(
        summary_type="video",
        content_markdown="# Existing Summary",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    processor = FakeProcessor(db)

    class SingleVideoProvider:
        name = "gemini"
        model = "fake-daily-model"

        def summarize(self, prompt: str, transcript: str) -> str:
            assert "正式日报提示词" in prompt
            assert "Episode 1" in transcript
            return "# 每日播客综合日报 - 2026-04-25\n\n- useful digest"

    result = DigestRunService(
        db=db,
        youtube=FakeYouTube(),
        processor=processor,
        digest_service=DailyDigestService(db, SingleVideoProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-25",
        window_days=3,
        max_videos_per_source=1,
        reuse_existing_summaries=False,
    )

    assert result["status"] == "completed"
    assert processor.processed == ["vid1"]


def test_digest_run_service_can_skip_failed_videos_when_retry_disabled(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    db.mark_video_failed("vid1", "previous failure")
    processor = FakeProcessor(db)

    result = DigestRunService(
        db=db,
        youtube=FakeYouTube(),
        processor=processor,
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    ).run(
        source_ids=[source_id],
        run_date="2026-04-25",
        window_days=3,
        max_videos_per_source=1,
        retry_failed_once=False,
    )

    with db.connect() as conn:
        run_videos = conn.execute("SELECT * FROM DailyRunVideos WHERE run_id = ?", (result["run_id"],)).fetchall()

    assert result["status"] == "no_updates"
    assert processor.processed == []
    assert result["skipped_count"] == 1
    assert run_videos[0]["status"] == "skipped"
    assert "previously failed" in run_videos[0]["error_message"]


def test_scheduler_retries_automatic_job_once_after_discovery_failure(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-29")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary vid1",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    youtube = FlakyDiscoveryYouTube(failures=1)
    runner = DigestRunService(
        db=db,
        youtube=youtube,
        processor=FakeProcessor(db),
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    )
    scheduler = SchedulerService(db, Settings(), runner, delivery=DeliveryService(db, Settings()))
    job = scheduler.create_job({"job_name": "Retry Job", "scope_type": "sources", "source_ids": [source_id]})

    result = scheduler.run_job_now(job["job_id"], now="2026-04-30T07:00:00+08:00", automatic=True)

    with db.connect() as conn:
        runs = conn.execute(
            "SELECT run_type, status, scheduled_job_id FROM DailyRuns ORDER BY run_id"
        ).fetchall()

    assert youtube.calls == 2
    assert result["status"] == "completed"
    assert runs[0]["run_type"] == "scheduled"
    assert runs[0]["status"] == "failed"
    assert runs[0]["scheduled_job_id"] == job["job_id"]
    assert runs[1]["run_type"] == "scheduled"
    assert runs[1]["status"] == "completed"
    assert runs[1]["scheduled_job_id"] == job["job_id"]


def test_scheduler_archives_and_notifies_automatic_job_after_retry_failure(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Failing Playlist",
        youtube_id="PLFAIL",
        url="https://www.youtube.com/playlist?list=PLFAIL",
        enabled=True,
    )
    DeliveryService(db, Settings()).update_settings(
        {"telegram_enabled": True, "telegram_bot_token": "token", "telegram_chat_id": "123456"}
    )
    youtube = FlakyDiscoveryYouTube(failures=2)
    runner = DigestRunService(
        db=db,
        youtube=youtube,
        processor=FakeProcessor(db),
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports"),
    )
    posted: list[dict] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        posted.append(json)
        return FakeResponse()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)
    scheduler = SchedulerService(db, Settings(), runner)
    job = scheduler.create_job(
        {
            "job_name": "Failing Job",
            "scope_type": "sources",
            "source_ids": [source_id],
            "telegram_enabled": True,
            "email_enabled": False,
        }
    )

    result = scheduler.run_job_now(job["job_id"], now="2026-04-30T07:00:00+08:00", automatic=True)

    with db.connect() as conn:
        runs = conn.execute(
            "SELECT run_id, run_type, status, scheduled_job_id, error_message FROM DailyRuns ORDER BY run_id"
        ).fetchall()
        logs = conn.execute("SELECT * FROM DeliveryLogs ORDER BY delivery_id").fetchall()

    assert youtube.calls == 2
    assert result["status"] == "failed"
    assert result["failure_notice_delivered"] is True
    assert len(runs) == 2
    assert [row["run_type"] for row in runs] == ["scheduled", "scheduled"]
    assert [row["scheduled_job_id"] for row in runs] == [job["job_id"], job["job_id"]]
    assert runs[-1]["status"] == "failed"
    assert "Google API read timed out" in runs[-1]["error_message"]
    assert logs[-1]["status"] == "success"
    assert posted
    assert "# Failing Job - 2026-04-30 运行失败" in posted[-1]["text"]
    assert "任务原因：Google API read timed out" in posted[-1]["text"]


def test_scheduler_allows_automatic_run_after_job_was_updated(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "daily_digest",
        system_prompt="正式日报提示词",
        user_template="日报 {{ run_date }}\n\n{{ summaries }}",
    )
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
        playlist_id="PL123",
    )
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-29")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary vid1",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    youtube = FlakyDiscoveryYouTube(failures=0)
    runner = DigestRunService(
        db=db,
        youtube=youtube,
        processor=FakeProcessor(db),
        digest_service=DailyDigestService(db, LenientFakeProvider(), tmp_path / "exports", settings=Settings(prompt_file=prompt_file)),
    )
    scheduler = SchedulerService(db, Settings(), runner, delivery=DeliveryService(db, Settings()))
    job = scheduler.create_job({"job_name": "Edited Job", "scope_type": "sources", "source_ids": [source_id]})
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO DailyRuns(
                run_type, status, window_start, window_end, source_ids_json,
                scheduled_job_id, created_at, completed_at
            )
            VALUES ('scheduled', 'completed', '2026-04-29', '2026-04-30', ?, ?, '2026-04-30 00:00:00', '2026-04-30 00:01:00')
            """,
            (json.dumps([source_id]), job["job_id"]),
        )
        conn.execute(
            "UPDATE ScheduledJobs SET run_time = '09:30', updated_at = '2026-04-30 01:00:00' WHERE job_id = ?",
            (job["job_id"],),
        )

    result = scheduler.run_job_now(job["job_id"], now="2026-04-30T09:30:00+08:00", automatic=True)

    with db.connect() as conn:
        runs = conn.execute(
            "SELECT run_id, run_type, status, scheduled_job_id FROM DailyRuns ORDER BY run_id"
        ).fetchall()

    assert not result.get("skipped_duplicate")
    assert youtube.calls == 1
    assert result["status"] == "completed"
    assert len(runs) == 2
    assert runs[-1]["run_type"] == "scheduled"
    assert runs[-1]["scheduled_job_id"] == job["job_id"]
