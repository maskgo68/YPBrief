import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ypbrief.config import load_settings
from ypbrief.database import Database
from ypbrief.video_processor import VideoProcessResult
from ypbrief_api.app import create_app
import ypbrief_api.app as app_module


def test_api_auth_requires_password_when_configured(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(
        create_app(
            db=db,
            settings_override={"access_password": "12345678901234567890123456789012"},
        )
    )

    blocked = client.get("/api/dashboard")
    bad_login = client.post("/api/auth/login", json={"password": "wrong"})
    good_login = client.post("/api/auth/login", json={"password": "12345678901234567890123456789012"})
    token = good_login.json()["token"]
    allowed = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})
    status = client.get("/api/auth/status", headers={"Authorization": f"Bearer {token}"})

    assert blocked.status_code == 401
    assert bad_login.status_code == 401
    assert good_login.status_code == 200
    assert "12345678901234567890123456789012" not in good_login.text
    assert allowed.status_code == 200
    assert status.json()["auth_required"] is True
    assert status.json()["authenticated"] is True


def test_api_auth_rate_limits_repeated_bad_passwords(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(
        create_app(
            db=db,
            settings_override={"access_password": "12345678901234567890123456789012"},
        )
    )

    responses = [
        client.post("/api/auth/login", json={"password": "wrong"})
        for _ in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [401, 401, 401, 401, 401]
    assert responses[5].status_code == 429
    assert "12345678901234567890123456789012" not in responses[5].text


def test_api_auth_password_change_syncs_database_env_and_runtime(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text("YPBRIEF_ACCESS_PASSWORD=old-password\n", encoding="utf-8")
    client = TestClient(create_app(db=db, env_file=env_file))

    token = client.post("/api/auth/login", json={"password": "old-password"}).json()["token"]
    response = client.patch(
        "/api/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "old-password", "new_password": "new-password-123"},
    )
    old_login = client.post("/api/auth/login", json={"password": "old-password"})
    new_login = client.post("/api/auth/login", json={"password": "new-password-123"})

    with db.connect() as conn:
        row = conn.execute(
            "SELECT setting_value FROM ApplicationSettings WHERE setting_key = 'YPBRIEF_ACCESS_PASSWORD'"
        ).fetchone()

    assert response.status_code == 200
    assert response.json()["token"]
    assert "YPBRIEF_ACCESS_PASSWORD=new-password-123" in env_file.read_text(encoding="utf-8")
    assert row["setting_value"] == "new-password-123"
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_api_sets_basic_security_headers(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db))

    response = client.get("/api/auth/status")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_api_auth_is_open_when_password_is_not_configured(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db))

    status = client.get("/api/auth/status")
    response = client.get("/api/dashboard")

    assert status.json()["auth_required"] is False
    assert response.status_code == 200


def test_api_serves_web_ui_when_static_dist_exists(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    web_dist = tmp_path / "web" / "dist"
    web_dist.mkdir(parents=True)
    (web_dist / "index.html").write_text("<html><body>YPBrief UI</body></html>", encoding="utf-8")
    client = TestClient(create_app(db=db, settings_override={"web_dist_dir": str(web_dist)}))

    response = client.get("/")

    assert response.status_code == 200
    assert "YPBrief UI" in response.text


def test_api_dashboard_returns_latest_digest_and_stats(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    db.save_summary(
        summary_type="digest",
        content_markdown="# Daily\n\n- Point",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-25",
        range_end="2026-04-25",
    )

    client = TestClient(create_app(db=db, settings_override={"llm_provider": "gemini"}))
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["videos"] == 1
    assert data["latest_digest"]["range_start"] == "2026-04-25"
    assert data["latest_digest"]["preview"].startswith("# Daily")


def test_api_dashboard_recent_videos_only_returns_summarized_videos(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("new1", "UC123", "Private video", "https://youtu.be/new1", video_date="2026-04-25")
    db.upsert_video("clean1", "UC123", "Cleaned Episode", "https://youtu.be/clean1", video_date="2026-04-24")
    db.save_transcript("clean1", "{}", "clean transcript", [])
    db.upsert_video("sum1", "UC123", "Summarized Episode", "https://youtu.be/sum1", video_date="2026-04-23")
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary",
        provider="gemini",
        model="gemini-test",
        video_id="sum1",
        channel_id="UC123",
    )
    client = TestClient(create_app(db=db))

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["summarized_videos"] == 1
    assert data["stats"]["pending_videos"] == 2
    assert [item["video_id"] for item in data["recent_videos"]] == ["sum1"]


def test_api_dashboard_recent_videos_order_by_latest_summary_time(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("older_published_new_summary", "UC123", "Older Published", "https://youtu.be/old", video_date="2026-04-01")
    db.upsert_video("newer_published_old_summary", "UC123", "Newer Published", "https://youtu.be/new", video_date="2026-04-25")
    db.save_summary(
        summary_type="video",
        content_markdown="# Old publish, new summary",
        provider="gemini",
        model="gemini-test",
        video_id="older_published_new_summary",
        channel_id="UC123",
    )
    db.save_summary(
        summary_type="video",
        content_markdown="# New publish, old summary",
        provider="gemini",
        model="gemini-test",
        video_id="newer_published_old_summary",
        channel_id="UC123",
    )
    with db.connect() as conn:
        conn.execute(
            "UPDATE Videos SET summarized_at = '2026-04-27 10:00:00', updated_at = '2026-04-27 10:00:00' WHERE video_id = 'older_published_new_summary'"
        )
        conn.execute(
            "UPDATE Videos SET summarized_at = '2026-04-26 10:00:00', updated_at = '2026-04-26 10:00:00' WHERE video_id = 'newer_published_old_summary'"
        )
    client = TestClient(create_app(db=db))

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert [item["video_id"] for item in response.json()["recent_videos"][:2]] == [
        "older_published_new_summary",
        "newer_published_old_summary",
    ]


def test_api_dashboard_digest_preview_includes_full_overall_synthesis(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    content = """# Daily Podcast Digest - 2026-04-27

# Daily Update Overview
Overview paragraph.

# Overall Synthesis
- First synthesis point.
- Second synthesis point with enough substance to be useful.

# Video-by-Video Summaries
This section should not appear in the dashboard preview.
"""
    db.save_summary(
        summary_type="digest",
        content_markdown=content,
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-27",
        range_end="2026-04-27",
    )
    client = TestClient(create_app(db=db))

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    preview = response.json()["latest_digest"]["preview"]
    assert "Second synthesis point" in preview
    assert "Video-by-Video Summaries" not in preview


def test_api_videos_list_exposes_transcript_and_summary_timestamps(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    db.save_transcript("vid1", "{}", "clean transcript", [])
    db.save_summary(
        summary_type="video",
        content_markdown="# Summary",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    client = TestClient(create_app(db=db))

    response = client.get("/api/videos")

    assert response.status_code == 200
    video = response.json()[0]
    assert video["has_transcript"] is True
    assert video["fetched_at"]
    assert video["cleaned_at"]
    assert video["summarized_at"]

    detail_response = client.get("/api/videos/vid1")
    assert detail_response.status_code == 200
    assert detail_response.json()["has_transcript"] is True


def test_api_videos_list_orders_by_latest_processing_time_desc(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("older_publish_newer_run", "UC123", "Older Publish", "https://youtu.be/older", video_date="2026-04-01")
    db.upsert_video("newer_publish_older_run", "UC123", "Newer Publish", "https://youtu.be/newer", video_date="2026-04-25")
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE Videos
            SET summarized_at = '2026-04-26 18:00:00',
                updated_at = '2026-04-26 18:00:00',
                status = 'summarized'
            WHERE video_id = 'older_publish_newer_run'
            """
        )
        conn.execute(
            """
            UPDATE Videos
            SET summarized_at = '2026-04-25 09:00:00',
                updated_at = '2026-04-25 09:00:00',
                status = 'summarized'
            WHERE video_id = 'newer_publish_older_run'
            """
        )
    client = TestClient(create_app(db=db))

    response = client.get("/api/videos")

    assert response.status_code == 200
    assert [item["video_id"] for item in response.json()[:2]] == [
        "older_publish_newer_run",
        "newer_publish_older_run",
    ]


def test_api_process_video_url_reuses_existing_summary_without_source(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    summary_id = db.save_summary(
        summary_type="video",
        content_markdown="# Existing",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )

    def fail_processor(*args, **kwargs):
        raise AssertionError("processor should not run for an already summarized video")

    monkeypatch.setattr(app_module, "_make_video_processor", fail_processor)
    client = TestClient(create_app(db=db))

    response = client.post("/api/videos/process-url", json={"video_url": "https://www.youtube.com/watch?v=vid1"})

    assert response.status_code == 200
    assert response.json()["video_id"] == "vid1"
    assert response.json()["summary_id"] == summary_id
    assert response.json()["reused"] is True
    assert db.list_sources() == []


def test_api_process_video_url_calls_processor_for_new_video(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    export_dir = tmp_path / "exports"
    calls = []

    class FakeProcessor:
        def process(self, video_input: str) -> VideoProcessResult:
            calls.append(video_input)
            db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
            db.upsert_video("newvid1", "UC123", "Episode 1", "https://youtu.be/newvid1", video_date="2026-04-25")
            summary_id = db.save_summary(
                summary_type="video",
                content_markdown="# New",
                provider="gemini",
                model="gemini-test",
                video_id="newvid1",
                channel_id="UC123",
            )
            return VideoProcessResult(
                video_id="newvid1",
                summary_id=summary_id,
                source_vtt=export_dir / "source.vtt",
                transcript_md=export_dir / "transcript.md",
                summary_md=export_dir / "summary.md",
            )

    monkeypatch.setattr(app_module, "_make_video_processor", lambda db, settings: FakeProcessor())
    client = TestClient(create_app(db=db))

    response = client.post("/api/videos/process-url", json={"video_url": "https://www.youtube.com/watch?v=newvid1"})

    assert response.status_code == 200
    assert calls == ["https://www.youtube.com/watch?v=newvid1"]
    assert response.json()["video_id"] == "newvid1"
    assert response.json()["summary_id"]
    assert response.json()["reused"] is False
    assert response.json()["status"] == "summarized"
    assert db.list_sources() == []


def test_api_process_video_url_passes_language_override_and_regenerates_existing_summary(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    export_dir = tmp_path / "exports"
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    db.save_summary(
        summary_type="video",
        content_markdown="# Existing",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    calls = []

    class FakeProcessor:
        def process(self, video_input: str, output_language: str | None = None) -> VideoProcessResult:
            calls.append((video_input, output_language))
            summary_id = db.save_summary(
                summary_type="video",
                content_markdown="# 中文总结",
                provider="gemini",
                model="gemini-test",
                video_id="vid1",
                channel_id="UC123",
            )
            return VideoProcessResult(
                video_id="vid1",
                summary_id=summary_id,
                source_vtt=export_dir / "source.vtt",
                transcript_md=export_dir / "transcript.md",
                summary_md=export_dir / "summary.md",
            )

    monkeypatch.setattr(app_module, "_make_video_processor", lambda db, settings: FakeProcessor())
    client = TestClient(create_app(db=db))

    response = client.post(
        "/api/videos/process-url",
        json={"video_url": "https://www.youtube.com/watch?v=vid1", "output_language": "zh"},
    )

    assert response.status_code == 200
    assert calls == [("https://www.youtube.com/watch?v=vid1", "zh")]
    assert response.json()["reused"] is False


def test_api_telegram_webhook_rejects_unauthorized_sender_without_processing(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    sent_messages = []

    def fail_processor(*args, **kwargs):
        raise AssertionError("unauthorized Telegram sender must not trigger processing")

    monkeypatch.setattr(app_module, "_make_video_processor", fail_processor)
    monkeypatch.setattr(app_module, "_send_telegram_text", lambda *args, **kwargs: sent_messages.append(args), raising=False)
    client = TestClient(
        create_app(
            db=db,
            settings_override={
                "telegram_bot_inbox_enabled": "true",
                "telegram_bot_webhook_secret": "secret-path",
                "telegram_bot_allowed_user_ids": "1001",
                "telegram_bot_token": "123456:test",
            },
        )
    )

    response = client.post(
        "/api/telegram/webhook/secret-path",
        json={
            "message": {
                "message_id": 1,
                "chat": {"id": 2002},
                "from": {"id": 2002},
                "text": "https://www.youtube.com/watch?v=unauth1",
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unauthorized"
    assert sent_messages == []


def test_api_telegram_webhook_reuses_existing_summary_and_replies(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    summary_id = db.save_summary(
        summary_type="video",
        content_markdown="# Existing\n\nUseful summary.",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    sent_messages = []

    def fail_processor(*args, **kwargs):
        raise AssertionError("processor should not run for an existing summary")

    def fake_send(token: str, chat_id: str, text: str, parse_mode: str | None = None) -> None:
        sent_messages.append({"token": token, "chat_id": chat_id, "text": text, "parse_mode": parse_mode})

    monkeypatch.setattr(app_module, "_make_video_processor", fail_processor)
    monkeypatch.setattr(app_module, "_send_telegram_text", fake_send, raising=False)
    client = TestClient(
        create_app(
            db=db,
            settings_override={
                "access_password": "12345678901234567890123456789012",
                "telegram_bot_inbox_enabled": "true",
                "telegram_bot_webhook_secret": "secret-path",
                "telegram_bot_header_secret": "header-secret",
                "telegram_bot_allowed_user_ids": "1001",
                "telegram_bot_public_base_url": "https://ypbrief.example.com",
                "telegram_bot_token": "123456:test",
                "telegram_parse_mode": "Markdown",
            },
        )
    )

    response = client.post(
        "/api/telegram/webhook/secret-path",
        headers={"X-Telegram-Bot-Api-Secret-Token": "header-secret"},
        json={
            "message": {
                "message_id": 1,
                "chat": {"id": 9001},
                "from": {"id": 1001},
                "text": "please summarize https://www.youtube.com/watch?v=vid1",
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "reused", "video_id": "vid1", "summary_id": summary_id}
    assert len(sent_messages) == 2
    assert "正在处理" in sent_messages[0]["text"]
    assert sent_messages[0]["chat_id"] == "9001"
    assert "Episode 1" in sent_messages[1]["text"]
    assert "Test Channel" in sent_messages[1]["text"]
    assert "# Existing" in sent_messages[1]["text"]
    assert "https://ypbrief.example.com" in sent_messages[1]["text"]


def test_api_telegram_webhook_processes_new_video_and_sanitizes_failure(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    export_dir = tmp_path / "exports"
    sent_messages = []

    class FakeProcessor:
        def process(self, video_input: str) -> VideoProcessResult:
            assert video_input == "https://www.youtube.com/watch?v=newvid1"
            db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
            db.upsert_video("newvid1", "UC123", "Episode 1", "https://youtu.be/newvid1", video_date="2026-04-25")
            summary_id = db.save_summary(
                summary_type="video",
                content_markdown="# New\n\nFresh summary.",
                provider="gemini",
                model="gemini-test",
                video_id="newvid1",
                channel_id="UC123",
            )
            return VideoProcessResult(
                video_id="newvid1",
                summary_id=summary_id,
                source_vtt=export_dir / "source.vtt",
                transcript_md=export_dir / "transcript.md",
                summary_md=export_dir / "summary.md",
            )

    monkeypatch.setattr(app_module, "_make_video_processor", lambda db, settings: FakeProcessor())
    monkeypatch.setattr(app_module, "_send_telegram_text", lambda token, chat_id, text, parse_mode=None: sent_messages.append(text), raising=False)
    client = TestClient(
        create_app(
            db=db,
            settings_override={
                "telegram_bot_inbox_enabled": "true",
                "telegram_bot_webhook_secret": "secret-path",
                "telegram_bot_allowed_chat_ids": "9001",
                "telegram_bot_token": "123456:test",
            },
        )
    )

    response = client.post(
        "/api/telegram/webhook/secret-path",
        json={
            "message": {
                "message_id": 1,
                "chat": {"id": 9001},
                "from": {"id": 1001},
                "text": "https://www.youtube.com/watch?v=newvid1",
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["video_id"] == "newvid1"
    assert len(sent_messages) == 2
    assert "# New" in sent_messages[1]


def test_api_dashboard_includes_latest_run_and_operating_items(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("ok1", "UC123", "Included Episode", "https://youtu.be/ok1", video_date="2026-04-24")
    db.upsert_video("fail1", "UC123", "Failed Episode", "https://youtu.be/fail1", video_date="2026-04-24")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Ops Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
    )
    digest_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-25",
        range_end="2026-04-25",
    )
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, summary_id, included_count, failed_count, skipped_count, error_message)
            VALUES ('manual', 'completed', '2026-04-24', '2026-04-25', '[1]', ?, 1, 1, 0, NULL)
            """,
            (digest_id,),
        )
        run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO DailyRunVideos(run_id, video_id, source_id, status, action, summary_id)
            VALUES (?, 'ok1', ?, 'included', 'include', NULL)
            """,
            (run_id, source_id),
        )
        conn.execute(
            """
            INSERT INTO DailyRunVideos(run_id, video_id, source_id, status, action, error_message)
            VALUES (?, 'fail1', ?, 'failed', 'process', 'caption blocked')
            """,
            (run_id, source_id),
        )
    client = TestClient(create_app(db=db))

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["latest_run"]["run_id"] == run_id
    assert data["latest_run"]["included_count"] == 1
    assert data["recent_run_videos"][0]["video_title"] == "Failed Episode"
    assert data["recent_run_videos"][0]["error_message"] == "caption blocked"


def test_api_prompts_create_list_and_preview(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    client = TestClient(create_app(db=db, settings_override={"prompt_file": prompt_file}))

    create_response = client.post(
        "/api/prompts",
        json={
            "prompt_type": "daily_digest",
            "system_prompt": "Editor",
            "user_template": "Digest {{ summaries }} on {{ run_date }}",
        },
    )
    list_response = client.get("/api/prompts")
    preview_response = client.post(
        "/api/prompts/daily_digest/preview",
        json={"values": {"summaries": "notes", "run_date": "2026-04-25", "digest_language": "zh"}},
    )

    assert create_response.status_code == 200
    assert create_response.json()["prompt_type"] == "daily_digest"
    assert list_response.json()[0]["prompt_type"] == "video_summary"
    assert preview_response.json()["user_prompt"] == "Digest notes on 2026-04-25"
    assert not prompt_file.exists()


def test_api_prompts_can_be_saved_and_exported_as_yaml(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    prompt_file = tmp_path / "prompts.yaml"
    client = TestClient(create_app(db=db, settings_override={"prompt_file": prompt_file}))

    client.post(
        "/api/prompts",
        json={
            "prompt_type": "daily_digest",
            "prompt_name": "Daily Digest Prompt",
            "system_prompt": "Editor",
            "user_template": "Digest {{ summaries }}",
        },
    )

    saved = client.post("/api/prompts/save")
    exported = client.get("/api/prompts/export")

    assert saved.status_code == 200
    assert prompt_file.exists()
    assert "prompts:" in prompt_file.read_text(encoding="utf-8")
    assert exported.json()["filename"] == "prompts.yaml"
    assert "global:" in exported.json()["content"]


def test_api_source_groups_and_sources_yaml_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, settings_override={"youtube_data_api_key": "test-key"}))

    group = client.post("/api/source-groups", json={"group_name": "investment", "display_name": "Investment"})
    source_id = db.upsert_source(
        source_type="channel",
        source_name="Bloomberg Podcasts",
        youtube_id="UC123",
        url="https://www.youtube.com/@BloombergPodcasts",
        channel_id="UC123",
        channel_name="Bloomberg Podcasts",
    )
    updated = client.patch(f"/api/sources/{source_id}", json={"group_id": group.json()["group_id"]})
    saved = client.post("/api/sources/save")
    exported = client.get("/api/sources/export")

    assert group.status_code == 200
    assert updated.json()["group_name"] == "investment"
    assert saved.status_code == 200
    assert Path("sources.yaml").exists()
    assert "groups:" in Path("sources.yaml").read_text(encoding="utf-8")
    assert "group: investment" in exported.json()["content"]


def test_api_source_group_assignment_can_be_set_and_cleared(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db))

    group = client.post("/api/source-groups", json={"group_name": "health", "display_name": "Health"}).json()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Health Playlist",
        youtube_id="PL999",
        url="https://www.youtube.com/playlist?list=PL999",
        enabled=True,
    )

    assigned = client.patch(f"/api/sources/{source_id}", json={"group_id": group["group_id"]})
    cleared = client.patch(f"/api/sources/{source_id}", json={"group_id": None})

    assert assigned.status_code == 200
    assert assigned.json()["group_name"] == "health"
    assert cleared.status_code == 200
    assert cleared.json()["group_id"] is None


def test_api_model_profiles_can_be_added_activated_and_deleted(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text("GEMINI_API_KEY=gemini-key\nLLM_PROVIDER=gemini\n", encoding="utf-8")
    client = TestClient(create_app(db=db, env_file=env_file))

    created = client.post(
        "/api/model-profiles",
        json={"provider": "gemini", "model_name": "gemini-test", "activate": True},
    )
    profiles = client.get("/api/model-profiles")
    test_result = client.post("/api/health/test-llm")
    updated = client.patch(
        f"/api/model-profiles/{created.json()['model_id']}",
        json={"model_name": "gemini-new", "is_active": True},
    )
    health = client.get("/api/health")
    deleted = client.delete(f"/api/model-profiles/{created.json()['model_id']}")

    assert created.status_code == 200
    assert created.json()["is_active"] == 1
    assert profiles.json()[0]["model_name"] == "gemini-test"
    assert test_result.status_code == 200
    assert test_result.json()["configured"] is True
    assert "display_name" not in updated.json()
    assert updated.json()["model_name"] == "gemini-new"
    assert health.json()["llm_model"] == "gemini-new"
    assert health.json()["provider_keys"]["gemini"] is True
    assert deleted.json()["deleted"] is True


def test_api_llm_providers_can_be_configured_from_frontend(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text("LLM_PROVIDER=gemini\nLLM_MODEL=gemini-test\n", encoding="utf-8")
    client = TestClient(create_app(db=db, env_file=env_file))

    created = client.post(
        "/api/llm-providers",
        json={
            "provider": "test gateway",
            "provider_type": "openai_compatible",
            "display_name": "Test Gateway",
            "base_url": "https://llm.example.test/v1",
            "api_key": "secret-key",
            "default_model": "test/model-a",
            "enabled": True,
        },
    )
    model = client.post(
        "/api/model-profiles",
        json={"provider": "test_gateway", "model_name": "test/model-b", "activate": True},
    )
    providers = client.get("/api/llm-providers")
    health = client.get("/api/health")

    assert created.status_code == 200
    assert created.json()["provider"] == "test_gateway"
    assert created.json()["api_key_configured"] is True
    assert "api_key" not in created.json()
    assert model.status_code == 200
    assert health.json()["llm_provider"] == "test_gateway"
    assert health.json()["llm_model"] == "test/model-b"
    assert health.json()["provider_keys"]["test_gateway"] is True
    assert any(item["provider"] == "test_gateway" for item in providers.json())


def test_api_llm_provider_normalizes_hyphenated_names(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, env_file=tmp_path / "key.env"))

    created = client.post(
        "/api/llm-providers",
        json={
            "provider": "custom-openai",
            "provider_type": "openai_compatible",
            "display_name": "Custom Gateway",
            "base_url": "https://llm.example.test/v1",
            "api_key": "secret",
            "default_model": "model-a",
            "enabled": True,
        },
    )

    assert created.status_code == 200
    assert created.json()["provider"] == "custom_openai"


def test_api_does_not_list_env_only_custom_openai_as_builtin(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(
        create_app(
            db=db,
            env_file=tmp_path / "key.env",
            settings_override={
                "custom_openai_api_key": "custom-key",
                "custom_openai_base_url": "https://llm.example.test/v1",
                "custom_openai_model": "model-a",
            },
        )
    )

    providers = client.get("/api/llm-providers").json()

    assert all(item["provider"] != "custom_openai" for item in providers)


def test_api_settings_exposes_env_default_provider_urls_and_active_model(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(
        create_app(
            db=db,
            settings_override={
                "llm_provider": "gemini",
                "llm_model": "gemini-3-flash-preview",
                "gemini_api_key": "test-key",
            },
        )
    )

    providers = client.get("/api/llm-providers").json()
    models = client.get("/api/model-profiles").json()

    gemini = next(item for item in providers if item["provider"] == "gemini")
    claude = next(item for item in providers if item["provider"] == "claude")
    assert gemini["base_url"] == "https://generativelanguage.googleapis.com/v1beta"
    assert gemini["default_model"] == ""
    assert claude["base_url"] == "https://api.anthropic.com/v1"
    assert models[0]["provider"] == "gemini"
    assert models[0]["model_name"] == "gemini-3-flash-preview"
    assert models[0]["is_active"] == 1


def test_api_proxy_settings_can_be_updated_and_synced_to_env(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "YOUTUBE_PROXY_ENABLED=false",
                "IPROYAL_PROXY_PASSWORD=old-secret",
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(db=db, env_file=env_file))

    updated = client.patch(
        "/api/proxy-settings",
        json={
            "enabled": True,
            "iproyal_host": "geo.iproyal.com",
            "iproyal_port": "12321",
            "iproyal_username": "user-token",
            "iproyal_password": "new-secret",
            "youtube_proxy_http": "",
            "youtube_proxy_https": "",
            "yt_dlp_proxy": "",
        },
    )
    health = client.get("/api/health").json()
    proxy_test = client.post("/api/health/test-proxy").json()
    env_text = env_file.read_text(encoding="utf-8")

    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["configured"] is True
    assert updated.json()["iproyal_password_configured"] is True
    assert "iproyal_password" not in updated.json()
    assert health["proxy"] is True
    assert proxy_test["configured"] is True
    assert "YOUTUBE_PROXY_ENABLED=true" in env_text
    assert "IPROYAL_PROXY_HOST=geo.iproyal.com" in env_text
    assert "IPROYAL_PROXY_PASSWORD=new-secret" in env_text


def test_api_proxy_settings_can_disable_proxy_without_erasing_credentials(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text(
        "\n".join(
            [
                "YOUTUBE_PROXY_ENABLED=true",
                "IPROYAL_PROXY_HOST=geo.iproyal.com",
                "IPROYAL_PROXY_PORT=12321",
                "IPROYAL_PROXY_USERNAME=user-token",
                "IPROYAL_PROXY_PASSWORD=secret",
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(db=db, env_file=env_file))

    updated = client.patch("/api/proxy-settings", json={"enabled": False})
    health = client.get("/api/health").json()
    env_text = env_file.read_text(encoding="utf-8")

    assert updated.json()["enabled"] is False
    assert updated.json()["configured"] is False
    assert health["proxy"] is False
    assert "YOUTUBE_PROXY_ENABLED=false" in env_text
    assert "IPROYAL_PROXY_PASSWORD=secret" in env_text


def test_api_proxy_settings_reports_disabled_when_enabled_without_proxy_url(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    env_file = tmp_path / "key.env"
    env_file.write_text("YOUTUBE_PROXY_ENABLED=true\n", encoding="utf-8")
    app = create_app(db=db, settings=load_settings(env_file), env_file=env_file)
    client = TestClient(app)

    payload = client.get("/api/proxy-settings").json()

    assert payload["enabled"] is False
    assert payload["configured"] is False
    assert payload["effective_proxy"] == ""
    assert payload["effective_yt_dlp_proxy"] == ""
    proxy_test = client.post("/api/health/test-proxy").json()
    assert proxy_test["enabled"] is False
    assert proxy_test["configured"] is False


def test_api_youtube_settings_can_be_updated_and_synced_to_env(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text("YOUTUBE_DATA_API_KEY=old-key\n", encoding="utf-8")
    client = TestClient(create_app(db=db, env_file=env_file))

    initial = client.get("/api/youtube-settings")
    updated = client.patch("/api/youtube-settings", json={"api_key": "new-key"})
    health = client.get("/api/health").json()
    youtube_test = client.post("/api/health/test-youtube").json()
    env_text = env_file.read_text(encoding="utf-8")

    assert initial.status_code == 200
    assert initial.json()["configured"] is True
    assert "api_key" not in initial.json()
    assert updated.status_code == 200
    assert updated.json()["configured"] is True
    assert "api_key" not in updated.json()
    assert health["youtube_api_key"] is True
    assert youtube_test["configured"] is True
    assert "YOUTUBE_DATA_API_KEY=new-key" in env_text


def test_api_uses_ypbrief_env_file_environment_variable(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "data" / "key.env"
    monkeypatch.setenv("YPBRIEF_ENV_FILE", str(env_file))
    client = TestClient(create_app(db=db))

    response = client.patch("/api/youtube-settings", json={"api_key": "env-file-key"})

    assert response.status_code == 200
    assert "YOUTUBE_DATA_API_KEY=env-file-key" in env_file.read_text(encoding="utf-8")


def test_api_default_scheduled_job_uses_env_fallback_without_scheduler_settings_table(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(
        create_app(
            db=db,
            settings_override={
                "scheduler_enabled": "true",
                "scheduler_run_time": "07:30",
                "scheduler_digest_language": "en",
                "scheduler_source_scope": "selected",
                "scheduler_source_ids": "3,5",
                "scheduler_max_videos_per_source": "7",
                "scheduler_send_empty_digest": "false",
            },
        )
    )

    response = client.get("/api/scheduled-jobs")
    with db.connect() as conn:
        scheduler_settings = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'SchedulerSettings'"
        ).fetchone()

    assert response.status_code == 200
    job = response.json()[0]
    assert job["job_name"] == "Default Daily Job"
    assert job["enabled"] is True
    assert job["run_time"] == "07:30"
    assert job["digest_language"] == "en"
    assert job["scope_type"] == "sources"
    assert job["source_ids"] == [3, 5]
    assert job["max_videos_per_source"] == 7
    assert job["send_empty_digest"] is False
    assert scheduler_settings is None


def test_api_legacy_scheduler_endpoints_are_retired(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, env_file=tmp_path / "key.env"))

    assert client.get("/api/scheduler-settings").status_code == 404
    assert client.patch("/api/scheduler-settings", json={"enabled": True}).status_code == 404
    assert client.post("/api/scheduler/run-now", json={}).status_code == 404


def test_api_scheduled_jobs_reload_background_scheduler(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text("", encoding="utf-8")

    class FakeRunner:
        def run(self, **kwargs):
            return {"run_id": 1, "status": "completed", "summary_id": None, "included_count": 0, "failed_count": 0, "skipped_count": 0}

    app = create_app(db=db, env_file=env_file, digest_runner=FakeRunner())
    client = TestClient(app)

    created = client.post("/api/scheduled-jobs", json={"job_name": "Enabled Job", "enabled": True, "run_time": "07:00"})

    assert created.status_code == 200
    assert getattr(app.state, "scheduler", None) is not None
    client.patch(f"/api/scheduled-jobs/{created.json()['job_id']}", json={"enabled": False})


def test_api_delivery_settings_mask_secrets_and_sync_env(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text("TELEGRAM_BOT_TOKEN=old-token\nSMTP_PASSWORD=old-pass\n", encoding="utf-8")
    client = TestClient(create_app(db=db, env_file=env_file))

    updated = client.patch(
        "/api/delivery-settings",
        json={
            "telegram_enabled": True,
            "telegram_bot_token": "123456:telegram-secret",
            "telegram_chat_id": "-10042",
            "email_enabled": True,
            "smtp_host": "smtp.example.test",
            "smtp_port": 465,
            "smtp_username": "mailer",
            "smtp_password": "smtp-secret",
            "smtp_use_ssl": True,
            "smtp_use_tls": False,
            "email_from": "bot@example.test",
            "email_to": ["ops@example.test", "me@example.test"],
        },
    )
    fetched = client.get("/api/delivery-settings")
    env_text = env_file.read_text(encoding="utf-8")

    assert updated.status_code == 200
    assert updated.json()["telegram_bot_token_configured"] is True
    assert "telegram_bot_token" not in updated.json()
    assert fetched.json()["smtp_password_configured"] is True
    assert "smtp_password" not in fetched.json()
    assert fetched.json()["email_to"] == ["ops@example.test", "me@example.test"]
    assert "TELEGRAM_BOT_TOKEN=123456:telegram-secret" in env_text
    assert "SMTP_PASSWORD=smtp-secret" in env_text
    assert "EMAIL_TO=ops@example.test,me@example.test" in env_text


def test_api_delivery_test_telegram_rejects_invalid_chat_id_without_exposing_token(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    env_file = tmp_path / "key.env"
    env_file.write_text("", encoding="utf-8")
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)
    client = TestClient(create_app(db=db, env_file=env_file))
    client.patch(
        "/api/delivery-settings",
        json={"telegram_enabled": True, "telegram_bot_token": "123456:secret-token", "telegram_chat_id": "chat"},
    )

    tested = client.post("/api/delivery/test-telegram")
    logs = client.get("/api/delivery-logs").json()

    assert tested.status_code == 200
    assert tested.json()["status"] == "failed"
    assert "Chat ID" in tested.json()["error_message"]
    assert "secret-token" not in tested.text
    assert called is False
    assert "secret-token" not in logs[0]["error_message"]


def test_api_delivery_logs_masks_telegram_tokens_from_existing_errors(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO DeliveryLogs(channel, status, target, error_message)
            VALUES ('telegram', 'failed', 'chat', '400 for https://api.telegram.org/bot123456:secret-token/sendMessage')
            """
        )
    client = TestClient(create_app(db=db))

    logs = client.get("/api/delivery-logs").json()

    assert "secret-token" not in logs[0]["error_message"]
    assert "/bot***:***/sendMessage" in logs[0]["error_message"]


def test_api_deliver_summary_respects_selected_channels(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    summary_id = db.save_summary(
        summary_type="video",
        content_markdown="# Summary",
        provider="gemini",
        model="gemini-test",
    )
    sent: list[str] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, message):
            sent.append("email")

    def fake_post(url, json, timeout=30):
        sent.append("telegram")

        class Response:
            def raise_for_status(self):
                return None

        return Response()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)
    monkeypatch.setattr("ypbrief.delivery.smtplib.SMTP", FakeSMTP)
    client = TestClient(create_app(db=db, env_file=tmp_path / "key.env"))
    client.patch(
        "/api/delivery-settings",
        json={
            "telegram_enabled": True,
            "telegram_bot_token": "token",
            "telegram_chat_id": "123456",
            "email_enabled": True,
            "smtp_host": "smtp.example.test",
            "email_from": "bot@example.test",
            "email_to": ["user@example.test"],
        },
    )

    response = client.post(
        f"/api/summaries/{summary_id}/deliver",
        json={"telegram_enabled": True, "email_enabled": False},
    )

    assert response.status_code == 200
    assert sent == ["telegram"]
    assert [item["channel"] for item in response.json()["deliveries"]] == ["telegram"]


def test_api_scheduled_job_run_now_uses_previous_day_and_selected_sources(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Daily Source",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        enabled=True,
    )

    class FakeRunner:
        def run(self, **kwargs):
            assert kwargs["source_ids"] == [source_id]
            assert kwargs["run_date"] == "2026-04-27"
            assert kwargs["window_days"] == 1
            assert kwargs["max_videos_per_source"] == 10
            return {
                "run_id": 99,
                "run_type": "scheduled",
                "status": "completed",
                "summary_id": 12,
                "included_count": 1,
                "failed_count": 0,
                "skipped_count": 0,
            }

    env_file = tmp_path / "key.env"
    env_file.write_text("", encoding="utf-8")
    client = TestClient(create_app(db=db, digest_runner=FakeRunner(), env_file=env_file))
    job = client.post(
        "/api/scheduled-jobs",
        json={
            "job_name": "Selected Source Job",
            "scope_type": "sources",
            "source_ids": [source_id],
        },
    ).json()

    response = client.post(f"/api/scheduled-jobs/{job['job_id']}/run-now", json={"now": "2026-04-27T07:00:00+08:00"})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["summary_id"] == 12


def test_api_scheduled_job_run_now_can_submit_background_task(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Background Source",
        youtube_id="PLBACKGROUND",
        url="https://www.youtube.com/playlist?list=PLBACKGROUND",
        enabled=True,
    )
    calls: list[dict] = []

    class FakeRunner:
        def run(self, **kwargs):
            calls.append(kwargs)
            return {
                "run_id": 88,
                "run_type": "manual",
                "status": "completed",
                "summary_id": 12,
                "included_count": 1,
                "failed_count": 0,
                "skipped_count": 0,
            }

    env_file = tmp_path / "key.env"
    env_file.write_text("", encoding="utf-8")
    client = TestClient(create_app(db=db, digest_runner=FakeRunner(), env_file=env_file))
    job = client.post(
        "/api/scheduled-jobs",
        json={"job_name": "Background Job", "scope_type": "sources", "source_ids": [source_id]},
    ).json()

    response = client.post(
        f"/api/scheduled-jobs/{job['job_id']}/run-now",
        json={"now": "2026-04-27T07:00:00+08:00", "background": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["job_id"] == job["job_id"]
    assert calls


def test_api_scheduled_job_no_updates_delivers_empty_digest_notice(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Quiet Source",
        youtube_id="PLQUIET",
        url="https://www.youtube.com/playlist?list=PLQUIET",
        enabled=True,
    )

    class FakeRunner:
        def run(self, **kwargs):
            return {
                "run_id": 44,
                "run_type": "scheduled",
                "status": "failed",
                "summary_id": None,
                "included_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "error_message": "No videos included",
            }

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        assert "sendMessage" in url
        assert "今天没有新视频更新" in json["text"]
        return FakeResponse()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)

    env_file = tmp_path / "key.env"
    env_file.write_text("", encoding="utf-8")
    client = TestClient(create_app(db=db, digest_runner=FakeRunner(), env_file=env_file))
    client.patch(
        "/api/delivery-settings",
        json={"telegram_enabled": True, "telegram_bot_token": "token", "telegram_chat_id": "123456"},
    )
    job = client.post(
        "/api/scheduled-jobs",
        json={
            "job_name": "Quiet Source Job",
            "scope_type": "sources",
            "source_ids": [source_id],
            "send_empty_digest": True,
            "telegram_enabled": True,
            "email_enabled": False,
        },
    ).json()

    response = client.post(f"/api/scheduled-jobs/{job['job_id']}/run-now", json={"now": "2026-04-27T07:00:00+08:00"})
    logs = client.get("/api/delivery-logs")

    assert response.status_code == 200
    assert response.json()["status"] == "no_updates"
    assert response.json()["empty_digest_delivered"] is True
    assert logs.json()[0]["channel"] == "telegram"
    assert logs.json()[0]["status"] == "success"


def test_api_scheduled_jobs_crud_and_run_groups_window(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    group = db.save_source_group(group_name="Investing", display_name="Investing")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Group Source",
        youtube_id="PLGROUP",
        url="https://www.youtube.com/playlist?list=PLGROUP",
        enabled=True,
    )
    other_source_id = db.upsert_source(
        source_type="playlist",
        source_name="Other Source",
        youtube_id="PLOTHER",
        url="https://www.youtube.com/playlist?list=PLOTHER",
        enabled=True,
    )
    db.update_source(source_id, group_id=group["group_id"])

    calls: list[dict] = []

    class FakeRunner:
        def run(self, **kwargs):
            calls.append(kwargs)
            with db.connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, included_count)
                    VALUES ('manual', 'completed', '2026-04-24', '2026-04-27', ?, 1)
                    """,
                    (json.dumps(kwargs["source_ids"]),),
                )
            return {
                "run_id": int(cursor.lastrowid),
                "status": "completed",
                "summary_id": None,
                "included_count": 1,
                "failed_count": 0,
                "skipped_count": 0,
            }

    client = TestClient(create_app(db=db, digest_runner=FakeRunner(), env_file=tmp_path / "key.env"))
    created = client.post(
        "/api/scheduled-jobs",
        json={
            "job_name": "Investing Daily",
            "enabled": True,
            "run_time": "06:30",
            "timezone": "Asia/Shanghai",
            "digest_language": "zh",
            "scope_type": "groups",
            "group_ids": [group["group_id"]],
            "source_ids": [other_source_id],
            "window_mode": "last_3",
            "max_videos_per_source": 7,
            "telegram_enabled": True,
            "email_enabled": False,
        },
    )
    listed = client.get("/api/scheduled-jobs")
    updated = client.patch(f"/api/scheduled-jobs/{created.json()['job_id']}", json={"job_name": "Investing Morning", "window_mode": "all_time", "max_videos_per_source": None})
    run = client.post(f"/api/scheduled-jobs/{created.json()['job_id']}/run-now", json={"now": "2026-04-27T07:00:00+08:00"})

    assert created.status_code == 200
    assert listed.status_code == 200
    assert any(item["job_name"] == "Investing Daily" for item in listed.json())
    assert updated.status_code == 200
    assert updated.json()["window_mode"] == "all_time"
    assert updated.json()["max_videos_per_source"] is None
    assert run.status_code == 200
    assert calls[0]["source_ids"] == [source_id]
    assert calls[0]["window_days"] is None
    assert calls[0]["max_videos_per_source"] is None
    with db.connect() as conn:
        row = conn.execute("SELECT run_type, scheduled_job_id FROM DailyRuns WHERE run_id = ?", (run.json()["run_id"],)).fetchone()
    assert row["run_type"] == "scheduled_manual"
    assert row["scheduled_job_id"] == created.json()["job_id"]


def test_api_scheduled_job_delivery_channel_toggles(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Delivery Source",
        youtube_id="PLDELIVERY",
        url="https://www.youtube.com/playlist?list=PLDELIVERY",
        enabled=True,
    )
    with db.connect() as conn:
        summary_id = conn.execute(
            """
            INSERT INTO Summaries(summary_type, range_start, range_end, model_provider, model_name, content_markdown)
            VALUES ('daily_digest', '2026-04-26', '2026-04-27', 'test', 'fake', '# Digest')
            """
        ).lastrowid

    class FakeRunner:
        def run(self, **kwargs):
            with db.connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, summary_id, included_count)
                    VALUES ('manual', 'completed', '2026-04-26', '2026-04-27', ?, ?, 1)
                    """,
                    (json.dumps(kwargs["source_ids"]), summary_id),
                )
            return {
                "run_id": int(cursor.lastrowid),
                "status": "completed",
                "summary_id": summary_id,
                "included_count": 1,
                "failed_count": 0,
                "skipped_count": 0,
            }

    sent: list[str] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        sent.append("telegram")
        return FakeResponse()

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def starttls(self):
            return None

        def login(self, *args):
            return None

        def send_message(self, message):
            sent.append("email")

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)
    monkeypatch.setattr("ypbrief.delivery.smtplib.SMTP", FakeSMTP)
    client = TestClient(create_app(db=db, digest_runner=FakeRunner(), env_file=tmp_path / "key.env"))
    client.patch(
        "/api/delivery-settings",
        json={
            "telegram_enabled": True,
            "telegram_bot_token": "token",
            "telegram_chat_id": "123456",
            "email_enabled": True,
            "smtp_host": "smtp.example.test",
            "email_from": "bot@example.test",
            "email_to": ["user@example.test"],
        },
    )
    job = client.post(
        "/api/scheduled-jobs",
        json={
            "job_name": "Telegram only",
            "scope_type": "sources",
            "source_ids": [source_id],
            "telegram_enabled": True,
            "email_enabled": False,
        },
    ).json()

    response = client.post(f"/api/scheduled-jobs/{job['job_id']}/run-now", json={"now": "2026-04-27T07:00:00+08:00"})

    assert response.status_code == 200
    assert sent == ["telegram"]


def test_api_scheduled_job_no_updates_respects_job_delivery_channel_toggles(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Quiet Job Source",
        youtube_id="PLQUIETJOB",
        url="https://www.youtube.com/playlist?list=PLQUIETJOB",
        enabled=True,
    )
    sent: list[str] = []

    class FakeRunner:
        def run(self, **kwargs):
            with db.connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, included_count, failed_count, skipped_count)
                    VALUES ('manual', 'failed', '2026-04-26', '2026-04-27', ?, 0, 0, 0)
                    """,
                    (json.dumps(kwargs["source_ids"]),),
                )
            return {
                "run_id": int(cursor.lastrowid),
                "status": "failed",
                "summary_id": None,
                "included_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "error_message": "No videos included",
            }

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        sent.append("telegram")
        return FakeResponse()

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def starttls(self):
            return None

        def login(self, *args):
            return None

        def send_message(self, message):
            sent.append("email")

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)
    monkeypatch.setattr("ypbrief.delivery.smtplib.SMTP", FakeSMTP)
    client = TestClient(create_app(db=db, digest_runner=FakeRunner(), env_file=tmp_path / "key.env"))
    client.patch(
        "/api/delivery-settings",
        json={
            "telegram_enabled": True,
            "telegram_bot_token": "token",
            "telegram_chat_id": "123456",
            "email_enabled": True,
            "smtp_host": "smtp.example.test",
            "email_from": "bot@example.test",
            "email_to": ["user@example.test"],
        },
    )
    job = client.post(
        "/api/scheduled-jobs",
        json={
            "job_name": "Email only no updates",
            "scope_type": "sources",
            "source_ids": [source_id],
            "send_empty_digest": True,
            "telegram_enabled": False,
            "email_enabled": True,
        },
    ).json()

    response = client.post(f"/api/scheduled-jobs/{job['job_id']}/run-now", json={"now": "2026-04-27T07:00:00+08:00"})

    assert response.status_code == 200
    assert response.json()["status"] == "no_updates"
    assert response.json()["empty_digest_delivered"] is True
    assert sent == ["email"]


def test_api_scheduled_jobs_rejects_removed_five_day_window(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, env_file=tmp_path / "key.env"))

    response = client.post(
        "/api/scheduled-jobs",
        json={"job_name": "Old window", "window_mode": "last_5"},
    )

    assert response.status_code == 400
    assert "last_1, last_3, last_7" in response.json()["detail"]


def test_api_model_profiles_use_database_candidates_when_database_models_exist(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO ModelProfiles(provider, model_name, display_name, is_active)
            VALUES ('grok', 'grok-4.20-0309-non-reasoning', 'Grok', 1)
            """
        )
    client = TestClient(
        create_app(
            db=db,
            settings_override={"llm_provider": "gemini", "llm_model": "gemini-3-flash-preview"},
        )
    )

    models = client.get("/api/model-profiles").json()

    assert [(item["provider"], item["model_name"]) for item in models] == [
        ("grok", "grok-4.20-0309-non-reasoning")
    ]
    assert "display_name" not in models[0]


def test_api_builtin_provider_database_rows_keep_default_urls_when_blank(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO LLMProviderConfigs(provider, provider_type, display_name, base_url, api_key, default_model, enabled)
            VALUES ('claude', 'claude', 'Claude', '', '', 'claude-3-5-sonnet-latest', 1)
            """
        )
    client = TestClient(create_app(db=db))

    providers = client.get("/api/llm-providers").json()

    claude = next(item for item in providers if item["provider"] == "claude")
    assert claude["provider_type"] == "claude"
    assert claude["base_url"] == "https://api.anthropic.com/v1"


def test_api_includes_grok_provider_and_tests_model_connectivity(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()

    class FakeProvider:
        def summarize(self, prompt: str, transcript: str) -> str:
            assert "ok" in prompt
            assert "Connectivity" in transcript
            return "ok"

    def fake_provider_from_config(config, model_name):
        assert config["provider"] == "grok"
        assert config["base_url"] == "https://api.x.ai/v1"
        assert model_name == "grok-4"
        return FakeProvider()

    monkeypatch.setattr("ypbrief_api.app._provider_from_config", fake_provider_from_config)
    env_file = tmp_path / "key.env"
    env_file.write_text("", encoding="utf-8")
    client = TestClient(create_app(db=db, env_file=env_file, settings_override={"xai_api_key": "test-key"}))

    providers = client.get("/api/llm-providers").json()
    tested = client.post("/api/model-profiles/test", json={"provider": "grok", "model_name": "grok-4"})

    grok = next(item for item in providers if item["provider"] == "grok")
    assert grok["display_name"] == "Grok / xAI"
    assert grok["base_url"] == "https://api.x.ai/v1"
    assert grok["default_model"] == ""
    assert tested.json()["ok"] is True
    assert tested.json()["message"] == "ok"


def test_api_provider_update_syncs_key_env(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("LLM_PROVIDER=gemini\nLLM_MODEL=gemini-test\nXAI_API_KEY=\n", encoding="utf-8")
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, env_file=env_file))

    response = client.patch(
        "/api/llm-providers/grok",
        json={
            "provider_type": "openai_compatible",
            "display_name": "Grok / xAI",
            "base_url": "https://api.x.ai/v1",
            "api_key": "xai-secret",
            "default_model": "grok-4",
            "enabled": True,
        },
    )

    contents = env_file.read_text(encoding="utf-8")
    assert response.status_code == 200
    assert "XAI_API_KEY=xai-secret" in contents
    assert "XAI_BASE_URL=https://api.x.ai/v1" in contents
    assert "XAI_MODEL=grok-4" in contents


def test_api_active_model_syncs_key_env(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("LLM_PROVIDER=gemini\nLLM_MODEL=gemini-test\n", encoding="utf-8")
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, env_file=env_file))

    created = client.post(
        "/api/model-profiles",
        json={"provider": "grok", "model_name": "grok-4.20-0309-non-reasoning", "activate": True},
    )

    contents = env_file.read_text(encoding="utf-8")
    assert created.status_code == 200
    assert "LLM_PROVIDER=grok" in contents
    assert "LLM_MODEL=grok-4.20-0309-non-reasoning" in contents


def test_api_model_profiles_keep_inactive_candidate_models_without_display_name(tmp_path: Path) -> None:
    env_file = tmp_path / "key.env"
    env_file.write_text("LLM_PROVIDER=gemini\nLLM_MODEL=gemini-test\n", encoding="utf-8")
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO ModelProfiles(provider, model_name, display_name, is_active)
            VALUES ('grok', 'grok-4.20-0309-reasoning', 'grok-4.20-0309-reasoning', 1)
            """
        )
        conn.execute(
            """
            INSERT INTO ModelProfiles(provider, model_name, display_name, is_active)
            VALUES ('gemini', 'gemini-test', 'Current model from key.env', 0)
            """
        )
    client = TestClient(create_app(db=db, env_file=env_file))

    models = client.get("/api/model-profiles").json()

    assert [(item["provider"], item["model_name"]) for item in models] == [
        ("gemini", "gemini-test"),
        ("grok", "grok-4.20-0309-reasoning"),
    ]
    assert "display_name" not in models[0]
    assert models[0]["is_active"] == 0
    assert "display_name" not in models[1]
    assert models[1]["is_active"] == 1


def test_api_includes_deepseek_provider(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, settings_override={"deepseek_api_key": "test-key"}))

    providers = client.get("/api/llm-providers").json()

    deepseek = next(item for item in providers if item["provider"] == "deepseek")
    assert deepseek["display_name"] == "DeepSeek"
    assert deepseek["provider_type"] == "openai_compatible"
    assert deepseek["base_url"] == "https://api.deepseek.com/v1"
    assert deepseek["default_model"] == ""
    assert deepseek["api_key_configured"] is True


