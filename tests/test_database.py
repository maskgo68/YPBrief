from pathlib import Path

from ypbrief.cleaner import TranscriptSegment
from ypbrief.database import Database


def test_database_initializes_tables_and_searches_subtitle_text(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()

    db.upsert_channel(
        channel_id="UC123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UC123",
        handle="@test",
        uploads_playlist_id="UU123",
    )
    db.upsert_video(
        video_id="vid1",
        channel_id="UC123",
        video_title="Episode 1",
        video_url="https://youtu.be/vid1",
        video_date="2026-04-25",
        duration=120,
    )
    db.save_transcript(
        video_id="vid1",
        raw_json='[{"text": "hello world"}]',
        clean_text="hello searchable world",
        segments=[
            TranscriptSegment(start=0.0, duration=2.0, text="hello searchable world"),
        ],
    )

    results = db.search("searchable")

    assert len(results) == 1
    assert results[0]["video_id"] == "vid1"
    assert results[0]["video_title"] == "Episode 1"
    assert results[0]["text"] == "hello searchable world"


def test_database_saves_summaries_and_updates_video_status(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1")

    summary_id = db.save_summary(
        summary_type="video",
        content_markdown="# Summary",
        provider="openai",
        model="gpt-test",
        video_id="vid1",
        channel_id="UC123",
    )

    video = db.get_video("vid1")
    summary = db.get_summary(summary_id)

    assert video["status"] == "summarized"
    assert video["summary_latest_id"] == summary_id
    assert summary["content_markdown"] == "# Summary"
    assert summary["model_provider"] == "openai"


def test_database_get_video_transcript_includes_source_and_dates(tmp_path: Path) -> None:
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
        raw_json='{"source": "yt_dlp"}',
        raw_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )
    with db.connect() as conn:
        conn.execute(
            "UPDATE Videos SET fetched_at = ? WHERE video_id = ?",
            ("2026-04-25 13:14:15", "vid1"),
        )

    transcript = db.get_video_transcript("vid1")

    assert transcript["channel_name"] == "Test Channel"
    assert transcript["video_title"] == "Episode 1"
    assert transcript["video_date"] == "2026-04-25"
    assert transcript["fetched_at"] == "2026-04-25 13:14:15"
    assert transcript["transcript_raw_json"] == '{"source": "yt_dlp"}'
    assert transcript["transcript_raw_vtt"].startswith("WEBVTT")


def test_database_delete_scheduled_job_keeps_history_runs(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    job = db.save_scheduled_job(job_name="Old Automation")
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, scheduled_job_id)
            VALUES ('scheduled', 'completed', '2026-04-27', '2026-04-27', '[]', ?)
            """,
            (job["job_id"],),
        )
        run_id = int(cursor.lastrowid)

    db.delete_scheduled_job(job["job_id"])

    with db.connect() as conn:
        run = conn.execute("SELECT scheduled_job_id FROM DailyRuns WHERE run_id = ?", (run_id,)).fetchone()
        deleted = conn.execute("SELECT job_id FROM ScheduledJobs WHERE job_id = ?", (job["job_id"],)).fetchone()
    assert run is not None
    assert run["scheduled_job_id"] is None
    assert deleted is None


def test_database_get_video_includes_channel_name(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Readable Podcast", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1")

    video = db.get_video("vid1")

    assert video["channel_name"] == "Readable Podcast"
