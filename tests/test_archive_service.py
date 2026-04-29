from pathlib import Path

from ypbrief.archive import ArchiveService
from ypbrief.cleaner import TranscriptSegment
from ypbrief.database import Database
from ypbrief.transcripts import TranscriptFetchResult
from ypbrief.youtube import ChannelInfo, VideoInfo


class FakeYouTube:
    def resolve_channel(self, channel_input: str) -> ChannelInfo:
        return ChannelInfo(
            channel_id="UC123",
            channel_name="Test Channel",
            channel_url="https://www.youtube.com/channel/UC123",
            handle="@test",
            uploads_playlist_id="UU123",
        )

    def iter_uploads(self, uploads_playlist_id: str, limit: int | None = None) -> list[VideoInfo]:
        return [
            VideoInfo(
                video_id="vid1",
                title="Episode 1",
                url="https://youtu.be/vid1",
                published_at="2026-04-25T00:00:00Z",
            )
        ]


class FakeTranscriptFetcher:
    def fetch(self, video_id: str, languages: list[str] | None = None) -> TranscriptFetchResult:
        return TranscriptFetchResult(
            source="fake",
            source_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\num hello\n",
            segments=[
                TranscriptSegment(start=0.0, duration=1.0, text="um hello"),
                TranscriptSegment(start=2.0, duration=1.0, text="world"),
            ],
        )


def test_archive_service_adds_channel_and_updates_transcripts(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = ArchiveService(db=db, youtube=FakeYouTube(), transcripts=FakeTranscriptFetcher())

    channel = service.add_channel("@test")
    stats = service.update_channel("UC123")

    channels = db.list_channels()
    video = db.get_video("vid1")
    results = db.search("hello")

    assert channel.channel_id == "UC123"
    assert stats["videos_seen"] == 1
    assert stats["transcripts_saved"] == 1
    assert channels[0]["uploads_playlist_id"] == "UU123"
    assert video["status"] == "cleaned"
    assert video["transcript_clean"] == "hello world"
    assert video["transcript_raw_vtt"].startswith("WEBVTT")
    assert results[0]["video_id"] == "vid1"
