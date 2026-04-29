from pathlib import Path

from ypbrief.database import Database
from ypbrief.sources import SourceService, detect_source_type, parse_playlist_id
from ypbrief.youtube import ChannelInfo, PlaylistInfo, VideoInfo


class FakeYouTube:
    def resolve_channel(self, channel_input: str) -> ChannelInfo:
        assert channel_input == "@test"
        return ChannelInfo(
            channel_id="UC123",
            channel_name="Test Channel",
            channel_url="https://www.youtube.com/channel/UC123",
            handle="@test",
            uploads_playlist_id="UU123",
        )

    def get_playlist(self, playlist_input: str) -> PlaylistInfo:
        assert "PL123" in playlist_input
        return PlaylistInfo(
            playlist_id="PL123",
            playlist_name="Test Playlist",
            playlist_url="https://www.youtube.com/playlist?list=PL123",
            channel_id="UC123",
            channel_name="Test Channel",
            item_count=2,
        )

    def get_video(self, video_input: str) -> VideoInfo:
        assert "vid1" in video_input
        return VideoInfo(
            video_id="vid1",
            title="Episode 1",
            url="https://www.youtube.com/watch?v=vid1",
            published_at="2026-04-25T00:00:00Z",
            channel_id="UC123",
            channel_name="Test Channel",
            default_language="en",
        )


def test_detect_source_type_for_channel_playlist_and_video() -> None:
    assert detect_source_type("@test") == "channel"
    assert detect_source_type("https://www.youtube.com/channel/UC123") == "channel"
    assert detect_source_type("https://www.youtube.com/playlist?list=PL123") == "playlist"
    assert detect_source_type("PL123") == "playlist"
    assert detect_source_type("https://www.youtube.com/watch?v=vid1") == "video"
    assert detect_source_type("vid1") == "video"
    assert parse_playlist_id("https://www.youtube.com/watch?v=abc&list=PL123") == "PL123"


def test_source_service_adds_and_manages_sources(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = SourceService(db=db, youtube=FakeYouTube())

    channel = service.add("@test")
    playlist = service.add("https://www.youtube.com/playlist?list=PL123")
    video = service.add("https://www.youtube.com/watch?v=vid1", enabled=False)
    service.disable(channel["source_id"])
    service.enable(channel["source_id"])

    sources = service.list()

    assert [source["source_type"] for source in sources] == ["channel", "playlist", "video"]
    assert channel["source_name"] == "Test Channel"
    assert playlist["youtube_id"] == "PL123"
    assert video["enabled"] == 0
    assert service.get(channel["source_id"])["enabled"] == 1

    service.delete(video["source_id"])

    assert [source["source_type"] for source in service.list()] == ["channel", "playlist"]


def test_source_service_imports_and_exports_yaml(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = SourceService(db=db, youtube=FakeYouTube())
    input_file = tmp_path / "sources.yaml"
    output_file = tmp_path / "exported.yaml"
    input_file.write_text(
        """
sources:
  - type: channel
    name: My Channel Name
    url: "@test"
    enabled: true
  - type: playlist
    url: "https://www.youtube.com/playlist?list=PL123"
    enabled: false
""".strip(),
        encoding="utf-8",
    )

    imported = service.import_yaml(input_file)
    service.export_yaml(output_file)

    exported = output_file.read_text(encoding="utf-8")
    assert imported == 2
    assert "sources:" in exported
    assert "Test Channel" in exported
    assert "Test Playlist" in exported
    assert "enabled: false" in exported


def test_source_service_bulk_adds_lines_with_group_and_duplicate_report(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    group = db.save_source_group(group_name="investment", display_name="Investment")
    service = SourceService(db=db, youtube=FakeYouTube())

    result = service.bulk_add_lines(
        [
            "# ignored",
            "@test",
            "@test",
            "https://www.youtube.com/playlist?list=PL123",
            "",
        ],
        group_id=group["group_id"],
    )

    sources = service.list()

    assert result["ignored"] == 2
    assert len(result["created"]) == 2
    assert len(result["duplicates"]) == 1
    assert len(result["failed"]) == 0
    assert {source["source_type"] for source in sources} == {"channel", "playlist"}
    assert {source["group_name"] for source in sources} == {"investment"}


def test_source_service_bulk_add_skips_existing_without_overwriting(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    first_group = db.save_source_group(group_name="investment", display_name="Investment")
    second_group = db.save_source_group(group_name="tech", display_name="Tech")
    service = SourceService(db=db, youtube=FakeYouTube())
    existing = service.add("@test", display_name="Readable", group_id=first_group["group_id"])

    result = service.bulk_add_lines(["@test"], group_id=second_group["group_id"])
    unchanged = service.get(existing["source_id"])

    assert len(result["created"]) == 0
    assert len(result["duplicates"]) == 1
    assert unchanged["display_name"] == "Readable"
    assert unchanged["group_name"] == "investment"
