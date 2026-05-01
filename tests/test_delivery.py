import logging
from pathlib import Path

import pytest
import requests

from ypbrief.config import Settings
from ypbrief.database import Database
from ypbrief.delivery import DeliveryService, _short_error


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "API key not valid. Please pass a valid API key.",
            "YouTube API key invalid or missing",
        ),
        (
            "quotaExceeded: The request cannot be completed because you have exceeded your quota.",
            "YouTube API quota exceeded",
        ),
        (
            "HTTPSConnectionPool(host='www.googleapis.com', port=443): Read timed out.",
            "YouTube API request timed out or network is unstable",
        ),
        (
            "Proxy probe failed: 407 Proxy Authentication Required",
            "Proxy authentication failed; check username and password",
        ),
        (
            "Proxy probe failed: ConnectTimeoutError proxy timeout",
            "Proxy connection failed or timed out",
        ),
        (
            "ERROR: [youtube] vid1: This video is unavailable",
            "YouTube video unavailable or private",
        ),
        (
            "ERROR: Unable to download video subtitles for 'en': HTTP Error 429: Too Many Requests",
            "YouTube rate limited the request; try again later or switch proxy",
        ),
        (
            "API key is required for openrouter",
            "LLM API key missing or invalid",
        ),
        (
            "Error code: 404 - model not found",
            "LLM model not found or unavailable",
        ),
        (
            "Error code: 429 - Some resource has been exhausted; monthly spending limit reached",
            "LLM quota exhausted or monthly spending limit reached",
        ),
    ],
)
def test_short_error_classifies_configuration_layers(raw: str, expected: str) -> None:
    assert _short_error(raw) == expected


def test_telegram_delivery_splits_long_digest_into_multiple_messages(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = DeliveryService(db, Settings(telegram_enabled="true", telegram_bot_token="123456:secret", telegram_chat_id="1234567890"))
    posted: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, json, timeout):
        posted.append(json)
        return FakeResponse()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)
    text = "\n\n".join([f"## Section {index}\n" + ("内容 " * 500) for index in range(1, 9)])

    result = service.send_text(text, run_date="2026-04-26")

    assert result[0]["status"] == "success"
    assert result[0]["channel"] == "telegram"
    assert len(posted) > 1
    assert all(len(item["text"]) <= 4096 for item in posted)
    assert posted[0]["text"].startswith("[1/")
    assert "Section 8" in posted[-1]["text"]


def test_telegram_delivery_retries_parse_errors_as_plain_text(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = DeliveryService(
        db,
        Settings(
            telegram_enabled="true",
            telegram_bot_token="123456:secret",
            telegram_chat_id="1234567890",
            telegram_parse_mode="Markdown",
        ),
    )
    posted: list[dict] = []

    class FakeResponse:
        text = '{"ok":false,"description":"Bad Request: can\'t parse entities"}'

        def raise_for_status(self) -> None:
            raise requests.HTTPError("400 Client Error", response=self)

    class OkResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, json, timeout):
        posted.append(json)
        if len(posted) == 1:
            return FakeResponse()
        return OkResponse()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)

    result = service.send_text("### A markdown-ish digest with _unbalanced text", run_date="2026-04-26")

    assert result[0]["status"] == "success"
    assert len(posted) == 2
    assert posted[0]["parse_mode"] == "Markdown"
    assert "parse_mode" not in posted[1]


def test_feishu_delivery_posts_signed_text_message(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = DeliveryService(
        db,
        Settings(
            feishu_enabled="true",
            feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-token",
            feishu_secret="sign-secret",
        ),
    )
    posted: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"code": 0}

    def fake_post(url, json, timeout):
        posted.append({"url": url, "json": json})
        return FakeResponse()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)
    monkeypatch.setattr("ypbrief.delivery.time.time", lambda: 1760000000)

    result = service.send_text("# Digest\n\nBody", run_date="2026-04-26", telegram_enabled=False, feishu_enabled=True, email_enabled=False)

    assert result[0]["status"] == "success"
    assert result[0]["channel"] == "feishu"
    assert posted[0]["url"].endswith("/test-token")
    assert posted[0]["json"]["msg_type"] == "text"
    assert posted[0]["json"]["content"]["text"] == "# Digest\n\nBody"
    assert posted[0]["json"]["timestamp"] == "1760000000"
    assert posted[0]["json"]["sign"]


