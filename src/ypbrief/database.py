from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .cleaner import TranscriptSegment


_UNSET = object()

_LEGACY_BUILTIN_PROVIDER_MODELS = {
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
    "claude": "claude-3-5-sonnet-latest",
    "siliconflow": "Qwen/Qwen2.5-72B-Instruct",
    "openrouter": "openai/gpt-4.1-mini",
    "grok": "grok-4",
    "deepseek": "deepseek-chat",
}


class Database:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS Channels (
                    channel_id TEXT PRIMARY KEY,
                    channel_name TEXT NOT NULL,
                    channel_url TEXT NOT NULL,
                    handle TEXT,
                    uploads_playlist_id TEXT,
                    last_checked_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS Sources (
                    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    display_name TEXT,
                    youtube_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    channel_id TEXT,
                    channel_name TEXT,
                    playlist_id TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_checked_at TEXT,
                    last_error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_type, youtube_id)
                );

                CREATE TABLE IF NOT EXISTS SourceGroups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT NOT NULL UNIQUE,
                    display_name TEXT,
                    description TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    digest_title TEXT,
                    digest_language TEXT NOT NULL DEFAULT 'zh',
                    run_time TEXT NOT NULL DEFAULT '07:00',
                    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                    max_videos_per_source INTEGER NOT NULL DEFAULT 10,
                    telegram_enabled INTEGER,
                    email_enabled INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS Videos (
                    video_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    video_title TEXT NOT NULL,
                    video_url TEXT NOT NULL,
                    video_date TEXT,
                    duration INTEGER,
                    status TEXT NOT NULL DEFAULT 'new',
                    transcript_raw_json TEXT,
                    transcript_raw_vtt TEXT,
                    transcript_clean TEXT,
                    summary_latest_id INTEGER,
                    error_message TEXT,
                    fetched_at TEXT,
                    cleaned_at TEXT,
                    summarized_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(channel_id) REFERENCES Channels(channel_id)
                );

                CREATE TABLE IF NOT EXISTS Subtitles (
                    subtitle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    stop_time TEXT NOT NULL,
                    start_seconds REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(video_id) REFERENCES Videos(video_id) ON DELETE CASCADE
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS Subtitles_fts
                USING fts5(text, content='Subtitles', content_rowid='subtitle_id');

                CREATE TRIGGER IF NOT EXISTS subtitles_ai AFTER INSERT ON Subtitles BEGIN
                    INSERT INTO Subtitles_fts(rowid, text) VALUES (new.subtitle_id, new.text);
                END;

                CREATE TRIGGER IF NOT EXISTS subtitles_ad AFTER DELETE ON Subtitles BEGIN
                    INSERT INTO Subtitles_fts(Subtitles_fts, rowid, text)
                    VALUES('delete', old.subtitle_id, old.text);
                END;

                CREATE TRIGGER IF NOT EXISTS subtitles_au AFTER UPDATE ON Subtitles BEGIN
                    INSERT INTO Subtitles_fts(Subtitles_fts, rowid, text)
                    VALUES('delete', old.subtitle_id, old.text);
                    INSERT INTO Subtitles_fts(rowid, text) VALUES (new.subtitle_id, new.text);
                END;

                CREATE TABLE IF NOT EXISTS Summaries (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_type TEXT NOT NULL,
                    video_id TEXT,
                    channel_id TEXT,
                    range_start TEXT,
                    range_end TEXT,
                    model_provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    provider_base_url TEXT,
                    prompt_version TEXT,
                    content_markdown TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(video_id) REFERENCES Videos(video_id),
                    FOREIGN KEY(channel_id) REFERENCES Channels(channel_id)
                );

                CREATE TABLE IF NOT EXISTS PromptTemplates (
                    prompt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_type TEXT NOT NULL,
                    prompt_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    language TEXT NOT NULL,
                    group_id INTEGER,
                    system_prompt TEXT,
                    user_template TEXT NOT NULL,
                    variables_json TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(group_id) REFERENCES SourceGroups(group_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ModelProfiles (
                    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    display_name TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(provider, model_name)
                );

                CREATE TABLE IF NOT EXISTS LLMProviderConfigs (
                    provider TEXT PRIMARY KEY,
                    provider_type TEXT NOT NULL,
                    display_name TEXT,
                    base_url TEXT,
                    api_key TEXT,
                    default_model TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS SourceVideos (
                    source_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    source_position INTEGER,
                    published_at TEXT,
                    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(source_id, video_id),
                    FOREIGN KEY(source_id) REFERENCES Sources(source_id) ON DELETE CASCADE,
                    FOREIGN KEY(video_id) REFERENCES Videos(video_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS DailyRuns (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    window_start TEXT,
                    window_end TEXT,
                    source_ids_json TEXT,
                    summary_id INTEGER,
                    included_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    error_message TEXT,
                    FOREIGN KEY(summary_id) REFERENCES Summaries(summary_id)
                );

                CREATE TABLE IF NOT EXISTS DailyRunVideos (
                    run_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    source_id INTEGER,
                    source_name_snapshot TEXT,
                    display_name_snapshot TEXT,
                    source_type_snapshot TEXT,
                    status TEXT NOT NULL,
                    action TEXT,
                    error_message TEXT,
                    summary_id INTEGER,
                    PRIMARY KEY(run_id, video_id, source_id),
                    FOREIGN KEY(run_id) REFERENCES DailyRuns(run_id) ON DELETE CASCADE,
                    FOREIGN KEY(video_id) REFERENCES Videos(video_id),
                    FOREIGN KEY(source_id) REFERENCES Sources(source_id),
                    FOREIGN KEY(summary_id) REFERENCES Summaries(summary_id)
                );

                CREATE TABLE IF NOT EXISTS ScheduledJobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_name TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                    run_time TEXT NOT NULL DEFAULT '07:00',
                    digest_language TEXT NOT NULL DEFAULT 'zh',
                    scope_type TEXT NOT NULL DEFAULT 'all_enabled',
                    group_ids_json TEXT,
                    source_ids_json TEXT,
                    window_mode TEXT NOT NULL DEFAULT 'last_1',
                    max_videos_per_source INTEGER,
                    process_missing_videos INTEGER NOT NULL DEFAULT 1,
                    retry_failed_once INTEGER NOT NULL DEFAULT 1,
                    send_empty_digest INTEGER NOT NULL DEFAULT 1,
                    telegram_enabled INTEGER NOT NULL DEFAULT 1,
                    email_enabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS DeliverySettings (
                    settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
                    telegram_enabled INTEGER NOT NULL DEFAULT 0,
                    telegram_bot_token TEXT,
                    telegram_chat_id TEXT,
                    telegram_parse_mode TEXT NOT NULL DEFAULT 'Markdown',
                    telegram_send_as_file_if_too_long INTEGER NOT NULL DEFAULT 1,
                    email_enabled INTEGER NOT NULL DEFAULT 0,
                    smtp_host TEXT,
                    smtp_port INTEGER DEFAULT 587,
                    smtp_username TEXT,
                    smtp_password TEXT,
                    smtp_use_tls INTEGER NOT NULL DEFAULT 1,
                    smtp_use_ssl INTEGER NOT NULL DEFAULT 0,
                    email_from TEXT,
                    email_to_json TEXT,
                    email_subject_template TEXT NOT NULL DEFAULT 'YPBrief 每日播客日报 - {{ run_date }}',
                    email_attach_markdown INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS DeliveryLogs (
                    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_id INTEGER,
                    run_id INTEGER,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target TEXT,
                    error_message TEXT,
                    sent_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(summary_id) REFERENCES Summaries(summary_id),
                    FOREIGN KEY(run_id) REFERENCES DailyRuns(run_id)
                );

                CREATE TABLE IF NOT EXISTS ApplicationSettings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            _ensure_column(conn, "Videos", "transcript_raw_vtt", "TEXT")
            _ensure_column(conn, "DailyRunVideos", "source_name_snapshot", "TEXT")
            _ensure_column(conn, "DailyRunVideos", "display_name_snapshot", "TEXT")
            _ensure_column(conn, "DailyRunVideos", "source_type_snapshot", "TEXT")
            _ensure_column(conn, "Sources", "group_id", "INTEGER REFERENCES SourceGroups(group_id)")
            _ensure_column(conn, "PromptTemplates", "group_id", "INTEGER REFERENCES SourceGroups(group_id)")
            _ensure_column(conn, "DailyRuns", "scheduled_job_id", "INTEGER REFERENCES ScheduledJobs(job_id)")
            conn.execute("UPDATE ScheduledJobs SET window_mode = 'last_7' WHERE window_mode = 'last_5'")
            for provider, model in _LEGACY_BUILTIN_PROVIDER_MODELS.items():
                conn.execute(
                    """
                    UPDATE LLMProviderConfigs
                    SET default_model = '',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE provider = ? AND default_model = ?
                    """,
                    (provider, model),
                )
            conn.execute(
                """
                UPDATE ModelProfiles
                SET display_name = model_name,
                    updated_at = CURRENT_TIMESTAMP
                WHERE display_name IS NULL
                   OR display_name = ''
                   OR display_name != model_name
                """
            )

    def upsert_source(
        self,
        source_type: str,
        source_name: str,
        youtube_id: str,
        url: str,
        display_name: str | None = None,
        channel_id: str | None = None,
        channel_name: str | None = None,
        playlist_id: str | None = None,
        enabled: bool = True,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO Sources(
                    source_type, source_name, display_name, youtube_id, url,
                    channel_id, channel_name, playlist_id, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, youtube_id) DO UPDATE SET
                    source_name=excluded.source_name,
                    display_name=excluded.display_name,
                    url=excluded.url,
                    channel_id=excluded.channel_id,
                    channel_name=excluded.channel_name,
                    playlist_id=excluded.playlist_id,
                    enabled=excluded.enabled,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING source_id
                """,
                (
                    source_type,
                    source_name,
                    display_name,
                    youtube_id,
                    url,
                    channel_id,
                    channel_name,
                    playlist_id,
                    1 if enabled else 0,
                ),
            )
            return int(cursor.fetchone()["source_id"])

    def list_sources(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = """
            SELECT s.*,
                   g.group_name,
                   COALESCE(NULLIF(g.display_name, ''), g.group_name) AS group_display_name
            FROM Sources s
            LEFT JOIN SourceGroups g ON g.group_id = s.group_id
        """
        params: tuple[Any, ...] = ()
        if enabled_only:
            query += " WHERE s.enabled = ?"
            params = (1,)
        query += " ORDER BY COALESCE(g.display_name, g.group_name, ''), s.source_type, s.source_name"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_source(self, source_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT s.*,
                       g.group_name,
                       COALESCE(NULLIF(g.display_name, ''), g.group_name) AS group_display_name
                FROM Sources s
                LEFT JOIN SourceGroups g ON g.group_id = s.group_id
                WHERE s.source_id = ?
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            raise KeyError(source_id)
        return dict(row)

    def get_source_by_identity(self, source_type: str, youtube_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT s.*,
                       g.group_name,
                       COALESCE(NULLIF(g.display_name, ''), g.group_name) AS group_display_name
                FROM Sources s
                LEFT JOIN SourceGroups g ON g.group_id = s.group_id
                WHERE s.source_type = ? AND s.youtube_id = ?
                """,
                (source_type, youtube_id),
            ).fetchone()
        return dict(row) if row else None

    def set_source_enabled(self, source_id: int, enabled: bool) -> None:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE Sources
                SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE source_id = ?
                """,
                (1 if enabled else 0, source_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(source_id)

    def delete_source(self, source_id: int) -> None:
        with self.connect() as conn:
            source = conn.execute("SELECT * FROM Sources WHERE source_id = ?", (source_id,)).fetchone()
            if source is None:
                raise KeyError(source_id)
            conn.execute(
                """
                UPDATE DailyRunVideos
                SET source_name_snapshot = COALESCE(source_name_snapshot, ?),
                    display_name_snapshot = COALESCE(display_name_snapshot, ?),
                    source_type_snapshot = COALESCE(source_type_snapshot, ?),
                    source_id = NULL
                WHERE source_id = ?
                """,
                (
                    source["source_name"],
                    source["display_name"],
                    source["source_type"],
                    source_id,
                ),
            )
            cursor = conn.execute("DELETE FROM Sources WHERE source_id = ?", (source_id,))
            if cursor.rowcount == 0:
                raise KeyError(source_id)

    def update_source(
        self,
        source_id: int,
        *,
        display_name: str | None | object = _UNSET,
        enabled: bool | None | object = _UNSET,
        group_id: int | None | object = _UNSET,
    ) -> dict[str, Any]:
        params: list[Any] = []
        assignments: list[str] = []
        if display_name is not _UNSET:
            assignments.append("display_name = ?")
            params.append(display_name)
        if enabled is not _UNSET:
            assignments.append("enabled = ?")
            params.append(1 if enabled else 0)
        if group_id is not _UNSET:
            assignments.append("group_id = ?")
            params.append(group_id)
        if not assignments:
            return self.get_source(source_id)
        params.append(source_id)
        with self.connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE Sources
                SET {", ".join(assignments)},
                    updated_at = CURRENT_TIMESTAMP
                WHERE source_id = ?
                """,
                tuple(params),
            )
            if cursor.rowcount == 0:
                raise KeyError(source_id)
        return self.get_source(source_id)

    def list_source_groups(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = """
            SELECT g.*,
                   COUNT(s.source_id) AS source_count
            FROM SourceGroups g
            LEFT JOIN Sources s ON s.group_id = g.group_id
        """
        params: tuple[Any, ...] = ()
        if enabled_only:
            query += " WHERE g.enabled = ?"
            params = (1,)
        query += " GROUP BY g.group_id ORDER BY COALESCE(g.display_name, g.group_name)"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_source_group(self, group_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT g.*,
                       COUNT(s.source_id) AS source_count
                FROM SourceGroups g
                LEFT JOIN Sources s ON s.group_id = g.group_id
                WHERE g.group_id = ?
                GROUP BY g.group_id
                """,
                (group_id,),
            ).fetchone()
        if row is None:
            raise KeyError(group_id)
        return dict(row)

    def save_source_group(
        self,
        *,
        group_name: str,
        display_name: str | None = None,
        description: str | None = None,
        enabled: bool = True,
        digest_title: str | None = None,
        digest_language: str = "zh",
        run_time: str = "07:00",
        timezone: str = "Asia/Shanghai",
        max_videos_per_source: int = 10,
        telegram_enabled: bool | None = None,
        email_enabled: bool | None = None,
        group_id: int | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            if group_id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO SourceGroups(
                        group_name, display_name, description, enabled, digest_title,
                        digest_language, run_time, timezone, max_videos_per_source,
                        telegram_enabled, email_enabled
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group_name,
                        display_name,
                        description,
                        1 if enabled else 0,
                        digest_title,
                        digest_language,
                        run_time,
                        timezone,
                        max_videos_per_source,
                        None if telegram_enabled is None else 1 if telegram_enabled else 0,
                        None if email_enabled is None else 1 if email_enabled else 0,
                    ),
                )
                group_id = int(cursor.lastrowid)
            else:
                cursor = conn.execute(
                    """
                    UPDATE SourceGroups
                    SET group_name = ?,
                        display_name = ?,
                        description = ?,
                        enabled = ?,
                        digest_title = ?,
                        digest_language = ?,
                        run_time = ?,
                        timezone = ?,
                        max_videos_per_source = ?,
                        telegram_enabled = ?,
                        email_enabled = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE group_id = ?
                    """,
                    (
                        group_name,
                        display_name,
                        description,
                        1 if enabled else 0,
                        digest_title,
                        digest_language,
                        run_time,
                        timezone,
                        max_videos_per_source,
                        None if telegram_enabled is None else 1 if telegram_enabled else 0,
                        None if email_enabled is None else 1 if email_enabled else 0,
                        group_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise KeyError(group_id)
        return self.get_source_group(group_id)

    def delete_source_group(self, group_id: int) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT group_id FROM SourceGroups WHERE group_id = ?", (group_id,)).fetchone()
            if row is None:
                raise KeyError(group_id)
            conn.execute(
                """
                UPDATE Sources
                SET group_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE group_id = ?
                """,
                (group_id,),
            )
            conn.execute(
                """
                UPDATE PromptTemplates
                SET group_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE group_id = ?
                """,
                (group_id,),
            )
            conn.execute("DELETE FROM SourceGroups WHERE group_id = ?", (group_id,))

    def list_scheduled_jobs(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM ScheduledJobs
                ORDER BY enabled DESC, run_time, job_name, job_id
                """
            ).fetchall()
        return [_scheduled_job_public(dict(row)) for row in rows]

    def get_scheduled_job(self, job_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM ScheduledJobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return _scheduled_job_public(dict(row))

    def save_scheduled_job(self, *, job_id: int | None = None, **payload: Any) -> dict[str, Any]:
        current = self.get_scheduled_job(job_id) if job_id is not None else {}
        values = _scheduled_job_values({**current, **payload})
        with self.connect() as conn:
            if job_id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO ScheduledJobs(
                        job_name, enabled, timezone, run_time, digest_language, scope_type,
                        group_ids_json, source_ids_json, window_mode, max_videos_per_source,
                        process_missing_videos, retry_failed_once, send_empty_digest,
                        telegram_enabled, email_enabled
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values["job_name"],
                        values["enabled"],
                        values["timezone"],
                        values["run_time"],
                        values["digest_language"],
                        values["scope_type"],
                        values["group_ids_json"],
                        values["source_ids_json"],
                        values["window_mode"],
                        values["max_videos_per_source"],
                        values["process_missing_videos"],
                        values["retry_failed_once"],
                        values["send_empty_digest"],
                        values["telegram_enabled"],
                        values["email_enabled"],
                    ),
                )
                job_id = int(cursor.lastrowid)
            else:
                cursor = conn.execute(
                    """
                    UPDATE ScheduledJobs
                    SET job_name = ?,
                        enabled = ?,
                        timezone = ?,
                        run_time = ?,
                        digest_language = ?,
                        scope_type = ?,
                        group_ids_json = ?,
                        source_ids_json = ?,
                        window_mode = ?,
                        max_videos_per_source = ?,
                        process_missing_videos = ?,
                        retry_failed_once = ?,
                        send_empty_digest = ?,
                        telegram_enabled = ?,
                        email_enabled = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                    """,
                    (
                        values["job_name"],
                        values["enabled"],
                        values["timezone"],
                        values["run_time"],
                        values["digest_language"],
                        values["scope_type"],
                        values["group_ids_json"],
                        values["source_ids_json"],
                        values["window_mode"],
                        values["max_videos_per_source"],
                        values["process_missing_videos"],
                        values["retry_failed_once"],
                        values["send_empty_digest"],
                        values["telegram_enabled"],
                        values["email_enabled"],
                        job_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise KeyError(job_id)
        return self.get_scheduled_job(job_id)

    def delete_scheduled_job(self, job_id: int) -> None:
        with self.connect() as conn:
            existing = conn.execute("SELECT job_id FROM ScheduledJobs WHERE job_id = ?", (job_id,)).fetchone()
            if existing is None:
                raise KeyError(job_id)
            conn.execute("UPDATE DailyRuns SET scheduled_job_id = NULL WHERE scheduled_job_id = ?", (job_id,))
            cursor = conn.execute("DELETE FROM ScheduledJobs WHERE job_id = ?", (job_id,))
            if cursor.rowcount == 0:
                raise KeyError(job_id)

    def list_scheduled_job_runs(self, job_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT r.*, j.job_name AS scheduled_job_name
                FROM DailyRuns r
                LEFT JOIN ScheduledJobs j ON j.job_id = r.scheduled_job_id
                WHERE r.scheduled_job_id = ?
                ORDER BY r.created_at DESC, r.run_id DESC
                LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def ensure_default_scheduled_job(self, defaults: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM ScheduledJobs ORDER BY job_id LIMIT 1").fetchone()
        if row is not None:
            return _scheduled_job_public(dict(row))
        return self.save_scheduled_job(**defaults)

    def upsert_channel(
        self,
        channel_id: str,
        channel_name: str,
        channel_url: str,
        handle: str | None = None,
        uploads_playlist_id: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO Channels(channel_id, channel_name, channel_url, handle, uploads_playlist_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    channel_name=excluded.channel_name,
                    channel_url=excluded.channel_url,
                    handle=COALESCE(excluded.handle, Channels.handle),
                    uploads_playlist_id=COALESCE(excluded.uploads_playlist_id, Channels.uploads_playlist_id),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (channel_id, channel_name, channel_url, handle, uploads_playlist_id),
            )

    def list_channels(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM Channels ORDER BY channel_name"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_channel(self, channel_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM Channels WHERE channel_id = ? OR channel_name = ? OR handle = ?",
                (channel_id, channel_id, channel_id),
            ).fetchone()
        if row is None:
            raise KeyError(channel_id)
        return dict(row)

    def delete_channel(self, channel_ref: str) -> None:
        channel = self.get_channel(channel_ref)
        channel_id = channel["channel_id"]
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM Subtitles WHERE video_id IN (SELECT video_id FROM Videos WHERE channel_id = ?)",
                (channel_id,),
            )
            conn.execute("DELETE FROM Summaries WHERE channel_id = ?", (channel_id,))
            conn.execute("DELETE FROM Videos WHERE channel_id = ?", (channel_id,))
            conn.execute("DELETE FROM Channels WHERE channel_id = ?", (channel_id,))

    def upsert_video(
        self,
        video_id: str,
        channel_id: str,
        video_title: str,
        video_url: str,
        video_date: str | None = None,
        duration: int | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO Videos(video_id, channel_id, video_title, video_url, video_date, duration)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    channel_id=excluded.channel_id,
                    video_title=excluded.video_title,
                    video_url=excluded.video_url,
                    video_date=excluded.video_date,
                    duration=excluded.duration,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (video_id, channel_id, video_title, video_url, video_date, duration),
            )

    def mark_video_failed(self, video_id: str, error_message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE Videos
                SET status = 'failed',
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE video_id = ?
                """,
                (error_message, video_id),
            )

    def mark_video_skipped(self, video_id: str, reason: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE Videos
                SET status = 'skipped',
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE video_id = ?
                """,
                (reason, video_id),
            )

    def save_transcript(
        self,
        video_id: str,
        raw_json: str,
        clean_text: str,
        segments: list[TranscriptSegment],
        raw_vtt: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM Subtitles WHERE video_id = ?", (video_id,))
            conn.execute(
                """
                UPDATE Videos
                SET transcript_raw_json = ?,
                    transcript_raw_vtt = ?,
                    transcript_clean = ?,
                    status = 'cleaned',
                    fetched_at = COALESCE(fetched_at, CURRENT_TIMESTAMP),
                    cleaned_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE video_id = ?
                """,
                (raw_json, raw_vtt, clean_text, video_id),
            )
            conn.executemany(
                """
                INSERT INTO Subtitles(video_id, start_time, stop_time, start_seconds, duration_seconds, text)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        video_id,
                        _format_timestamp(segment.start),
                        _format_timestamp(segment.end),
                        segment.start,
                        segment.duration,
                        segment.text,
                    )
                    for segment in segments
                ],
            )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.video_id, s.start_time, s.stop_time, s.text, v.video_title, v.video_url
                FROM Subtitles_fts f
                JOIN Subtitles s ON s.subtitle_id = f.rowid
                JOIN Videos v ON v.video_id = s.video_id
                WHERE Subtitles_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_summary(
        self,
        summary_type: str,
        content_markdown: str,
        provider: str,
        model: str,
        video_id: str | None = None,
        channel_id: str | None = None,
        range_start: str | None = None,
        range_end: str | None = None,
        provider_base_url: str | None = None,
        prompt_version: str | None = "v1",
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO Summaries(
                    summary_type, video_id, channel_id, range_start, range_end,
                    model_provider, model_name, provider_base_url, prompt_version, content_markdown
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_type,
                    video_id,
                    channel_id,
                    range_start,
                    range_end,
                    provider,
                    model,
                    provider_base_url,
                    prompt_version,
                    content_markdown,
                ),
            )
            summary_id = int(cursor.lastrowid)
            if video_id:
                conn.execute(
                    """
                    UPDATE Videos
                    SET status = 'summarized',
                        summary_latest_id = ?,
                        summarized_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                    """,
                    (summary_id, video_id),
                )
        return summary_id

    def get_video(self, video_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT v.*, c.channel_name
                FROM Videos v
                JOIN Channels c ON c.channel_id = v.channel_id
                WHERE v.video_id = ?
                """,
                (video_id,),
            ).fetchone()
        if row is None:
            raise KeyError(video_id)
        return dict(row)

    def get_video_transcript(self, video_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT v.video_id, v.video_title, v.video_url, v.video_date,
                       v.fetched_at, v.transcript_raw_json, v.transcript_raw_vtt, v.transcript_clean,
                       c.channel_name
                FROM Videos v
                JOIN Channels c ON c.channel_id = v.channel_id
                WHERE v.video_id = ?
                """,
                (video_id,),
            ).fetchone()
        if row is None:
            raise KeyError(video_id)
        return dict(row)

    def get_summary(self, summary_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM Summaries WHERE summary_id = ?", (summary_id,)).fetchone()
        if row is None:
            raise KeyError(summary_id)
        return dict(row)

    def list_prompt_templates(self, group_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if group_id == -1:
                rows = conn.execute(
                    """
                    SELECT p.*,
                           g.group_name,
                           COALESCE(NULLIF(g.display_name, ''), g.group_name) AS group_display_name
                    FROM PromptTemplates p
                    LEFT JOIN SourceGroups g ON g.group_id = p.group_id
                    ORDER BY COALESCE(g.display_name, g.group_name, ''),
                             CASE p.prompt_type WHEN 'video_summary' THEN 0 WHEN 'daily_digest' THEN 1 ELSE 99 END,
                             p.created_at DESC,
                             p.prompt_id DESC
                    """
                ).fetchall()
            elif group_id is None:
                rows = conn.execute(
                    """
                    SELECT p.*,
                           g.group_name,
                           COALESCE(NULLIF(g.display_name, ''), g.group_name) AS group_display_name
                    FROM PromptTemplates p
                    LEFT JOIN SourceGroups g ON g.group_id = p.group_id
                    WHERE p.group_id IS NULL
                    ORDER BY CASE p.prompt_type WHEN 'video_summary' THEN 0 WHEN 'daily_digest' THEN 1 ELSE 99 END,
                             p.created_at DESC,
                             p.prompt_id DESC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT p.*,
                           g.group_name,
                           COALESCE(NULLIF(g.display_name, ''), g.group_name) AS group_display_name
                    FROM PromptTemplates p
                    LEFT JOIN SourceGroups g ON g.group_id = p.group_id
                    WHERE p.group_id = ?
                    ORDER BY CASE p.prompt_type WHEN 'video_summary' THEN 0 WHEN 'daily_digest' THEN 1 ELSE 99 END,
                             p.created_at DESC,
                             p.prompt_id DESC
                    """,
                    (group_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_prompt_template(self, prompt_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT p.*,
                       g.group_name,
                       COALESCE(NULLIF(g.display_name, ''), g.group_name) AS group_display_name
                FROM PromptTemplates p
                LEFT JOIN SourceGroups g ON g.group_id = p.group_id
                WHERE p.prompt_id = ?
                """,
                (prompt_id,),
            ).fetchone()
        if row is None:
            raise KeyError(prompt_id)
        return dict(row)

    def create_prompt_template(
        self,
        *,
        prompt_type: str,
        prompt_name: str,
        version: str,
        language: str,
        system_prompt: str,
        user_template: str,
        variables_json: str,
        is_active: bool,
        group_id: int | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            if is_active:
                if group_id is None:
                    conn.execute(
                        """
                        UPDATE PromptTemplates
                        SET is_active = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE prompt_type = ? AND group_id IS NULL
                        """,
                        (prompt_type,),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE PromptTemplates
                        SET is_active = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE prompt_type = ? AND group_id = ?
                        """,
                        (prompt_type, group_id),
                    )
            cursor = conn.execute(
                """
                INSERT INTO PromptTemplates(
                    prompt_type, prompt_name, version, language, group_id,
                    system_prompt, user_template, variables_json, is_active, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prompt_type,
                    prompt_name,
                    version,
                    language,
                    group_id,
                    system_prompt,
                    user_template,
                    variables_json,
                    1 if is_active else 0,
                    notes,
                ),
            )
            prompt_id = int(cursor.lastrowid)
        return self.get_prompt_template(prompt_id)

    def activate_prompt_template(self, prompt_id: int) -> dict[str, Any]:
        prompt = self.get_prompt_template(prompt_id)
        with self.connect() as conn:
            if prompt["group_id"] is None:
                conn.execute(
                    """
                    UPDATE PromptTemplates
                    SET is_active = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE prompt_type = ? AND group_id IS NULL
                    """,
                    (prompt["prompt_type"],),
                )
            else:
                conn.execute(
                    """
                    UPDATE PromptTemplates
                    SET is_active = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE prompt_type = ? AND group_id = ?
                    """,
                    (prompt["prompt_type"], prompt["group_id"]),
                )
            conn.execute(
                """
                UPDATE PromptTemplates
                SET is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE prompt_id = ?
                """,
                (prompt_id,),
            )
        return self.get_prompt_template(prompt_id)


def _format_timestamp(seconds: float) -> str:
    whole_seconds = int(seconds)
    millis = int(round((seconds - whole_seconds) * 1000))
    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    secs = whole_seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _scheduled_job_values(payload: dict[str, Any]) -> dict[str, Any]:
    scope_type = payload.get("scope_type") or "all_enabled"
    window_mode = payload.get("window_mode") or "last_1"
    if scope_type not in {"all_enabled", "groups", "sources"}:
        raise ValueError("scope_type must be all_enabled, groups, or sources")
    if window_mode not in {"last_1", "last_3", "last_7", "all_time"}:
        raise ValueError("window_mode must be last_1, last_3, last_7, or all_time")
    digest_language = payload.get("digest_language") or "zh"
    if digest_language not in {"zh", "en"}:
        raise ValueError("digest_language must be zh or en")
    max_videos = payload.get("max_videos_per_source", 10)
    return {
        "job_name": (payload.get("job_name") or "Default Daily Job").strip() or "Default Daily Job",
        "enabled": 1 if payload.get("enabled", True) else 0,
        "timezone": payload.get("timezone") or "Asia/Shanghai",
        "run_time": payload.get("run_time") or "07:00",
        "digest_language": digest_language,
        "scope_type": scope_type,
        "group_ids_json": json.dumps([int(item) for item in payload.get("group_ids", [])]),
        "source_ids_json": json.dumps([int(item) for item in payload.get("source_ids", [])]),
        "window_mode": window_mode,
        "max_videos_per_source": None if max_videos is None else int(max_videos),
        "process_missing_videos": 1 if payload.get("process_missing_videos", True) else 0,
        "retry_failed_once": 1 if payload.get("retry_failed_once", True) else 0,
        "send_empty_digest": 1 if payload.get("send_empty_digest", True) else 0,
        "telegram_enabled": 1 if payload.get("telegram_enabled", True) else 0,
        "email_enabled": 1 if payload.get("email_enabled", False) else 0,
    }


def _scheduled_job_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "enabled": bool(row.get("enabled")),
        "group_ids": json.loads(row.get("group_ids_json") or "[]"),
        "source_ids": json.loads(row.get("source_ids_json") or "[]"),
        "process_missing_videos": bool(row.get("process_missing_videos")),
        "retry_failed_once": bool(row.get("retry_failed_once")),
        "send_empty_digest": bool(row.get("send_empty_digest")),
        "telegram_enabled": bool(row.get("telegram_enabled")),
        "email_enabled": bool(row.get("email_enabled")),
    }
