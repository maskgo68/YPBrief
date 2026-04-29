from pathlib import Path

from ypbrief.cleaner import TranscriptSegment
from ypbrief.database import Database
from ypbrief.transcripts import TranscriptFetchResult
from ypbrief.video_processor import VideoProcessor, parse_video_id
from ypbrief.youtube import VideoInfo


class FakeYouTube:
    def get_video(self, video_input: str) -> VideoInfo:
        assert video_input == "https://www.youtube.com/watch?v=vid1&t=60s"
        return VideoInfo(
            video_id="vid1",
            title="Episode 1",
            url="https://www.youtube.com/watch?v=vid1",
            published_at="2026-04-25T00:00:00Z",
            channel_id="UC123",
            channel_name="Test Channel",
            default_language="en",
        )


class FakeShortVideoYouTube:
    def get_video(self, video_input: str) -> VideoInfo:
        return VideoInfo(
            video_id="short1",
            title="Quick clip",
            url="https://www.youtube.com/watch?v=short1",
            published_at="2026-04-25T00:00:00Z",
            channel_id="UC123",
            channel_name="Test Channel",
            default_language="en",
            duration_seconds=299,
        )


class FakeTranscriptFetcher:
    def fetch(self, video_id: str, languages: list[str] | None = None) -> TranscriptFetchResult:
        assert video_id == "vid1"
        assert languages == ["en-US", "en", "en-GB"]
        return TranscriptFetchResult(
            source="yt-dlp",
            source_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n",
            segments=[TranscriptSegment(0.0, 2.0, "hello world")],
        )


class FailingTranscriptFetcher:
    def fetch(self, video_id: str, languages: list[str] | None = None) -> TranscriptFetchResult:
        raise AssertionError("short videos should not fetch transcripts")


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def summarize(self, prompt: str, transcript: str) -> str:
        assert "professional content research editor" in prompt
        assert "Episode 1" in transcript
        assert "hello world" in transcript
        return "# Summary\n\nhello summary"


def test_parse_video_id_handles_urls_and_raw_ids() -> None:
    assert parse_video_id("https://www.youtube.com/watch?v=abc123&t=60s") == "abc123"
    assert parse_video_id("https://youtu.be/abc123?si=test") == "abc123"
    assert parse_video_id("abc123") == "abc123"


def test_video_processor_processes_url_to_exports(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    processor = VideoProcessor(
        db=db,
        youtube=FakeYouTube(),
        transcripts=FakeTranscriptFetcher(),
        provider=FakeProvider(),
        export_dir=tmp_path / "exports",
    )

    result = processor.process("https://www.youtube.com/watch?v=vid1&t=60s")

    video = db.get_video("vid1")
    summary = db.get_summary(result.summary_id)
    assert video["status"] == "summarized"
    assert video["transcript_raw_vtt"].startswith("WEBVTT")
    assert summary["content_markdown"].startswith("# Summary")
    assert result.source_vtt.name == "source.vtt"
    assert result.transcript_md.name == "transcript.md"
    assert result.summary_md.name == "summary.md"
    assert result.summary_md.parent.name == "2026-04-25 - vid1 - Episode 1"


def test_video_processor_skips_videos_under_five_minutes(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    processor = VideoProcessor(
        db=db,
        youtube=FakeShortVideoYouTube(),
        transcripts=FailingTranscriptFetcher(),
        provider=FakeProvider(),
        export_dir=tmp_path / "exports",
    )

    try:
        processor.process("short1")
    except ValueError as exc:
        assert "shorter than 300 seconds" in str(exc)
    else:
        raise AssertionError("short videos should be rejected")

    video = db.get_video("short1")
    assert video["status"] == "skipped"
    assert video["duration"] == 299
    assert video["summary_latest_id"] is None