def test_send_summary_replaces_digest_title_with_scheduled_job_name(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    job = db.save_scheduled_job(job_name="Investment Morning Brief")
    summary_id = db.save_summary(
        summary_type="digest",
        content_markdown="# Daily Podcast Digest - 2026-04-27\n\nBody",
        provider="xai",
        model="grok-test",
        range_start="2026-04-27",
        range_end="2026-04-27",
    )
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO DailyRuns(
                run_type, status, window_start, window_end, source_ids_json,
                summary_id, included_count, scheduled_job_id
            )
            VALUES ('scheduled', 'completed', '2026-04-27', '2026-04-27', '[]', ?, 3, ?)
            """,
            (summary_id, job["job_id"]),
        )
        run_id = int(cursor.lastrowid)
    service = DeliveryService(db, Settings(telegram_enabled="true", telegram_bot_token="123456:secret", telegram_chat_id="1234567890"))
    posted: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, json, timeout):
        posted.append(json)
        return FakeResponse()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)

    result = service.send_summary(summary_id, run_id=run_id)

    assert result[0]["status"] == "success"
    assert posted[0]["text"].startswith("# Investment Morning Brief - 2026-04-27")
    assert "Daily Podcast Digest" not in posted[0]["text"].splitlines()[0]
    assert "Body" in posted[0]["text"]


def test_delivery_logs_runtime_channel_result(tmp_path: Path, caplog) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = DeliveryService(db, Settings(telegram_enabled="true", telegram_bot_token="", telegram_chat_id="1234567890"))

    with caplog.at_level(logging.INFO, logger="ypbrief.delivery"):
        result = service.send_text("hello", run_date="2026-04-30")

    messages = [record.getMessage() for record in caplog.records]
    assert result[0]["status"] == "failed"
    assert any("delivery telegram failed" in message for message in messages)
    assert all("1234567890" not in message for message in messages)


def test_delivery_runtime_logs_mask_telegram_token_and_feishu_webhook(tmp_path: Path, caplog) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = DeliveryService(db, Settings())
    error = (
        "404 Client Error for https://api.telegram.org/bot123456:secret-token/sendMessage "
        "and https://open.feishu.cn/open-apis/bot/v2/hook/test-token-secret"
    )

    with caplog.at_level(logging.WARNING, logger="ypbrief.delivery"):
        service._log(None, None, "telegram", "failed", "1234567890", error)

    messages = [record.getMessage() for record in caplog.records]
    assert any("/bot***:***/sendMessage" in message for message in messages)
    assert any("/bot/v2/hook/***" in message for message in messages)
    assert all("123456:secret-token" not in message for message in messages)
    assert all("test-token-secret" not in message for message in messages)


def test_send_summary_replaces_video_title_for_single_video(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Podcast", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "A Sharp Market Conversation", "https://youtu.be/vid1")
    summary_id = db.save_summary(
        summary_type="video",
        video_id="vid1",
        content_markdown="# Podcast Name\n\nBody",
        provider="gemini",
        model="gemini-test",
    )
    service = DeliveryService(db, Settings(telegram_enabled="true", telegram_bot_token="123456:secret", telegram_chat_id="1234567890"))
    posted: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, json, timeout):
        posted.append(json)
        return FakeResponse()

    monkeypatch.setattr("ypbrief.delivery.requests.post", fake_post)

    result = service.send_summary(summary_id)

    assert result[0]["status"] == "success"
    assert posted[0]["text"].startswith("# Video Summary - A Sharp Market Conversation")
    assert "Body" in posted[0]["text"]


def test_email_delivery_attaches_markdown_when_enabled(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = DeliveryService(
        db,
        Settings(
            email_enabled="true",
            smtp_host="smtp.example.test",
            smtp_port="587",
            smtp_use_tls="false",
            email_from="from@example.test",
            email_to="to@example.test",
            email_attach_markdown="true",
        ),
    )
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def starttls(self):
            raise AssertionError("TLS should be disabled in this test")

        def login(self, username, password):
            raise AssertionError("login should not be called in this test")

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr("ypbrief.delivery.smtplib.SMTP", FakeSMTP)

    result = service.send_text("# Digest\n\nBody", run_date="2026-04-28", telegram_enabled=False, email_enabled=True)

    assert result[0]["status"] == "success"
    assert sent_messages[0].is_multipart()
    attachments = list(sent_messages[0].iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "ypbrief-digest-2026-04-28.md"
    assert attachments[0].get_content().strip() == "# Digest\n\nBody"


def test_email_delivery_does_not_attach_markdown_when_disabled(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    service = DeliveryService(
        db,
        Settings(
            email_enabled="true",
            smtp_host="smtp.example.test",
            smtp_port="587",
            smtp_use_tls="false",
            email_from="from@example.test",
            email_to="to@example.test",
            email_attach_markdown="false",
        ),
    )
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr("ypbrief.delivery.smtplib.SMTP", FakeSMTP)

    result = service.send_text("# Digest\n\nBody", run_date="2026-04-28", telegram_enabled=False, email_enabled=True)

    assert result[0]["status"] == "success"
    assert not sent_messages[0].is_multipart()
