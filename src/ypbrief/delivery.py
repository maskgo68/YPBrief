from __future__ import annotations

from datetime import UTC, datetime
from email.message import EmailMessage
import json
import re
import smtplib
from typing import Any

import requests

from .config import Settings
from .database import Database
from .utils import as_bool


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


class DeliveryService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def get_settings(self) -> dict[str, Any]:
        row = self._row()
        return {
            "telegram_enabled": bool(row["telegram_enabled"]),
            "telegram_bot_token_configured": bool(row["telegram_bot_token"]),
            "telegram_bot_token_hint": mask_secret(row["telegram_bot_token"] or ""),
            "telegram_chat_id": row["telegram_chat_id"] or "",
            "telegram_parse_mode": row["telegram_parse_mode"] or "Markdown",
            "telegram_send_as_file_if_too_long": bool(row["telegram_send_as_file_if_too_long"]),
            "email_enabled": bool(row["email_enabled"]),
            "smtp_host": row["smtp_host"] or "",
            "smtp_port": int(row["smtp_port"] or 587),
            "smtp_username": row["smtp_username"] or "",
            "smtp_password_configured": bool(row["smtp_password"]),
            "smtp_password_hint": mask_secret(row["smtp_password"] or ""),
            "smtp_use_tls": bool(row["smtp_use_tls"]),
            "smtp_use_ssl": bool(row["smtp_use_ssl"]),
            "email_from": row["email_from"] or "",
            "email_to": json.loads(row["email_to_json"] or "[]"),
            "email_subject_template": row["email_subject_template"] or "YPBrief 每日播客日报 - {{ run_date }}",
            "email_attach_markdown": bool(row["email_attach_markdown"]),
        }

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = dict(self._row(private=True))
        email_to = payload.get("email_to")
        if isinstance(email_to, str):
            email_to = [item.strip() for item in email_to.replace("\n", ",").split(",") if item.strip()]
        values = {
            "telegram_enabled": int(payload.get("telegram_enabled", current["telegram_enabled"])),
            "telegram_bot_token": current["telegram_bot_token"] if payload.get("telegram_bot_token") is None else payload.get("telegram_bot_token", "").strip(),
            "telegram_chat_id": payload.get("telegram_chat_id", current["telegram_chat_id"]) or "",
            "telegram_parse_mode": payload.get("telegram_parse_mode", current["telegram_parse_mode"]) or "Markdown",
            "telegram_send_as_file_if_too_long": int(payload.get("telegram_send_as_file_if_too_long", current["telegram_send_as_file_if_too_long"])),
            "email_enabled": int(payload.get("email_enabled", current["email_enabled"])),
            "smtp_host": payload.get("smtp_host", current["smtp_host"]) or "",
            "smtp_port": int(payload.get("smtp_port", current["smtp_port"]) or 587),
            "smtp_username": payload.get("smtp_username", current["smtp_username"]) or "",
            "smtp_password": current["smtp_password"] if payload.get("smtp_password") is None else payload.get("smtp_password", ""),
            "smtp_use_tls": int(payload.get("smtp_use_tls", current["smtp_use_tls"])),
            "smtp_use_ssl": int(payload.get("smtp_use_ssl", current["smtp_use_ssl"])),
            "email_from": payload.get("email_from", current["email_from"]) or "",
            "email_to_json": json.dumps(email_to if email_to is not None else json.loads(current["email_to_json"] or "[]")),
            "email_subject_template": payload.get("email_subject_template", current["email_subject_template"]) or "YPBrief 每日播客日报 - {{ run_date }}",
            "email_attach_markdown": int(payload.get("email_attach_markdown", current["email_attach_markdown"])),
        }
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO DeliverySettings(
                    settings_id, telegram_enabled, telegram_bot_token, telegram_chat_id,
                    telegram_parse_mode, telegram_send_as_file_if_too_long, email_enabled,
                    smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                    smtp_use_ssl, email_from, email_to_json, email_subject_template,
                    email_attach_markdown, updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(settings_id) DO UPDATE SET
                    telegram_enabled=excluded.telegram_enabled,
                    telegram_bot_token=excluded.telegram_bot_token,
                    telegram_chat_id=excluded.telegram_chat_id,
                    telegram_parse_mode=excluded.telegram_parse_mode,
                    telegram_send_as_file_if_too_long=excluded.telegram_send_as_file_if_too_long,
                    email_enabled=excluded.email_enabled,
                    smtp_host=excluded.smtp_host,
                    smtp_port=excluded.smtp_port,
                    smtp_username=excluded.smtp_username,
                    smtp_password=excluded.smtp_password,
                    smtp_use_tls=excluded.smtp_use_tls,
                    smtp_use_ssl=excluded.smtp_use_ssl,
                    email_from=excluded.email_from,
                    email_to_json=excluded.email_to_json,
                    email_subject_template=excluded.email_subject_template,
                    email_attach_markdown=excluded.email_attach_markdown,
                    updated_at=CURRENT_TIMESTAMP
                """,
                tuple(values.values()),
            )
        self._sync_settings_object(values)
        return self.get_settings()

    def send_summary(
        self,
        summary_id: int,
        run_id: int | None = None,
        *,
        telegram_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> list[dict[str, Any]]:
        if not self.any_enabled(telegram_enabled=telegram_enabled, email_enabled=email_enabled):
            return []
        summary = self.db.get_summary(summary_id)
        run_date = summary.get("range_start") or ""
        text = _replace_first_h1(
            summary["content_markdown"],
            self._delivery_title_for_summary(summary, run_id),
        )
        return self.send_text(
            text,
            run_date=run_date,
            summary_id=summary_id,
            run_id=run_id,
            telegram_enabled=telegram_enabled,
            email_enabled=email_enabled,
        )

    def send_no_updates(
        self,
        run_date: str,
        language: str,
        run_id: int | None = None,
        *,
        telegram_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> list[dict[str, Any]]:
        if language == "en":
            text = f"# Daily Podcast Digest - {run_date}\n\nNo new videos today."
        else:
            text = f"# 每日播客综合日报 - {run_date}\n\n今天没有新视频更新。"
        text = _replace_first_h1(text, self._delivery_title_for_run(run_id, run_date))
        return self.send_text(
            text,
            run_date=run_date,
            summary_id=None,
            run_id=run_id,
            telegram_enabled=telegram_enabled,
            email_enabled=email_enabled,
        )

    def send_text(
        self,
        text: str,
        run_date: str,
        summary_id: int | None = None,
        run_id: int | None = None,
        *,
        telegram_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> list[dict[str, Any]]:
        settings = self._row(private=True)
        results: list[dict[str, Any]] = []
        if settings["telegram_enabled"] and (telegram_enabled is not False):
            results.append(self._send_telegram(settings, text, summary_id, run_id))
        if settings["email_enabled"] and (email_enabled is not False):
            results.append(self._send_email(settings, text, run_date, summary_id, run_id))
        return results

    def any_enabled(self, *, telegram_enabled: bool | None = None, email_enabled: bool | None = None) -> bool:
        settings = self._row(private=True)
        return bool((settings["telegram_enabled"] and telegram_enabled is not False) or (settings["email_enabled"] and email_enabled is not False))

    def list_logs(self, limit: int = 50, job_id: int | None = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if job_id is None:
                rows = conn.execute(
                    """
                    SELECT l.*, j.job_name AS scheduled_job_name
                    FROM DeliveryLogs l
                    LEFT JOIN DailyRuns r ON r.run_id = l.run_id
                    LEFT JOIN ScheduledJobs j ON j.job_id = r.scheduled_job_id
                    ORDER BY l.created_at DESC, l.delivery_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT l.*, j.job_name AS scheduled_job_name
                    FROM DeliveryLogs l
                    JOIN DailyRuns r ON r.run_id = l.run_id
                    LEFT JOIN ScheduledJobs j ON j.job_id = r.scheduled_job_id
                    WHERE r.scheduled_job_id = ?
                    ORDER BY l.created_at DESC, l.delivery_id DESC
                    LIMIT ?
                    """,
                    (job_id, limit),
                ).fetchall()
        return [self._public_log(dict(row)) for row in rows]

    def _delivery_title_for_summary(self, summary: dict[str, Any], run_id: int | None) -> str:
        if summary.get("summary_type") == "digest":
            return self._delivery_title_for_run(run_id, summary.get("range_start") or "", summary_id=summary.get("summary_id"))
        if summary.get("summary_type") == "video":
            title = self._video_title(summary.get("video_id")) or "Video Summary"
            return f"Video Summary - {_one_line(title)}"
        return _one_line(summary.get("range_start") or "YPBrief Summary")

    def _delivery_title_for_run(self, run_id: int | None, run_date: str, summary_id: int | None = None) -> str:
        run = self._run_context(run_id, summary_id)
        date_text = run.get("window_end") or run_date or ""
        job_name = _one_line(run.get("scheduled_job_name") or "")
        if job_name:
            return f"{job_name} - {date_text}" if date_text else job_name
        if run.get("run_type") in {"scheduled", "scheduled_manual"}:
            title = "Scheduled Digest"
        elif run:
            title = "Manual Digest"
        else:
            title = "Daily Podcast Digest"
        return f"{title} - {date_text}" if date_text else title

    def _run_context(self, run_id: int | None, summary_id: int | None = None) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = None
            if run_id is not None:
                row = conn.execute(
                    """
                    SELECT r.*, j.job_name AS scheduled_job_name
                    FROM DailyRuns r
                    LEFT JOIN ScheduledJobs j ON j.job_id = r.scheduled_job_id
                    WHERE r.run_id = ?
                    """,
                    (run_id,),
                ).fetchone()
            if row is None and summary_id is not None:
                row = conn.execute(
                    """
                    SELECT r.*, j.job_name AS scheduled_job_name
                    FROM DailyRuns r
                    LEFT JOIN ScheduledJobs j ON j.job_id = r.scheduled_job_id
                    WHERE r.summary_id = ?
                    ORDER BY r.run_id DESC
                    LIMIT 1
                    """,
                    (summary_id,),
                ).fetchone()
        return dict(row) if row is not None else {}

    def _video_title(self, video_id: str | None) -> str | None:
        if not video_id:
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT video_title FROM Videos WHERE video_id = ?", (video_id,)).fetchone()
        return row["video_title"] if row is not None else None

    def _send_telegram(self, settings: dict[str, Any], text: str, summary_id: int | None, run_id: int | None) -> dict[str, Any]:
        token = settings["telegram_bot_token"] or ""
        chat_id = settings["telegram_chat_id"] or ""
        if not token or not chat_id:
            return self._log(summary_id, run_id, "telegram", "failed", chat_id, "Telegram token or chat id missing")
        if not _valid_telegram_chat_id(chat_id):
            return self._log(
                summary_id,
                run_id,
                "telegram",
                "failed",
                chat_id,
                "Telegram Chat ID must be a numeric chat id, negative group id, or @channelusername",
            )
        try:
            messages = _telegram_message_parts(text)
            for message in messages:
                _post_telegram_message(token, chat_id, message, settings["telegram_parse_mode"] or "Markdown")
            detail = None if len(messages) == 1 else f"Sent {len(messages)} Telegram message parts"
            return self._log(summary_id, run_id, "telegram", "success", chat_id, detail)
        except Exception as exc:
            detail = str(exc)
            response = getattr(exc, "response", None)
            if response is not None and getattr(response, "text", ""):
                detail = f"{detail}: {response.text}"
            return self._log(summary_id, run_id, "telegram", "failed", chat_id, detail)

    def _send_email(self, settings: dict[str, Any], text: str, run_date: str, summary_id: int | None, run_id: int | None) -> dict[str, Any]:
        recipients = json.loads(settings["email_to_json"] or "[]")
        if not settings["smtp_host"] or not settings["email_from"] or not recipients:
            return self._log(summary_id, run_id, "email", "failed", ",".join(recipients), "SMTP host, from, or recipients missing")
        subject = (settings["email_subject_template"] or "YPBrief 每日播客日报 - {{ run_date }}").replace("{{ run_date }}", run_date)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings["email_from"]
        message["To"] = ", ".join(recipients)
        message.set_content(text)
        if settings["email_attach_markdown"]:
            message.add_attachment(
                text,
                subtype="markdown",
                filename=f"ypbrief-digest-{run_date}.md",
            )
        try:
            smtp_cls = smtplib.SMTP_SSL if settings["smtp_use_ssl"] else smtplib.SMTP
            with smtp_cls(settings["smtp_host"], int(settings["smtp_port"] or 587), timeout=20) as smtp:
                if settings["smtp_use_tls"] and not settings["smtp_use_ssl"]:
                    smtp.starttls()
                if settings["smtp_username"] or settings["smtp_password"]:
                    smtp.login(settings["smtp_username"] or settings["email_from"], settings["smtp_password"] or "")
                smtp.send_message(message)
            return self._log(summary_id, run_id, "email", "success", ",".join(recipients), None)
        except Exception as exc:
            return self._log(summary_id, run_id, "email", "failed", ",".join(recipients), str(exc))

    def _log(self, summary_id: int | None, run_id: int | None, channel: str, status: str, target: str, error: str | None) -> dict[str, Any]:
        run_id = self._existing_run_id(run_id)
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO DeliveryLogs(summary_id, run_id, channel, status, target, error_message, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (summary_id, run_id, channel, status, target, error, datetime.now(UTC).isoformat(timespec="seconds")),
            )
            row = conn.execute("SELECT * FROM DeliveryLogs WHERE delivery_id = ?", (cursor.lastrowid,)).fetchone()
        return self._public_log(dict(row))

    def _existing_run_id(self, run_id: int | None) -> int | None:
        if run_id is None:
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT run_id FROM DailyRuns WHERE run_id = ?", (run_id,)).fetchone()
        return run_id if row else None

    def _public_log(self, row: dict[str, Any]) -> dict[str, Any]:
        if row.get("error_message"):
            row["error_message"] = _mask_telegram_token(row["error_message"])
        return row

    def _row(self, private: bool = False):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM DeliverySettings WHERE settings_id = 1").fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO DeliverySettings(
                        settings_id, telegram_enabled, telegram_bot_token, telegram_chat_id,
                        telegram_parse_mode, telegram_send_as_file_if_too_long,
                        email_enabled, smtp_host, smtp_port, smtp_username, smtp_password,
                        smtp_use_tls, smtp_use_ssl, email_from, email_to_json,
                        email_subject_template, email_attach_markdown
                    )
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(as_bool(self.settings.telegram_enabled)),
                        self.settings.telegram_bot_token,
                        self.settings.telegram_chat_id,
                        self.settings.telegram_parse_mode,
                        int(as_bool(self.settings.telegram_send_as_file_if_too_long)),
                        int(as_bool(self.settings.email_enabled)),
                        self.settings.smtp_host,
                        int(self.settings.smtp_port or 587),
                        self.settings.smtp_username,
                        self.settings.smtp_password,
                        int(as_bool(self.settings.smtp_use_tls)),
                        int(as_bool(self.settings.smtp_use_ssl)),
                        self.settings.email_from,
                        json.dumps([item.strip() for item in self.settings.email_to.replace("\n", ",").split(",") if item.strip()]),
                        self.settings.email_subject_template,
                        int(as_bool(self.settings.email_attach_markdown)),
                    ),
                )
                row = conn.execute("SELECT * FROM DeliverySettings WHERE settings_id = 1").fetchone()
        return row

    def _sync_settings_object(self, values: dict[str, Any]) -> None:
        self.settings.telegram_enabled = "true" if values["telegram_enabled"] else "false"
        self.settings.telegram_bot_token = values["telegram_bot_token"]
        self.settings.telegram_chat_id = values["telegram_chat_id"]
        self.settings.telegram_parse_mode = values["telegram_parse_mode"]
        self.settings.telegram_send_as_file_if_too_long = "true" if values["telegram_send_as_file_if_too_long"] else "false"
        self.settings.email_enabled = "true" if values["email_enabled"] else "false"
        self.settings.smtp_host = values["smtp_host"]
        self.settings.smtp_port = str(values["smtp_port"])
        self.settings.smtp_username = values["smtp_username"]
        self.settings.smtp_password = values["smtp_password"]
        self.settings.smtp_use_tls = "true" if values["smtp_use_tls"] else "false"
        self.settings.smtp_use_ssl = "true" if values["smtp_use_ssl"] else "false"
        self.settings.email_from = values["email_from"]
        self.settings.email_to = ",".join(json.loads(values["email_to_json"] or "[]"))
        self.settings.email_subject_template = values["email_subject_template"]
        self.settings.email_attach_markdown = "true" if values["email_attach_markdown"] else "false"


def _valid_telegram_chat_id(chat_id: str) -> bool:
    value = chat_id.strip()
    if not value:
        return False
    if value.startswith("@") and len(value) > 1:
        return True
    return bool(re.fullmatch(r"-?\d+", value))


def _post_telegram_message(token: str, chat_id: str, text: str, parse_mode: str | None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=20,
    )
    try:
        response.raise_for_status()
    except Exception as exc:
        if parse_mode and _is_telegram_parse_error(exc):
            plain_response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=20,
            )
            plain_response.raise_for_status()
            return
        raise


def _is_telegram_parse_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    detail = getattr(response, "text", "") if response is not None else str(exc)
    detail = detail.lower()
    return "can't parse entities" in detail or "can't find end of the entity" in detail


def _mask_telegram_token(value: str) -> str:
    return re.sub(r"/bot[^/]+/sendMessage", "/bot***:***/sendMessage", value)


def _one_line(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _replace_first_h1(markdown: str, title: str) -> str:
    safe_title = _one_line(title)
    if not safe_title:
        return markdown
    replacement = f"# {safe_title}"
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^#\s+\S", line):
            lines[index] = replacement
            return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")
    text = markdown.strip()
    return f"{replacement}\n\n{text}" if text else replacement


def _telegram_message_parts(text: str, limit: int = 3900) -> list[str]:
    chunks = _split_text_for_telegram(text, limit=limit - 16)
    if len(chunks) <= 1:
        return chunks
    total = len(chunks)
    return [f"[{index}/{total}]\n{chunk}" for index, chunk in enumerate(chunks, start=1)]


def _split_text_for_telegram(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(paragraph) <= limit:
            current = paragraph
            continue
        chunks.extend(paragraph[start : start + limit] for start in range(0, len(paragraph), limit))
    if current:
        chunks.append(current)
    return chunks
