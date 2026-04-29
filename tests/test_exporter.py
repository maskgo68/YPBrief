from pathlib import Path

from ypbrief.cleaner import TranscriptSegment
from ypbrief.database import Database
from ypbrief.exporter import Exporter


def test_exporter_writes_markdown_with_podcast_episode_and_date_first(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Bg2 Pod", "https://youtube.com/channel/UC123")
    db.upsert_video(
        video_id="jA8ZQfq_Hzs",
        channel_id="UC123",
        video_title="AI Enterprise: Databricks/Glean | BG2 Guest Interview?",
        video_url="https://youtu.be/jA8ZQfq_Hzs",
        video_date="2026-04-24",
    )
    db.save_transcript(
        video_id="jA8ZQfq_Hzs",
        raw_json='{"source": "yt_dlp", "segments": [{"text": "hello world"}]}',
        raw_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )
    with db.connect() as conn:
        conn.execute(
            "UPDATE Videos SET fetched_at = ? WHERE video_id = ?",
            ("2026-04-25 13:14:15", "jA8ZQfq_Hzs"),
        )

    output = Exporter(db, tmp_path / "exports").export_transcript("jA8ZQfq_Hzs")

    assert (
        output.transcript.name
        == "transcript.md"
    )
    assert (
        output.source.name
        == "source.vtt"
    )
    assert output.source.parent.name == (
        "2026-04-24 - jA8ZQfq_Hzs - AI Enterprise Databricks Glean BG2 Guest Interview"
    )
    assert output.source.parent.parent.name == "Bg2 Pod"
    assert output.source.parent.parent.parent.name == "videos"
    assert output.source.read_text(encoding="utf-8") == (
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n"
    )
    body = output.transcript.read_text(encoding="utf-8")
    assert body.startswith(
        "# Bg2 Pod\n\n"
        "## AI Enterprise: Databricks/Glean | BG2 Guest Interview?\n\n"
        "Podcast Date: 2026-04-24\n"
        "Downloaded At: 2026-04-25 13:14:15\n"
        "Video ID: jA8ZQfq_Hzs\n"
        "URL: https://youtu.be/jA8ZQfq_Hzs\n\n"
        "## Transcript\n\n"
        "hello world\n"
    )


def test_exporter_txt_includes_identifying_header(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1")
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        raw_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nplain transcript\n",
        clean_text="plain transcript",
        segments=[TranscriptSegment(0.0, 2.0, "plain transcript")],
    )
    with db.connect() as conn:
        conn.execute("UPDATE Videos SET fetched_at = NULL WHERE video_id = ?", ("vid1",))

    output = Exporter(db, tmp_path / "exports").export_transcript("vid1", file_format="txt")

    assert output.source.name == (
        "source.vtt"
    )
    assert output.transcript.name == (
        "transcript.txt"
    )
    assert output.source.parent.name == "unknown-podcast-date - vid1 - Episode 1"
    assert output.transcript.read_text(encoding="utf-8").startswith(
        "Podcast: Test Channel\n"
        "Video: Episode 1\n"
        "Podcast Date: unknown-podcast-date\n"
        "Downloaded At: unknown-download-time\n"
        "Video ID: vid1\n"
        "URL: https://youtu.be/vid1\n\n"
        "Transcript:\n\n"
        "plain transcript\n"
    )


def test_exporter_writes_summary_markdown_next_to_video_files(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video(
        "vid1",
        "UC123",
        "Episode 1",
        "https://youtu.be/vid1",
        video_date="2026-04-25",
    )
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        raw_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )
    summary_id = db.save_summary(
        summary_type="video",
        content_markdown="# Summary\n\nhello summary",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )

    output = Exporter(db, tmp_path / "exports").export_summary("vid1")

    assert output.name == "summary.md"
    assert output.parent.name == "2026-04-25 - vid1 - Episode 1"
    body = output.read_text(encoding="utf-8")
    assert "Summary ID: " + str(summary_id) in body
    assert "Provider: gemini" in body
    assert "# Summary\n\nhello summary" in body
