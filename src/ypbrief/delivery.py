from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.message import EmailMessage
import hashlib
import hmac
import json
import logging
import re
import smtplib
import time
from typing import Any

import requests

from .config import Settings
from .database import Database
from .utils import as_bool


logger = logging.getLogger(__name__)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def mask_webhook_url(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"(?<=/bot/v2/hook/)[^/?#]+", "***", value)


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
            "feishu_enabled": bool(row["feishu_enabled"]),
            "feishu_webhook_url_configured": bool(row["feishu_webhook_url"]),
            "feishu_webhook_url_hint": mask_webhook_url(row["feishu_webhook_url"] or ""),
            "feishu_secret_configured": bool(row["feishu_secret"]),
            "feishu_secret_hint": mask_secret(row["feishu_secret"] or ""),
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
            "feishu_enabled": int(payload.get("feishu_enabled", current["feishu_enabled"])),
            "feishu_webhook_url": current["feishu_webhook_url"] if payload.get("feishu_webhook_url") is None else payload.get("feishu_webhook_url", "").strip(),
            "feishu_secret": current["feishu_secret"] if payload.get("feishu_secret") is None else payload.get("feishu_secret", "").strip(),
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
                    telegram_parse_mode, telegram_send_as_file_if_too_long, feishu_enabled,
                    feishu_webhook_url, feishu_secret, email_enabled,
                    smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                    smtp_use_ssl, email_from, email_to_json, email_subject_template,
                    email_attach_markdown, updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(settings_id) DO UPDATE SET
                    telegram_enabled=excluded.telegram_enabled,
                    telegram_bot_token=excluded.telegram_bot_token,
                    telegram_chat_id=excluded.telegram_chat_id,
                    telegram_parse_mode=excluded.telegram_parse_mode,
                    telegram_send_as_file_if_too_long=excluded.telegram_send_as_file_if_too_long,
                    feishu_enabled=excluded.feishu_enabled,
                    feishu_webhook_url=excluded.feishu_webhook_url,
                    feishu_secret=excluded.feishu_secret,
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
        feishu_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> list[dict[str, Any]]:
        if not self.any_enabled(telegram_enabled=telegram_enabled, feishu_enabled=feishu_enabled, email_enabled=email_enabled):
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
            feishu_enabled=feishu_enabled,
            email_enabled=email_enabled,
        )

    def send_no_updates(
        self,
        run_date: str,
        language: str,
        run_id: int | None = None,
        *,
        telegram_enabled: bool | None = None,
        feishu_enabled: bool | None = None,
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
            feishu_enabled=feishu_enabled,
            email_enabled=email_enabled,
        )

    def send_failure_notice(
        self,
        run_id: int,
        run_date: str,
        language: str,
        *,
        telegram_enabled: bool | None = None,
        feishu_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> list[dict[str, Any]]:
        if not self.any_enabled(telegram_enabled=telegram_enabled, feishu_enabled=feishu_enabled, email_enabled=email_enabled):
            return []
        text = self._failure_notice_text(run_id, run_date, language)
        return self.send_text(
            text,
            run_date=run_date,
            summary_id=None,
            run_id=run_id,
            telegram_enabled=telegram_enabled,
            feishu_enabled=feishu_enabled,
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
        feishu_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> list[dict[str, Any]]:
        settings = self._row(private=True)
        results: list[dict[str, Any]] = []
        if settings["telegram_enabled"] and (telegram_enabled is not False):
            results.append(self._send_telegram(settings, text, summary_id, run_id))
        if settings["feishu_enabled"] and (feishu_enabled is not False):
            results.append(self._send_feishu(settings, text, summary_id, run_id))
        if settings["email_enabled"] and (email_enabled is not False):
            results.append(self._send_email(settings, text, run_date, summary_id, run_id))
        return results

    def any_enabled(self, *, telegram_enabled: bool | None = None, feishu_enabled: bool | None = None, email_enabled: bool | None = None) -> bool:
        settings = self._row(private=True)
        return bool(
            (settings["telegram_enabled"] and telegram_enabled is not False)
            or (settings["feishu_enabled"] and feishu_enabled is not False)
            or (settings["email_enabled"] and email_enabled is not False)
        )

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

    def _failure_notice_text(self, run_id: int, run_date: str, language: str) -> str:
        run = self._run_context(run_id)
        title = self._delivery_title_for_run(run_id, run_date)
        rows = self._failed_run_videos(run_id)
        if language == "en":
            lines = [
                f"# {title} Failed",
                "",
                f"Status: {run.get('status') or 'failed'}",
                f"Failed videos: {run.get('failed_count') or len(rows)}",
            ]
            if run.get("error_message"):
                lines.append(f"Run reason: {_short_error(run['error_message'])}")
            for index, row in enumerate(rows[:3], start=1):
                lines.extend(
                    [
                        "",
                        f"## Failed Video {index}",
                        f"Channel: {_one_line(row.get('channel_name') or '-')}",
                        f"Source: {_one_line(row.get('source_name') or '-')}",
                        f"Video: {_one_line(row.get('video_title') or row.get('video_id') or '-')}",
                        f"Published: {_one_line(row.get('video_date') or '-')}",
                        f"Link: {_one_line(row.get('video_url') or _youtube_watch_url(row.get('video_id')))}",
                        f"Reason: {_short_error(row.get('error_message') or run.get('error_message') or '-')}",
                    ]
                )
            if len(rows) > 3:
                lines.extend(["", f"...and {len(rows) - 3} more failed videos."])
            return "\n".join(lines)

        lines = [
            f"# {title} 运行失败",
            "",
            f"状态：{run.get('status') or 'failed'}",
            f"失败视频数：{run.get('failed_count') or len(rows)}",
        ]
        if run.get("error_message"):
            lines.append(f"任务原因：{_short_error(run['error_message'])}")
        for index, row in enumerate(rows[:3], start=1):
            lines.extend(
                [
                    "",
                    f"## 失败视频 {index}",
                    f"频道：{_one_line(row.get('channel_name') or '-')}",
                    f"来源：{_one_line(row.get('source_name') or '-')}",
                    f"视频：{_one_line(row.get('video_title') or row.get('video_id') or '-')}",
                    f"发布时间：{_one_line(row.get('video_date') or '-')}",
                    f"链接：{_one_line(row.get('video_url') or _youtube_watch_url(row.get('video_id')))}",
                    f"原因：{_short_error(row.get('error_message') or run.get('error_message') or '-')}",
                ]
            )
        if len(rows) > 3:
            lines.extend(["", f"另有 {len(rows) - 3} 个失败视频，请到任务记录查看。"])
        return "\n".join(lines)

    def _failed_run_videos(self, run_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    drv.video_id,
                    drv.error_message,
                    COALESCE(NULLIF(drv.display_name_snapshot, ''), NULLIF(drv.source_name_snapshot, ''), NULLIF(s.display_name, ''), s.source_name) AS source_name,
                    COALESCE(s.channel_name, c.channel_name, v.channel_id) AS channel_name,
                    v.video_title,
                    v.video_url,
                    v.video_date
                FROM DailyRunVideos drv
                LEFT JOIN Videos v ON v.video_id = drv.video_id
                LEFT JOIN Sources s ON s.source_id = drv.source_id
                LEFT JOIN Channels c ON c.channel_id = v.channel_id
                WHERE drv.run_id = ?
                  AND drv.status = 'failed'
                ORDER BY drv.video_id
                """,
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def _send_feishu(self, settings: dict[str, Any], text: str, summary_id: int | None, run_id: int | None) -> dict[str, Any]:
        webhook_url = settings["feishu_webhook_url"] or ""
        if not webhook_url:
            return self._log(summary_id, run_id, "feishu", "failed", "", "Feishu webhook URL missing")
        try:
            messages = _feishu_message_parts(text)
            for message in messages:
                _post_feishu_message(webhook_url, message, settings["feishu_secret"] or "")
            detail = None if len(messages) == 1 else f"Sent {len(messages)} Feishu message parts"
            return self._log(summary_id, run_id, "feishu", "success", mask_webhook_url(webhook_url), detail)
        except Exception as exc:
            detail = str(exc)
            response = getattr(exc, "response", None)
            if response is not None and getattr(response, "text", ""):
                detail = f"{detail}: {response.text}"
            return self._log(summary_id, run_id, "feishu", "failed", mask_webhook_url(webhook_url), detail)

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
        safe_error = _mask_delivery_error(error or "")
        if status == "success":
            logger.info("delivery %s success run_id=%s summary_id=%s", channel, run_id, summary_id)
        else:
            logger.warning(
                "delivery %s failed run_id=%s summary_id=%s reason=%s",
                channel,
                run_id,
                summary_id,
                _short_error(safe_error),
            )
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
            row["error_message"] = _mask_feishu_webhook(row["error_message"])
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
                        feishu_enabled, feishu_webhook_url, feishu_secret,
                        email_enabled, smtp_host, smtp_port, smtp_username, smtp_password,
                        smtp_use_tls, smtp_use_ssl, email_from, email_to_json,
                        email_subject_template, email_attach_markdown
                    )
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(as_bool(self.settings.telegram_enabled)),
                        self.settings.telegram_bot_token,
                        self.settings.telegram_chat_id,
                        self.settings.telegram_parse_mode,
                        int(as_bool(self.settings.telegram_send_as_file_if_too_long)),
                        int(as_bool(self.settings.feishu_enabled)),
                        self.settings.feishu_webhook_url,
                        self.settings.feishu_secret,
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
        self.settings.feishu_enabled = "true" if values["feishu_enabled"] else "false"
        self.settings.feishu_webhook_url = values["feishu_webhook_url"]
        self.settings.feishu_secret = values["feishu_secret"]
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


def _mask_feishu_webhook(value: str) -> str:
    return re.sub(r"(?<=/bot/v2/hook/)[^/?#\s]+", "***", value)


def _mask_delivery_error(value: str) -> str:
    return _mask_feishu_webhook(_mask_telegram_token(value))


def _post_feishu_message(webhook_url: str, text: str, secret: str | None = None) -> None:
    payload: dict[str, Any] = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = str(int(time.time()))
        sign_source = f"{timestamp}\n{secret}".encode("utf-8")
        payload["timestamp"] = timestamp
        payload["sign"] = base64.b64encode(hmac.new(sign_source, b"", digestmod=hashlib.sha256).digest()).decode("utf-8")
    response = requests.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()
    try:
        data = response.json()
    except Exception:
        return
    code = data.get("code", data.get("StatusCode", 0))
    if code not in (0, "0"):
        raise RuntimeError(data.get("msg") or data.get("StatusMessage") or json.dumps(data, ensure_ascii=False))


def _feishu_message_parts(text: str, limit: int = 3900) -> list[str]:
    chunks = _split_text_for_telegram(text, limit=limit - 16)
    if len(chunks) <= 1:
        return chunks
    total = len(chunks)
    return [f"[{index}/{total}]\n{chunk}" for index, chunk in enumerate(chunks, start=1)]


def _one_line(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _short_error(value: Any, limit: int = 220) -> str:
    text = _one_line(value)
    if not text:
        return "-"
    transcript_match = re.search(r"Could not fetch transcript for ([\w-]+)", text)
    subtitle_match = re.search(r"yt-dlp could not fetch subtitles for ([\w-]+)", text)
    if transcript_match and subtitle_match:
        return f"Could not fetch transcript: yt-dlp could not fetch subtitles for {subtitle_match.group(1)}"
    if transcript_match:
        return f"Could not fetch transcript for {transcript_match.group(1)}"
    text = re.sub(r"^Could not fetch transcript for [\w-]+:\s*", "Could not fetch transcript: ", text)
    text = text.split("; ", 1)[0]
    return f"{text[: limit - 3]}..." if len(text) > limit else text


def _youtube_watch_url(video_id: Any) -> str:
    video = _one_line(video_id)
    return f"https://www.youtube.com/watch?v={video}" if video else "-"


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