def test_api_model_connectivity_reports_missing_api_key(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db))

    response = client.post("/api/model-profiles/test", json={"provider": "grok", "model_name": "grok-4"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["configured"] is False
    assert "API key" in data["message"]


def test_api_digest_runs_uses_injected_runner(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()

    class FakeRunner:
        def run(self, **kwargs):
            assert kwargs["source_ids"] == [1, 2]
            assert kwargs["window_days"] == 7
            assert kwargs["digest_language"] == "en"
            return {"run_id": 12, "status": "completed", "included_count": 3}

        def get_run(self, run_id: int):
            assert run_id == 12
            return {"run_id": 12, "status": "completed"}

    client = TestClient(create_app(db=db, digest_runner=FakeRunner()))

    created = client.post(
        "/api/digest-runs",
        json={"source_ids": [1, 2], "window_days": 7, "max_videos_per_source": 10, "digest_language": "en"},
    )
    fetched = client.get("/api/digest-runs/12")

    assert created.status_code == 200
    assert created.json()["included_count"] == 3
    assert fetched.json()["status"] == "completed"


def test_api_digest_runs_rejects_removed_five_day_preset(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    client = TestClient(create_app(db=db, digest_runner=object()))

    response = client.post(
        "/api/digest-runs",
        json={"source_ids": [1], "window_days": 5, "max_videos_per_source": 10},
    )

    assert response.status_code == 400
    assert "1, 3, or 7" in response.json()["detail"]


def test_api_digest_runs_accepts_group_ids_and_expands_enabled_sources(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    group = db.save_source_group(group_name="investment", display_name="Investment")
    first_source_id = db.upsert_source(
        source_type="playlist",
        source_name="Alpha Research",
        youtube_id="PL-ALPHA",
        url="https://www.youtube.com/playlist?list=PL-ALPHA",
        enabled=True,
    )
    second_source_id = db.upsert_source(
        source_type="playlist",
        source_name="Beta Markets",
        youtube_id="PL-BETA",
        url="https://www.youtube.com/playlist?list=PL-BETA",
        enabled=True,
    )
    disabled_source_id = db.upsert_source(
        source_type="playlist",
        source_name="Gamma Disabled",
        youtube_id="PL-GAMMA",
        url="https://www.youtube.com/playlist?list=PL-GAMMA",
        enabled=False,
    )
    db.update_source(first_source_id, group_id=group["group_id"])
    db.update_source(second_source_id, group_id=group["group_id"])
    db.update_source(disabled_source_id, group_id=group["group_id"])

    class FakeRunner:
        def run(self, **kwargs):
            assert kwargs["source_ids"] == [first_source_id, second_source_id]
            assert kwargs["window_days"] == 3
            return {"run_id": 22, "status": "completed", "included_count": 2}

        def get_run(self, run_id: int):
            assert run_id == 22
            return {"run_id": 22, "status": "completed"}

    client = TestClient(create_app(db=db, digest_runner=FakeRunner()))

    created = client.post(
        "/api/digest-runs",
        json={"group_ids": [group["group_id"]], "window_days": 3, "max_videos_per_source": 10},
    )

    assert created.status_code == 200
    assert created.json()["included_count"] == 2


def test_api_digest_runs_accepts_unlimited_video_limit(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()

    class FakeRunner:
        def __init__(self) -> None:
            self.called_with = None

        def run(self, **kwargs):
            self.called_with = kwargs
            return {"run_id": 12, "status": "completed", "included_count": 12}

    runner = FakeRunner()
    client = TestClient(create_app(db=db, digest_runner=runner))

    response = client.post(
        "/api/digest-runs",
        json={
            "source_ids": [1],
            "date_from": "2026-01-01",
            "date_to": "2026-04-25",
            "max_videos_per_source": None,
        },
    )

    assert response.status_code == 200
    assert runner.called_with["max_videos_per_source"] is None
    assert runner.called_with["run_date"] == "2026-04-26"
    assert runner.called_with["window_days"] == 115


def test_api_digest_runs_accepts_all_time_scope(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()

    class FakeRunner:
        def __init__(self) -> None:
            self.called_with = None

        def run(self, **kwargs):
            self.called_with = kwargs
            return {"run_id": 18, "status": "completed", "included_count": 8}

    runner = FakeRunner()
    client = TestClient(create_app(db=db, digest_runner=runner))

    response = client.post(
        "/api/digest-runs",
        json={
            "source_ids": [1],
            "all_time": True,
            "max_videos_per_source": None,
        },
    )

    assert response.status_code == 200
    assert runner.called_with["window_days"] is None
    assert runner.called_with["max_videos_per_source"] is None


def test_api_regenerate_digest_uses_previous_run_window(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    digest_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-24",
        range_end="2026-04-25",
    )
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, summary_id, included_count)
            VALUES ('manual', 'completed', '2026-04-23', '2026-04-25', '[7, 8]', ?, 2)
            """,
            (digest_id,),
        )

    class FakeRunner:
        def __init__(self) -> None:
            self.called_with = None

        def run(self, **kwargs):
            self.called_with = kwargs
            return {"run_id": 44, "status": "completed", "summary_id": 99, "included_count": 2, "failed_count": 0, "skipped_count": 0}

    runner = FakeRunner()
    client = TestClient(create_app(db=db, digest_runner=runner))

    response = client.post(f"/api/digests/{digest_id}/regenerate")

    assert response.status_code == 200
    assert response.json()["run_id"] == 44
    assert runner.called_with == {
        "source_ids": [7, 8],
        "run_date": "2026-04-25",
        "window_days": 2,
        "max_videos_per_source": 10,
        "reuse_existing_summaries": True,
        "process_missing_videos": True,
        "retry_failed_once": True,
    }


def test_api_regenerate_digest_reuses_all_time_window(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    digest_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-26",
        range_end="2026-04-26",
    )
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, summary_id, included_count)
            VALUES ('manual', 'completed', NULL, '2026-04-26', '[3]', ?, 1)
            """,
            (digest_id,),
        )

    class FakeRunner:
        def __init__(self) -> None:
            self.called_with = None

        def run(self, **kwargs):
            self.called_with = kwargs
            return {"run_id": 45, "status": "completed", "summary_id": 199, "included_count": 1, "failed_count": 0, "skipped_count": 0}

    runner = FakeRunner()
    client = TestClient(create_app(db=db, digest_runner=runner))

    response = client.post(f"/api/digests/{digest_id}/regenerate")

    assert response.status_code == 200
    assert response.json()["run_id"] == 45
    assert runner.called_with["source_ids"] == [3]
    assert runner.called_with["run_date"] == "2026-04-26"
    assert runner.called_with["window_days"] is None


def test_api_source_update_import_export_and_health_checks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Original",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        enabled=True,
    )
    Path("sources.yaml").write_text("sources: []\n", encoding="utf-8")
    client = TestClient(
        create_app(
            db=db,
            settings_override={
                "youtube_data_api_key": "test-key",
                "youtube_proxy_enabled": "true",
                "youtube_proxy_http": "http://127.0.0.1:8080",
            },
        )
    )

    updated = client.patch(f"/api/sources/{source_id}", json={"display_name": "Readable name", "enabled": False})
    imported = client.post("/api/sources/import")
    exported = client.get("/api/sources/export")
    proxy = client.post("/api/health/test-proxy")
    database = client.post("/api/health/test-database")

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Readable name"
    assert updated.json()["enabled"] == 0
    assert exported.status_code == 200
    assert Path(exported.json()["path"]).name == "sources.yaml"
    assert imported.status_code == 200
    assert proxy.json()["configured"] is True
    assert database.json()["configured"] is True


def test_api_sources_bulk_add_assigns_group_and_reports_duplicates(tmp_path: Path, monkeypatch) -> None:
    class FakeYouTube:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"

        def resolve_channel(self, channel_input: str):
            return SimpleNamespace(
                channel_id="UC123",
                channel_name="Test Channel",
                channel_url="https://www.youtube.com/channel/UC123",
                handle="@test",
                uploads_playlist_id="UU123",
            )

        def get_playlist(self, playlist_input: str):
            return SimpleNamespace(
                playlist_id="PL123",
                playlist_name="Test Playlist",
                playlist_url="https://www.youtube.com/playlist?list=PL123",
                channel_id="UC123",
                channel_name="Test Channel",
                item_count=2,
            )

        def get_video(self, video_input: str):
            raise AssertionError(video_input)

    monkeypatch.setattr(app_module, "YouTubeDataClient", FakeYouTube)
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    group = db.save_source_group(group_name="investment", display_name="Investment")
    client = TestClient(create_app(db=db, settings_override={"youtube_data_api_key": "test-key"}))

    response = client.post(
        "/api/sources/bulk-add",
        json={
            "text": "@test\n@test\nhttps://www.youtube.com/playlist?list=PL123\n",
            "group_id": group["group_id"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["created"]) == 2
    assert len(data["duplicates"]) == 1
    assert len(data["failed"]) == 0
    assert {item["group_name"] for item in client.get("/api/sources").json()} == {"investment"}


def test_api_source_delete_removes_source_even_when_run_history_references_it(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Temporary Source",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
    )
    with db.connect() as conn:
        run_id = conn.execute(
            """
            INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, failed_count)
            VALUES ('manual', 'completed', '2026-04-24', '2026-04-25', '[1]', 1)
            """
        ).lastrowid
        conn.execute(
            """
            INSERT INTO DailyRunVideos(run_id, video_id, source_id, status, action, error_message)
            VALUES (?, 'vid1', ?, 'failed', 'process', 'caption blocked')
            """,
            (run_id, source_id),
        )
    client = TestClient(create_app(db=db))

    deleted = client.delete(f"/api/sources/{source_id}")
    sources = client.get("/api/sources").json()
    dashboard = client.get("/api/dashboard").json()
    with db.connect() as conn:
        run_video = conn.execute("SELECT source_id FROM DailyRunVideos WHERE run_id = ?", (run_id,)).fetchone()

    assert deleted.status_code == 200
    assert not any(item["source_id"] == source_id for item in sources)
    assert run_video["source_id"] is None
    assert dashboard["recent_run_videos"][0]["source_name"] == "Temporary Source"


def test_api_video_detail_and_export_endpoints(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-25")
    db.save_transcript("vid1", "[]", "Clean transcript", [], raw_vtt="WEBVTT\n\n00:00.000 --> 00:01.000\nHi")
    summary_id = db.save_summary(
        summary_type="video",
        video_id="vid1",
        content_markdown="# Summary",
        provider="gemini",
        model="gemini-test",
    )
    client = TestClient(create_app(db=db, settings_override={"export_dir": tmp_path / "exports"}))

    detail = client.get("/api/videos/vid1")
    transcript = client.post("/api/videos/vid1/export-transcript")
    summary = client.post("/api/videos/vid1/export-summary")
    digest_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-25",
        range_end="2026-04-25",
    )
    digest = client.post(f"/api/digests/{digest_id}/export")
    digest_later_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily Later",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-25",
        range_end="2026-04-25",
    )
    digest_later = client.post(f"/api/digests/{digest_later_id}/export")

    assert detail.status_code == 200
    assert detail.json()["summary"]["summary_id"] == summary_id
    assert detail.json()["transcript_raw_vtt"].startswith("WEBVTT")
    assert transcript.status_code == 200
    assert Path(transcript.json()["source"]).exists()
    assert summary.status_code == 200
    assert Path(summary.json()["summary"]).exists()
    assert digest.status_code == 200
    assert Path(digest.json()["summary"]).exists()
    assert digest.json()["filename"] == "daily-summary.md"
    assert digest.json()["content_markdown"] == "# Daily\n"
    assert digest_later.status_code == 200
    assert digest_later.json()["filename"].startswith("daily-summary-")
    assert Path(digest.json()["summary"]).read_text(encoding="utf-8") == "# Daily\n"
    assert Path(digest_later.json()["summary"]).read_text(encoding="utf-8") == "# Daily Later\n"


def test_api_digest_detail_includes_run_videos(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
    )
    video_summary = db.save_summary(
        summary_type="video",
        content_markdown="# Video",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    digest_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-25",
        range_end="2026-04-25",
    )
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, summary_id, included_count)
            VALUES ('manual', 'completed', '2026-04-24', '2026-04-25', '[1]', ?, 1)
            """,
            (digest_id,),
        )
        run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO DailyRunVideos(run_id, video_id, source_id, status, action, summary_id)
            VALUES (?, 'vid1', ?, 'included', 'include', ?)
            """,
            (run_id, source_id, video_summary),
        )
    client = TestClient(create_app(db=db))

    response = client.get(f"/api/digests/{digest_id}")

    assert response.status_code == 200
    assert response.json()["included_count"] == 1
    assert response.json()["included_videos"][0]["video_title"] == "Episode 1"
    assert response.json()["included_videos"][0]["source_name"] == "Test Playlist"


def test_api_digest_detail_infers_videos_from_digest_markdown_when_run_missing(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
    )
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO SourceVideos(source_id, video_id, source_position, published_at)
            VALUES (?, 'vid1', 1, '2026-04-24')
            """,
            (source_id,),
        )
    db.save_summary(
        summary_type="video",
        content_markdown="# Video",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    digest_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily\n\n# Video-by-Video Summaries\n\n## Test Channel | Episode 1\n- Publish Date: 2026-04-24\n",
        provider="gemini",
        model="gemini-test",
        range_start="2026-04-25",
        range_end="2026-04-25",
    )
    client = TestClient(create_app(db=db))

    response = client.get(f"/api/digests/{digest_id}")

    assert response.status_code == 200
    assert response.json()["included_count"] == 1
    assert response.json()["included_videos"][0]["video_id"] == "vid1"
    assert response.json()["included_videos"][0]["action"] == "inferred"


def test_api_retry_run_video_marks_existing_summary_included(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1", video_date="2026-04-24")
    source_id = db.upsert_source(
        source_type="playlist",
        source_name="Test Playlist",
        youtube_id="PL123",
        url="https://www.youtube.com/playlist?list=PL123",
        channel_id="UC123",
        channel_name="Test Channel",
    )
    summary_id = db.save_summary(
        summary_type="video",
        content_markdown="# Video",
        provider="gemini",
        model="gemini-test",
        video_id="vid1",
        channel_id="UC123",
    )
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json, failed_count, skipped_count)
            VALUES ('manual', 'completed', '2026-04-24', '2026-04-25', '[1]', 0, 1)
            """
        )
        run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO DailyRunVideos(run_id, video_id, source_id, status, action, error_message)
            VALUES (?, 'vid1', ?, 'skipped', 'skip', 'temporary issue')
            """,
            (run_id, source_id),
        )
    client = TestClient(create_app(db=db))

    response = client.post(f"/api/digest-runs/{run_id}/videos/vid1/retry?source_id={source_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "included"
    assert data["summary_id"] == summary_id
    assert data["run"]["included_count"] == 1
    assert data["run"]["failed_count"] == 0
    assert data["run"]["skipped_count"] == 0
