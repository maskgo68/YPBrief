from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import re
import secrets
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ypbrief.config import Settings, load_settings
from ypbrief.daily import DailyDigestService, DigestRunService, daily_artifact_paths
from ypbrief.database import Database
from ypbrief.delivery import DeliveryService, as_bool, mask_secret
from ypbrief.delivery import _post_telegram_message, _telegram_message_parts
from ypbrief.llm import ConfigError
from ypbrief.prompts import DatabasePromptService
from ypbrief.provider_config import (
    BUILTIN_PROVIDER_DEFAULTS as BUILTIN_LLM_PROVIDERS,
    PROVIDER_ENV_KEYS,
    active_model as _active_model,
    create_provider_from_database,
    get_effective_provider_config as _get_llm_provider_effective,
    normalize_provider as _normalize_provider,
    provider_from_config as _provider_from_config,
    sync_provider_config_to_settings as _sync_provider_config_to_settings,
)
from ypbrief.scheduler import SchedulerService
from ypbrief.sources import SourceService
from ypbrief.transcripts import TranscriptFetcher
from ypbrief.video_processor import VideoProcessor, parse_video_id
from ypbrief.youtube import YouTubeDataClient


logger = logging.getLogger(__name__)


class PromptCreate(BaseModel):
    prompt_type: str
    prompt_name: str | None = None
    language: str = "auto"
    group_id: int | None = None
    system_prompt: str | None = ""
    user_template: str
    activate: bool = True


class PromptPreview(BaseModel):
    values: dict[str, Any]


class SourceCreate(BaseModel):
    source_input: str
    source_type: str | None = None
    name: str | None = None
    display_name: str | None = None
    enabled: bool = True
    group_id: int | None = None


class SourceBulkAdd(BaseModel):
    lines: list[str] = []
    text: str | None = None
    source_type: str | None = None
    group_id: int | None = None


class SourceUpdate(BaseModel):
    display_name: str | None = None
    enabled: bool | None = None
    group_id: int | None = None


class SourceGroupCreate(BaseModel):
    group_name: str
    display_name: str | None = None
    description: str | None = None
    enabled: bool = True
    digest_title: str | None = None
    digest_language: str = "zh"
    run_time: str = "07:00"
    timezone: str = "Asia/Shanghai"
    max_videos_per_source: int = 10
    telegram_enabled: bool | None = None
    email_enabled: bool | None = None


class SourceGroupUpdate(BaseModel):
    group_name: str | None = None
    display_name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    digest_title: str | None = None
    digest_language: str | None = None
    run_time: str | None = None
    timezone: str | None = None
    max_videos_per_source: int | None = None
    telegram_enabled: bool | None = None
    email_enabled: bool | None = None


class ModelProfileCreate(BaseModel):
    provider: str
    model_name: str
    activate: bool = False


class ModelProfileUpdate(BaseModel):
    provider: str | None = None
    model_name: str | None = None
    is_active: bool | None = None


class ModelProfileTest(BaseModel):
    provider: str
    model_name: str


class VideoProcessUrl(BaseModel):
    video_url: str
    output_language: str = "auto"


class LLMProviderCreate(BaseModel):
    provider: str
    provider_type: str
    display_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool = True
    notes: str | None = None


class LLMProviderUpdate(BaseModel):
    provider_type: str | None = None
    display_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool | None = None
    notes: str | None = None


class ProxySettingsUpdate(BaseModel):
    enabled: bool | None = None
    youtube_proxy_http: str | None = None
    youtube_proxy_https: str | None = None
    iproyal_host: str | None = None
    iproyal_port: str | None = None
    iproyal_username: str | None = None
    iproyal_password: str | None = None
    yt_dlp_proxy: str | None = None


class YoutubeSettingsUpdate(BaseModel):
    api_key: str | None = None


class AuthLogin(BaseModel):
    password: str


class AuthPasswordChange(BaseModel):
    current_password: str
    new_password: str


class DigestRunCreate(BaseModel):
    source_ids: list[int] = []
    group_ids: list[int] = []
    use_all_enabled_sources: bool = False
    window_days: int | None = 1
    date_from: str | None = None
    date_to: str | None = None
    all_time: bool = False
    max_videos_per_source: int | None = 10
    reuse_existing_summaries: bool = True
    process_missing_videos: bool = True
    retry_failed_once: bool = True
    digest_language: str = "zh"
    run_date: str | None = None
    deliver_after_run: bool = False
    send_empty_digest: bool = False
    telegram_enabled: bool | None = None
    feishu_enabled: bool | None = None
    email_enabled: bool | None = None


class SchedulerRunNow(BaseModel):
    now: str | None = None
    background: bool = False


class ScheduledJobCreate(BaseModel):
    job_name: str = "Default Daily Job"
    enabled: bool = True
    timezone: str = "Asia/Shanghai"
    run_time: str = "07:00"
    digest_language: str = "zh"
    scope_type: str = "all_enabled"
    group_ids: list[int] = []
    source_ids: list[int] = []
    window_mode: str = "last_1"
    max_videos_per_source: int | None = 10
    process_missing_videos: bool = True
    retry_failed_once: bool = True
    send_empty_digest: bool = True
    telegram_enabled: bool = True
    feishu_enabled: bool = False
    email_enabled: bool = False


class ScheduledJobUpdate(BaseModel):
    job_name: str | None = None
    enabled: bool | None = None
    timezone: str | None = None
    run_time: str | None = None
    digest_language: str | None = None
    scope_type: str | None = None
    group_ids: list[int] | None = None
    source_ids: list[int] | None = None
    window_mode: str | None = None
    max_videos_per_source: int | None = None
    process_missing_videos: bool | None = None
    retry_failed_once: bool | None = None
    send_empty_digest: bool | None = None
    telegram_enabled: bool | None = None
    feishu_enabled: bool | None = None
    email_enabled: bool | None = None


class DeliverySettingsUpdate(BaseModel):
    telegram_enabled: bool | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_parse_mode: str | None = None
    telegram_send_as_file_if_too_long: bool | None = None
    feishu_enabled: bool | None = None
    feishu_webhook_url: str | None = None
    feishu_secret: str | None = None
    email_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None
    smtp_use_ssl: bool | None = None
    email_from: str | None = None
    email_to: list[str] | str | None = None
    email_subject_template: str | None = None
    email_attach_markdown: bool | None = None


class DeliveryRequest(BaseModel):
    telegram_enabled: bool | None = None
    feishu_enabled: bool | None = None
    email_enabled: bool | None = None


def create_app(
    db: Database | None = None,
    settings: Settings | None = None,
    settings_override: dict[str, Any] | None = None,
    digest_runner: Any | None = None,
    env_file: str | Path | None = None,
) -> FastAPI:
    env_file = env_file or os.environ.get("YPBRIEF_ENV_FILE", "key.env")
    if settings is None:
        settings = Settings() if db is not None and str(env_file) == "key.env" else load_settings(env_file)
    env_path = Path(env_file)
    for key, value in (settings_override or {}).items():
        setattr(settings, key, value)
    db = db or Database(settings.db_path)
    db.initialize()
    DatabasePromptService(db, settings.prompt_file).ensure_defaults()

    app = FastAPI(title="YPBrief API")
    app.state.db = db
    app.state.settings = settings
    app.state.auth_secret = secrets.token_urlsafe(32)
    app.state.login_failures = {}

    @app.middleware("http")
    async def require_api_auth(request: Request, call_next):
        response = None
        if not _auth_required(settings):
            response = await call_next(request)
        elif request.method == "OPTIONS":
            response = await call_next(request)
        else:
            path = request.url.path
            if not path.startswith("/api/") or path in {"/api/auth/status", "/api/auth/login"} or path.startswith("/api/telegram/webhook/"):
                response = await call_next(request)
            elif _valid_auth_header(request.headers.get("authorization", ""), app.state.auth_secret):
                response = await call_next(request)
            else:
                response = JSONResponse({"detail": "Authentication required"}, status_code=401)
        _apply_security_headers(response)
        return response

    @app.get("/api/auth/status")
    def auth_status(request: Request) -> dict[str, Any]:
        required = _auth_required(settings)
        return {
            "auth_required": required,
            "authenticated": (not required) or _valid_auth_header(request.headers.get("authorization", ""), app.state.auth_secret),
        }

    @app.post("/api/auth/login")
    def auth_login(payload: AuthLogin, request: Request) -> dict[str, Any]:
        if not _auth_required(settings):
            return {"auth_required": False, "token": "", "expires_at": None}
        client_id = _client_identifier(request)
        if _login_rate_limited(app.state.login_failures, client_id):
            raise HTTPException(status_code=429, detail="Too many failed login attempts")
        if not hmac.compare_digest(payload.password, settings.access_password):
            _record_failed_login(app.state.login_failures, client_id)
            raise HTTPException(status_code=401, detail="Invalid password")
        _clear_failed_logins(app.state.login_failures, client_id)
        token, expires_at = _issue_auth_token(app.state.auth_secret)
        return {"auth_required": True, "token": token, "expires_at": expires_at}

    @app.patch("/api/auth/password")
    def change_auth_password(payload: AuthPasswordChange, request: Request) -> dict[str, Any]:
        new_password = payload.new_password.strip()
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        if _auth_required(settings) and not hmac.compare_digest(payload.current_password, settings.access_password):
            _record_failed_login(app.state.login_failures, _client_identifier(request))
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        settings.access_password = new_password
        _sync_access_password_to_database(db, new_password)
        _update_env_file(env_path, {"YPBRIEF_ACCESS_PASSWORD": new_password})
        app.state.auth_secret = secrets.token_urlsafe(32)
        app.state.login_failures = {}
        token, expires_at = _issue_auth_token(app.state.auth_secret)
        return {"auth_required": True, "token": token, "expires_at": expires_at}

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        active_model = _active_model(db)
        effective_provider = active_model["provider"] if active_model else settings.llm_provider
        effective_model = active_model["model_name"] if active_model else settings.llm_model
        return {
            "status": "ok",
            "database_path": str(settings.db_path),
            "export_dir": str(settings.export_dir),
            "youtube_api_key": bool(settings.youtube_data_api_key),
            "llm_provider": effective_provider,
            "llm_model": effective_model,
            "active_model": active_model,
            "provider_keys": _provider_key_status(db, settings),
            "gemini_api_key": bool(settings.gemini_api_key),
            "openai_api_key": bool(settings.openai_api_key),
            "proxy": bool(settings.youtube_proxy_url),
        }

    @app.post("/api/health/test-youtube")
    def test_youtube() -> dict[str, Any]:
        return {
            "configured": bool(settings.youtube_data_api_key),
            "message": "YOUTUBE_DATA_API_KEY configured" if settings.youtube_data_api_key else "YOUTUBE_DATA_API_KEY missing",
        }

    @app.post("/api/health/test-llm")
    def test_llm() -> dict[str, Any]:
        active_model = _active_model(db)
        provider = active_model["provider"] if active_model else settings.llm_provider
        model = active_model["model_name"] if active_model else settings.llm_model
        configured = _llm_configured(db, settings, provider)
        return {
            "configured": configured,
            "provider": provider,
            "model": model,
            "message": "LLM provider configured" if configured else "LLM provider key missing",
        }

    @app.post("/api/health/test-proxy")
    def test_proxy() -> dict[str, Any]:
        effective_proxy = settings.youtube_proxy_url
        return {
            "configured": bool(effective_proxy),
            "enabled": bool(effective_proxy),
            "message": "Proxy configured" if effective_proxy else "Proxy disabled or missing",
        }

    @app.post("/api/health/test-database")
    def test_database() -> dict[str, Any]:
        with db.connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"configured": True, "message": "Database connection ok"}

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        with db.connect() as conn:
            stats = {
                "sources": conn.execute("SELECT COUNT(*) AS count FROM Sources").fetchone()["count"],
                "enabled_sources": conn.execute("SELECT COUNT(*) AS count FROM Sources WHERE enabled = 1").fetchone()["count"],
                "videos": conn.execute("SELECT COUNT(*) AS count FROM Videos").fetchone()["count"],
                "summarized_videos": conn.execute("SELECT COUNT(*) AS count FROM Videos WHERE status = 'summarized' AND summary_latest_id IS NOT NULL").fetchone()["count"],
                "pending_videos": conn.execute("SELECT COUNT(*) AS count FROM Videos WHERE status != 'summarized' OR summary_latest_id IS NULL").fetchone()["count"],
                "failed_videos": conn.execute("SELECT COUNT(*) AS count FROM Videos WHERE status = 'failed'").fetchone()["count"],
                "digests": conn.execute("SELECT COUNT(*) AS count FROM Summaries WHERE summary_type = 'digest'").fetchone()["count"],
            }
            latest_digest_row = conn.execute(
                """
                SELECT *
                FROM Summaries
                WHERE summary_type = 'digest'
                ORDER BY created_at DESC, summary_id DESC
                LIMIT 1
                """
            ).fetchone()
            recent_videos = conn.execute(
                """
                SELECT v.video_id, v.video_title, v.video_url, v.video_date, v.status, c.channel_name
                FROM Videos v
                JOIN Channels c ON c.channel_id = v.channel_id
                WHERE v.status = 'summarized' AND v.summary_latest_id IS NOT NULL
                ORDER BY COALESCE(v.summarized_at, v.updated_at, v.cleaned_at, v.fetched_at, v.created_at) DESC,
                         COALESCE(v.video_date, '') DESC,
                         v.video_id DESC
                LIMIT 5
                """
            ).fetchall()
            latest_run = conn.execute(
                """
                SELECT *
                FROM DailyRuns
                ORDER BY created_at DESC, run_id DESC
                LIMIT 1
                """
            ).fetchone()
            recent_run_videos = conn.execute(
                """
                SELECT drv.run_id, drv.video_id, drv.source_id, drv.status, drv.action,
                       drv.error_message, drv.summary_id AS video_summary_id,
                       v.video_title, v.video_url, v.video_date,
                       c.channel_name,
                       COALESCE(s.source_name, drv.source_name_snapshot) AS source_name,
                       COALESCE(s.display_name, drv.display_name_snapshot) AS display_name,
                       COALESCE(s.source_type, drv.source_type_snapshot) AS source_type
                FROM DailyRunVideos drv
                LEFT JOIN Videos v ON v.video_id = drv.video_id
                LEFT JOIN Channels c ON c.channel_id = v.channel_id
                LEFT JOIN Sources s ON s.source_id = drv.source_id
                WHERE drv.status IN ('failed', 'skipped')
                ORDER BY drv.run_id DESC, CASE drv.status WHEN 'failed' THEN 0 ELSE 1 END, drv.video_id
                LIMIT 12
                """
            ).fetchall()

        latest_digest = _digest_preview(dict(latest_digest_row)) if latest_digest_row else None
        return {
            "stats": stats,
            "latest_digest": latest_digest,
            "recent_videos": [dict(row) for row in recent_videos],
            "latest_run": dict(latest_run) if latest_run else None,
            "recent_run_videos": [dict(row) for row in recent_run_videos],
        }

    @app.get("/api/sources")
    def list_sources() -> list[dict[str, Any]]:
        return db.list_sources()

    @app.get("/api/source-groups")
    def list_source_groups() -> list[dict[str, Any]]:
        return db.list_source_groups()

    @app.post("/api/source-groups")
    def create_source_group(payload: SourceGroupCreate) -> dict[str, Any]:
        try:
            return db.save_source_group(
                group_name=payload.group_name,
                display_name=payload.display_name,
                description=payload.description,
                enabled=payload.enabled,
                digest_title=payload.digest_title,
                digest_language=payload.digest_language,
                run_time=payload.run_time,
                timezone=payload.timezone,
                max_videos_per_source=payload.max_videos_per_source,
                telegram_enabled=payload.telegram_enabled,
                email_enabled=payload.email_enabled,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/source-groups/{group_id}")
    def update_source_group(group_id: int, payload: SourceGroupUpdate) -> dict[str, Any]:
        try:
            current = db.get_source_group(group_id)
            return db.save_source_group(
                group_id=group_id,
                group_name=payload.group_name or current["group_name"],
                display_name=payload.display_name if "display_name" in payload.model_fields_set else current.get("display_name"),
                description=payload.description if "description" in payload.model_fields_set else current.get("description"),
                enabled=payload.enabled if payload.enabled is not None else bool(current["enabled"]),
                digest_title=payload.digest_title if "digest_title" in payload.model_fields_set else current.get("digest_title"),
                digest_language=payload.digest_language or current["digest_language"],
                run_time=payload.run_time or current["run_time"],
                timezone=payload.timezone or current["timezone"],
                max_videos_per_source=payload.max_videos_per_source or current["max_videos_per_source"],
                telegram_enabled=payload.telegram_enabled if "telegram_enabled" in payload.model_fields_set else current.get("telegram_enabled"),
                email_enabled=payload.email_enabled if "email_enabled" in payload.model_fields_set else current.get("email_enabled"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Source group not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/source-groups/{group_id}")
    def delete_source_group(group_id: int) -> dict[str, bool]:
        try:
            db.delete_source_group(group_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Source group not found") from exc
        return {"deleted": True}

    @app.post("/api/sources")
    def create_source(payload: SourceCreate) -> dict[str, Any]:
        if not settings.youtube_data_api_key:
            raise HTTPException(status_code=400, detail="YOUTUBE_DATA_API_KEY is required")
        service = SourceService(db, YouTubeDataClient(settings.youtube_data_api_key))
        return service.add(
            payload.source_input,
            source_type=payload.source_type,  # type: ignore[arg-type]
            name=payload.name,
            display_name=payload.display_name,
            enabled=payload.enabled,
            group_id=payload.group_id,
        )

    @app.post("/api/sources/bulk-add")
    def bulk_add_sources(payload: SourceBulkAdd) -> dict[str, Any]:
        if not settings.youtube_data_api_key:
            raise HTTPException(status_code=400, detail="YOUTUBE_DATA_API_KEY is required")
        lines = list(payload.lines)
        if payload.text:
            lines.extend(payload.text.splitlines())
        if not lines:
            raise HTTPException(status_code=400, detail="At least one source line is required")
        if payload.group_id is not None:
            try:
                db.get_source_group(payload.group_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Source group not found") from exc
        service = SourceService(db, YouTubeDataClient(settings.youtube_data_api_key))
        try:
            return service.bulk_add_lines(
                lines,
                group_id=payload.group_id,
                source_type=payload.source_type,  # type: ignore[arg-type]
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sources/{source_id}/enable")
    def enable_source(source_id: int) -> dict[str, Any]:
        try:
            db.set_source_enabled(source_id, True)
            return db.get_source(source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Source not found") from exc

    @app.post("/api/sources/{source_id}/disable")
    def disable_source(source_id: int) -> dict[str, Any]:
        try:
            db.set_source_enabled(source_id, False)
            return db.get_source(source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Source not found") from exc

    @app.delete("/api/sources/{source_id}")
    def delete_source(source_id: int) -> dict[str, bool]:
        try:
            db.delete_source(source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Source not found") from exc
        return {"deleted": True}

    @app.patch("/api/sources/{source_id}")
    def update_source(source_id: int, payload: SourceUpdate) -> dict[str, Any]:
        try:
            fields = payload.model_fields_set
            update_kwargs: dict[str, Any] = {}
            if "display_name" in fields:
                update_kwargs["display_name"] = payload.display_name
            if "enabled" in fields:
                update_kwargs["enabled"] = payload.enabled
            if "group_id" in fields:
                update_kwargs["group_id"] = payload.group_id
            return db.update_source(source_id, **update_kwargs)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Source not found") from exc

    @app.post("/api/sources/import")
    def import_sources() -> dict[str, Any]:
        if not settings.youtube_data_api_key:
            raise HTTPException(status_code=400, detail="YOUTUBE_DATA_API_KEY is required")
        path = Path("sources.yaml")
        if not path.exists():
            raise HTTPException(status_code=404, detail="sources.yaml not found")
        count = SourceService(db, YouTubeDataClient(settings.youtube_data_api_key)).import_yaml(path)
        return {"imported": count}

    @app.post("/api/sources/save")
    def save_sources() -> dict[str, Any]:
        path = Path("sources.yaml")
        SourceService(db, YouTubeDataClient(settings.youtube_data_api_key or "not-required")).export_yaml(path)
        return {"path": str(path.resolve())}

    @app.get("/api/sources/export")
    def export_sources() -> dict[str, Any]:
        service = SourceService(db, YouTubeDataClient(settings.youtube_data_api_key or "not-required"))
        with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False, encoding="utf-8") as temp:
            temp_path = Path(temp.name)
        try:
            service.export_yaml(temp_path)
            content = temp_path.read_text(encoding="utf-8")
        finally:
            temp_path.unlink(missing_ok=True)
        return {"filename": "sources.yaml", "content": content, "path": "sources.yaml"}

    @app.get("/api/model-profiles")
    def list_model_profiles() -> list[dict[str, Any]]:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ModelProfiles ORDER BY provider, model_name"
            ).fetchall()
        models = [dict(row) for row in rows]
        for row in models:
            row["provider"] = _normalize_provider(row["provider"])
        has_active_database_model = any(row.get("is_active") for row in models)
        for row in models:
            row.pop("display_name", None)
        env_provider = _normalize_provider(settings.llm_provider)
        env_model_exists = any(
            row["provider"] == env_provider and row["model_name"] == settings.llm_model
            for row in models
        )
        if settings.llm_provider and settings.llm_model and not env_model_exists and not has_active_database_model:
            models.append(
                {
                    "model_id": 0,
                    "provider": env_provider,
                    "model_name": settings.llm_model,
                    "is_active": 1,
                    "created_at": None,
                    "updated_at": None,
                    "source": "key.env",
                }
            )
        return models

    @app.get("/api/llm-providers")
    def list_llm_providers() -> list[dict[str, Any]]:
        return _list_llm_providers(db, settings)

    @app.post("/api/llm-providers")
    def create_llm_provider(payload: LLMProviderCreate) -> dict[str, Any]:
        provider = _normalize_provider(payload.provider)
        _upsert_llm_provider_config(
            db,
            provider=provider,
            provider_type=payload.provider_type,
            display_name=payload.display_name,
            base_url=payload.base_url,
            api_key=payload.api_key,
            default_model=payload.default_model,
            enabled=payload.enabled,
            notes=payload.notes,
        )
        effective = _get_llm_provider_effective(db, settings, provider) or {}
        _sync_provider_to_settings(settings, provider, effective)
        _sync_provider_to_env(env_path, provider, effective)
        return _get_llm_provider_public(db, settings, provider)

    @app.patch("/api/llm-providers/{provider}")
    def update_llm_provider(provider: str, payload: LLMProviderUpdate) -> dict[str, Any]:
        provider = _normalize_provider(provider)
        current = _get_llm_provider_effective(db, settings, provider)
        if current is None:
            raise HTTPException(status_code=404, detail="LLM provider not found")
        _upsert_llm_provider_config(
            db,
            provider=provider,
            provider_type=payload.provider_type if payload.provider_type is not None else current["provider_type"],
            display_name=payload.display_name if payload.display_name is not None else current.get("display_name"),
            base_url=payload.base_url if payload.base_url is not None else current.get("base_url"),
            api_key=current.get("api_key") if payload.api_key is None else payload.api_key,
            default_model=payload.default_model if payload.default_model is not None else current.get("default_model"),
            enabled=payload.enabled if payload.enabled is not None else bool(current.get("enabled", 1)),
            notes=payload.notes if payload.notes is not None else current.get("notes"),
        )
        effective = _get_llm_provider_effective(db, settings, provider) or {}
        _sync_provider_to_settings(settings, provider, effective)
        _sync_provider_to_env(env_path, provider, effective)
        return _get_llm_provider_public(db, settings, provider)

    @app.delete("/api/llm-providers/{provider}")
    def delete_llm_provider(provider: str) -> dict[str, bool]:
        provider = _normalize_provider(provider)
        with db.connect() as conn:
            conn.execute("DELETE FROM LLMProviderConfigs WHERE provider = ?", (provider,))
        return {"deleted": True}

    @app.get("/api/proxy-settings")
    def get_proxy_settings() -> dict[str, Any]:
        return _proxy_settings_public(settings)

    @app.get("/api/youtube-settings")
    def get_youtube_settings() -> dict[str, Any]:
        return _youtube_settings_public(settings)

    @app.patch("/api/youtube-settings")
    def update_youtube_settings(payload: YoutubeSettingsUpdate) -> dict[str, Any]:
        env_updates: dict[str, str] = {}
        if payload.api_key is not None:
            api_key = payload.api_key.strip()
            settings.youtube_data_api_key = api_key
            env_updates["YOUTUBE_DATA_API_KEY"] = api_key
        _update_env_file(env_path, env_updates)
        return _youtube_settings_public(settings)

    @app.patch("/api/proxy-settings")
    def update_proxy_settings(payload: ProxySettingsUpdate) -> dict[str, Any]:
        field_updates: dict[str, str] = {}
        env_updates: dict[str, str] = {}
        proxy_fields = {
            "youtube_proxy_http": ("youtube_proxy_http", "YOUTUBE_PROXY_HTTP"),
            "youtube_proxy_https": ("youtube_proxy_https", "YOUTUBE_PROXY_HTTPS"),
            "iproyal_host": ("iproyal_proxy_host", "IPROYAL_PROXY_HOST"),
            "iproyal_port": ("iproyal_proxy_port", "IPROYAL_PROXY_PORT"),
            "iproyal_username": ("iproyal_proxy_username", "IPROYAL_PROXY_USERNAME"),
            "iproyal_password": ("iproyal_proxy_password", "IPROYAL_PROXY_PASSWORD"),
            "yt_dlp_proxy": ("yt_dlp_proxy", "YT_DLP_PROXY"),
        }
        if payload.enabled is not None:
            field_updates["youtube_proxy_enabled"] = "true" if payload.enabled else "false"
            env_updates["YOUTUBE_PROXY_ENABLED"] = field_updates["youtube_proxy_enabled"]
        for payload_field, (settings_field, env_key) in proxy_fields.items():
            value = getattr(payload, payload_field)
            if value is not None:
                field_updates[settings_field] = value.strip()
                env_updates[env_key] = value.strip()

        for key, value in field_updates.items():
            setattr(settings, key, value)
        _update_env_file(env_path, env_updates)
        return _proxy_settings_public(settings)

    @app.get("/api/scheduler/status")
    def scheduler_status() -> dict[str, Any]:
        with db.connect() as conn:
            latest = conn.execute(
                "SELECT * FROM DailyRuns ORDER BY created_at DESC, run_id DESC LIMIT 1"
            ).fetchone()
        service = _make_scheduler_service(db, settings, digest_runner)
        jobs = service.list_jobs()
        return {
            "jobs": jobs,
            "enabled_jobs": len([job for job in jobs if job["enabled"]]),
            "latest_run": dict(latest) if latest else None,
        }

    @app.get("/api/scheduler-settings")
    @app.patch("/api/scheduler-settings")
    def legacy_scheduler_settings_retired() -> None:
        raise HTTPException(status_code=404, detail="Legacy scheduler settings API retired")

    @app.post("/api/scheduler/run-now")
    def legacy_scheduler_run_now_retired() -> None:
        raise HTTPException(status_code=404, detail="Legacy scheduler run-now API retired")

    @app.get("/api/scheduled-jobs")
    def list_scheduled_jobs() -> list[dict[str, Any]]:
        service = _make_scheduler_service(db, settings, digest_runner)
        jobs = service.list_jobs()
        for job in jobs:
            job["recent_runs"] = service.list_job_runs(int(job["job_id"]), limit=5)
        return jobs

    @app.post("/api/scheduled-jobs")
    def create_scheduled_job(payload: ScheduledJobCreate) -> dict[str, Any]:
        try:
            job = _make_scheduler_service(db, settings, digest_runner).create_job(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _configure_background_scheduler(app, db, settings, digest_runner)
        return job

    @app.patch("/api/scheduled-jobs/{job_id}")
    def update_scheduled_job(job_id: int, payload: ScheduledJobUpdate) -> dict[str, Any]:
        try:
            job = _make_scheduler_service(db, settings, digest_runner).update_job(job_id, payload.model_dump(exclude_unset=True))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Scheduled job not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _configure_background_scheduler(app, db, settings, digest_runner)
        return job

    @app.delete("/api/scheduled-jobs/{job_id}")
    def delete_scheduled_job(job_id: int) -> dict[str, Any]:
        try:
            _make_scheduler_service(db, settings, digest_runner).delete_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Scheduled job not found") from exc
        _configure_background_scheduler(app, db, settings, digest_runner)
        return {"deleted": True}

    @app.post("/api/scheduled-jobs/{job_id}/run-now")
    def run_scheduled_job_now(job_id: int, background_tasks: BackgroundTasks, payload: SchedulerRunNow | None = None) -> dict[str, Any]:
        try:
            service = _make_scheduler_service(db, settings, digest_runner)
            service.get_job(job_id)
            if payload and payload.background:
                background_tasks.add_task(_run_scheduled_job_background, db, settings, digest_runner, job_id, payload.now)
                return {"status": "accepted", "job_id": job_id, "message": "Scheduled job submitted"}
            return service.run_job_now(job_id, payload.now if payload else None)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Scheduled job not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/scheduled-jobs/{job_id}/runs")
    def list_scheduled_job_runs(job_id: int, limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
        try:
            return _make_scheduler_service(db, settings, digest_runner).list_job_runs(job_id, limit=limit)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Scheduled job not found") from exc

    @app.get("/api/delivery-settings")
    def get_delivery_settings() -> dict[str, Any]:
        return DeliveryService(db, settings).get_settings()

    @app.patch("/api/delivery-settings")
    def update_delivery_settings(payload: DeliverySettingsUpdate) -> dict[str, Any]:
        data = payload.model_dump(exclude_unset=True)
        updated = DeliveryService(db, settings).update_settings(data)
        _update_env_file(env_path, _delivery_env_updates(updated, data))
        return updated

    @app.post("/api/delivery/test-telegram")
    def test_telegram_delivery() -> dict[str, Any]:
        service = DeliveryService(db, settings)
        result = service.send_text("YPBrief Telegram test", run_date=date.today().isoformat())
        telegram = next((item for item in result if item["channel"] == "telegram"), None)
        return telegram or {"status": "skipped", "error_message": "Telegram disabled"}

    @app.post("/api/delivery/test-email")
    def test_email_delivery() -> dict[str, Any]:
        service = DeliveryService(db, settings)
        result = service.send_text("YPBrief Email test", run_date=date.today().isoformat())
        email = next((item for item in result if item["channel"] == "email"), None)
        return email or {"status": "skipped", "error_message": "Email disabled"}

    @app.post("/api/delivery/test-feishu")
    def test_feishu_delivery() -> dict[str, Any]:
        service = DeliveryService(db, settings)
        result = service.send_text("YPBrief Feishu test", run_date=date.today().isoformat())
        feishu = next((item for item in result if item["channel"] == "feishu"), None)
        return feishu or {"status": "skipped", "error_message": "Feishu disabled"}

    @app.post("/api/summaries/{summary_id}/deliver")
    def deliver_summary(summary_id: int, payload: DeliveryRequest | None = None) -> dict[str, Any]:
        try:
            request = payload or DeliveryRequest()
            return {
                "deliveries": DeliveryService(db, settings).send_summary(
                    summary_id,
                    telegram_enabled=request.telegram_enabled,
                    feishu_enabled=request.feishu_enabled,
                    email_enabled=request.email_enabled,
                )
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Summary not found") from exc

    @app.post("/api/digests/{summary_id}/deliver")
    def deliver_digest(summary_id: int, payload: DeliveryRequest | None = None) -> dict[str, Any]:
        return deliver_summary(summary_id, payload)

    @app.get("/api/delivery-logs")
    def list_delivery_logs(job_id: int | None = None) -> list[dict[str, Any]]:
        return DeliveryService(db, settings).list_logs(limit=5, job_id=job_id)

    @app.post("/api/model-profiles")
    def create_model_profile(payload: ModelProfileCreate) -> dict[str, Any]:
        provider = _normalize_provider(payload.provider)
        with db.connect() as conn:
            if payload.activate:
                conn.execute("UPDATE ModelProfiles SET is_active = 0, updated_at = CURRENT_TIMESTAMP")
            cursor = conn.execute(
                """
                INSERT INTO ModelProfiles(provider, model_name, display_name, is_active)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(provider, model_name) DO UPDATE SET
                    display_name=excluded.display_name,
                    is_active=excluded.is_active,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING model_id
                """,
                (
                    provider,
                    payload.model_name,
                    payload.model_name,
                    1 if payload.activate else 0,
                ),
            )
            model_id = int(cursor.fetchone()["model_id"])
        if payload.activate:
            _sync_active_model_to_env(env_path, settings, provider, payload.model_name)
        return _get_model_profile(db, model_id)

    @app.post("/api/model-profiles/{model_id}/activate")
    def activate_model_profile(model_id: int) -> dict[str, Any]:
        with db.connect() as conn:
            conn.execute("UPDATE ModelProfiles SET is_active = 0, updated_at = CURRENT_TIMESTAMP")
            cursor = conn.execute(
                "UPDATE ModelProfiles SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE model_id = ?",
                (model_id,),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Model profile not found")
        model = _get_model_profile(db, model_id)
        _sync_active_model_to_env(env_path, settings, model["provider"], model["model_name"])
        return model

    @app.patch("/api/model-profiles/{model_id}")
    def update_model_profile(model_id: int, payload: ModelProfileUpdate) -> dict[str, Any]:
        current = _get_model_profile(db, model_id)
        provider = payload.provider if payload.provider is not None else current["provider"]
        model_name = payload.model_name if payload.model_name is not None else current["model_name"]
        with db.connect() as conn:
            if payload.is_active:
                conn.execute("UPDATE ModelProfiles SET is_active = 0, updated_at = CURRENT_TIMESTAMP")
            cursor = conn.execute(
                """
                UPDATE ModelProfiles
                SET provider = ?,
                    model_name = ?,
                    display_name = ?,
                    is_active = COALESCE(?, is_active),
                    updated_at = CURRENT_TIMESTAMP
                WHERE model_id = ?
                """,
                (
                    provider,
                    model_name,
                    model_name,
                    None if payload.is_active is None else 1 if payload.is_active else 0,
                    model_id,
                ),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Model profile not found")
        model = _get_model_profile(db, model_id)
        if model["is_active"]:
            _sync_active_model_to_env(env_path, settings, model["provider"], model["model_name"])
        return model

    @app.delete("/api/model-profiles/{model_id}")
    def delete_model_profile(model_id: int) -> dict[str, bool]:
        with db.connect() as conn:
            cursor = conn.execute("DELETE FROM ModelProfiles WHERE model_id = ?", (model_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Model profile not found")
        return {"deleted": True}

    @app.post("/api/model-profiles/test")
    def test_model_profile(payload: ModelProfileTest) -> dict[str, Any]:
        provider = _normalize_provider(payload.provider)
        config = _get_llm_provider_effective(db, settings, provider)
        if config is None:
            return {"ok": False, "configured": False, "provider": provider, "model": payload.model_name, "message": "Provider not found"}
        try:
            llm = _provider_from_config(config, payload.model_name)
            content = llm.summarize(
                "Reply with exactly: ok",
                "Connectivity test. Reply with exactly: ok",
            )
            return {
                "ok": True,
                "configured": True,
                "provider": provider,
                "model": payload.model_name,
                "message": (content or "ok").strip()[:160],
            }
        except ConfigError as exc:
            return {"ok": False, "configured": False, "provider": provider, "model": payload.model_name, "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "configured": True, "provider": provider, "model": payload.model_name, "message": str(exc)}

    @app.get("/api/videos")
    def list_videos() -> list[dict[str, Any]]:
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT v.video_id, v.video_title, v.video_url, v.video_date, v.status,
                       v.error_message, v.summary_latest_id, v.fetched_at, v.cleaned_at,
                       v.summarized_at,
                       CASE WHEN v.transcript_clean IS NOT NULL AND v.transcript_clean != '' THEN 1 ELSE 0 END AS has_transcript,
                       c.channel_name
                FROM Videos v
                JOIN Channels c ON c.channel_id = v.channel_id
                ORDER BY COALESCE(v.summarized_at, v.cleaned_at, v.fetched_at, v.updated_at, v.created_at) DESC,
                         COALESCE(v.video_date, '') DESC,
                         v.video_id DESC
                LIMIT 200
                """
            ).fetchall()
        videos = [dict(row) for row in rows]
        for video in videos:
            video["has_transcript"] = bool(video["has_transcript"])
        return videos

    @app.post("/api/videos/process-url")
    def process_video_url(payload: VideoProcessUrl) -> dict[str, Any]:
        try:
            return _process_video_url(db, settings, payload.video_url, output_language=payload.output_language)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/telegram/webhook/{webhook_secret}")
    def telegram_webhook(webhook_secret: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        if not as_bool(settings.telegram_bot_inbox_enabled):
            raise HTTPException(status_code=404, detail="Telegram bot inbox disabled")
        if not settings.telegram_bot_webhook_secret or not hmac.compare_digest(webhook_secret, settings.telegram_bot_webhook_secret):
            raise HTTPException(status_code=404, detail="Telegram webhook not found")
        if settings.telegram_bot_header_secret:
            header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not hmac.compare_digest(header_secret, settings.telegram_bot_header_secret):
                raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

        message = payload.get("message") or payload.get("edited_message") or {}
        chat_id = str((message.get("chat") or {}).get("id") or "")
        user_id = str((message.get("from") or {}).get("id") or "")
        text = message.get("text") or message.get("caption") or ""
        if not _telegram_sender_allowed(settings, chat_id, user_id):
            return {"status": "unauthorized"}

        video_url = _extract_first_youtube_url(text)
        if not video_url:
            _telegram_reply(settings, chat_id, "请发送一个 YouTube 视频链接，我会自动抓取字幕并生成总结。")
            return {"status": "ignored", "reason": "no_youtube_url"}

        _telegram_reply(settings, chat_id, "已收到视频链接，正在处理...")
        try:
            result = _process_video_url(db, settings, video_url, reuse_existing=as_bool(settings.telegram_bot_reuse_existing_summary))
            summary = db.get_summary(int(result["summary_id"]))
            video = db.get_video(result["video_id"])
            _telegram_reply(settings, chat_id, _format_telegram_video_summary(video, summary, settings, bool(result["reused"])))
            return {
                "status": "reused" if result["reused"] else "processed",
                "video_id": result["video_id"],
                "summary_id": result["summary_id"],
            }
        except Exception:
            _telegram_reply(
                settings,
                chat_id,
                "这个视频暂时没有处理成功。可能原因包括字幕不可用、YouTube 请求受限，或当前模型服务不可用。你可以稍后重试，或在 Web UI 的视频页面查看维护状态。",
            )
            return {"status": "failed"}

    @app.get("/api/videos/{video_id}")
    def get_video(video_id: str) -> dict[str, Any]:
        try:
            video = db.get_video_transcript(video_id)
            raw = db.get_video(video_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Video not found") from exc
        summary = db.get_summary(raw["summary_latest_id"]) if raw.get("summary_latest_id") else None
        with db.connect() as conn:
            source_rows = conn.execute(
                """
                SELECT s.source_id, s.source_type, s.source_name, s.display_name, sv.published_at, sv.discovered_at
                FROM SourceVideos sv
                JOIN Sources s ON s.source_id = sv.source_id
                WHERE sv.video_id = ?
                ORDER BY s.source_name
                """,
                (video_id,),
            ).fetchall()
        return {
            **video,
            "status": raw["status"],
            "duration": raw.get("duration"),
            "has_transcript": bool(raw.get("transcript_clean")),
            "error_message": raw.get("error_message"),
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at"),
            "cleaned_at": raw.get("cleaned_at"),
            "summarized_at": raw.get("summarized_at"),
            "summary": summary,
            "sources": [dict(row) for row in source_rows],
        }

    @app.post("/api/videos/{video_id}/process")
    def process_video(video_id: str) -> dict[str, Any]:
        processor = _make_video_processor(db, settings)
        result = processor.process(video_id)
        return {
            "video_id": result.video_id,
            "summary_id": result.summary_id,
            "source_vtt": str(result.source_vtt),
            "transcript_md": str(result.transcript_md),
            "summary_md": str(result.summary_md),
        }

    @app.post("/api/videos/{video_id}/summarize")
    def summarize_video(video_id: str) -> dict[str, Any]:
        from ypbrief.summarizer import Summarizer

        summary_id = Summarizer(db, _provider_from_settings(db, settings), settings=settings).summarize_video(video_id)
        return {"summary_id": summary_id}

    @app.post("/api/videos/{video_id}/export-transcript")
    def export_video_transcript(video_id: str) -> dict[str, Any]:
        from ypbrief.exporter import Exporter

        result = Exporter(db, settings.export_dir).export_transcript(video_id)
        return {"source": str(result.source), "transcript": str(result.transcript)}

    @app.post("/api/videos/{video_id}/export-summary")
    def export_video_summary(video_id: str) -> dict[str, Any]:
        from ypbrief.exporter import Exporter

        path = Exporter(db, settings.export_dir).export_summary(video_id)
        return {"summary": str(path)}

    @app.get("/api/digests")
    def list_digests() -> list[dict[str, Any]]:
        with db.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                       r.run_id AS latest_run_id,
                       r.run_type AS latest_run_type,
                       r.status AS latest_run_status,
                       r.window_start AS latest_run_window_start,
                       r.window_end AS latest_run_window_end,
                       r.included_count AS latest_run_included_count,
                       r.failed_count AS latest_run_failed_count,
                       r.skipped_count AS latest_run_skipped_count,
                       r.created_at AS latest_run_created_at,
                       r.completed_at AS latest_run_completed_at,
                       r.scheduled_job_id AS scheduled_job_id,
                       j.job_name AS scheduled_job_name
                FROM Summaries s
                LEFT JOIN DailyRuns r ON r.run_id = (
                    SELECT run_id
                    FROM DailyRuns
                    WHERE summary_id = s.summary_id
                    ORDER BY run_id DESC
                    LIMIT 1
                )
                LEFT JOIN ScheduledJobs j ON j.job_id = r.scheduled_job_id
                WHERE s.summary_type = 'digest'
                ORDER BY s.created_at DESC, s.summary_id DESC
                LIMIT 100
                """
            ).fetchall()
        return [_digest_preview(dict(row)) for row in rows]

    @app.get("/api/digests/latest")
    def latest_digest() -> dict[str, Any]:
        digests = list_digests()
        if not digests:
            raise HTTPException(status_code=404, detail="No digest found")
        return digests[0]

    @app.get("/api/digests/{summary_id}")
    def get_digest(summary_id: int) -> dict[str, Any]:
        try:
            summary = db.get_summary(summary_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Digest not found") from exc
        if summary["summary_type"] != "digest":
            raise HTTPException(status_code=404, detail="Digest not found")
        return _digest_detail(db, summary)

    @app.post("/api/digests/{summary_id}/export")
    def export_digest(summary_id: int) -> dict[str, Any]:
        try:
            summary = db.get_summary(summary_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Digest not found") from exc
        if summary["summary_type"] != "digest":
            raise HTTPException(status_code=404, detail="Digest not found")
        run_date = summary.get("range_start") or datetime_now_date()
        output, _, _ = daily_artifact_paths(settings.export_dir, run_date)
        content = f"{summary['content_markdown'].rstrip()}\n"
        output.write_text(content, encoding="utf-8")
        return {"summary": str(output), "filename": output.name, "content_markdown": content}

    @app.post("/api/digests/{summary_id}/regenerate")
    def regenerate_digest(summary_id: int) -> dict[str, Any]:
        try:
            summary = db.get_summary(summary_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Digest not found") from exc
        if summary["summary_type"] != "digest":
            raise HTTPException(status_code=404, detail="Digest not found")
        with db.connect() as conn:
            run = conn.execute(
                """
                SELECT *
                FROM DailyRuns
                WHERE summary_id = ?
                ORDER BY run_id DESC
                LIMIT 1
                """,
                (summary_id,),
            ).fetchone()
        if run is None:
            raise HTTPException(status_code=400, detail="Digest has no previous run to regenerate")
        source_ids = json.loads(run["source_ids_json"] or "[]")
        if not source_ids:
            raise HTTPException(status_code=400, detail="Previous run has no source_ids")
        if not run["window_end"]:
            raise HTTPException(status_code=400, detail="Previous run has no date window")
        window_end = date.fromisoformat(run["window_end"])
        window_days = None
        if run["window_start"]:
            window_start = date.fromisoformat(run["window_start"])
            window_days = (window_end - window_start).days
            if window_days <= 0:
                window_days = 1
        runner = digest_runner or _make_digest_runner(db, settings)
        try:
            return runner.run(
                source_ids=[int(source_id) for source_id in source_ids],
                run_date=window_end.isoformat(),
                window_days=window_days,
                max_videos_per_source=10,
                reuse_existing_summaries=True,
                process_missing_videos=True,
                retry_failed_once=True,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/digest-runs")
    def create_digest_run(payload: DigestRunCreate) -> dict[str, Any]:
        runner = digest_runner or _make_digest_runner(db, settings)
        source_ids = _resolve_requested_source_ids(
            db,
            source_ids=payload.source_ids,
            group_ids=payload.group_ids,
            use_all_enabled_sources=payload.use_all_enabled_sources,
        )
        if not source_ids:
            raise HTTPException(status_code=400, detail="At least one source is required")
        run_date = payload.run_date or datetime_now_date()
        window_days = None if payload.all_time else payload.window_days
        if payload.date_from and payload.date_to and not payload.all_time:
            from datetime import date, timedelta

            start = date.fromisoformat(payload.date_from)
            end = date.fromisoformat(payload.date_to) + timedelta(days=1)
            if end <= start:
                raise HTTPException(status_code=400, detail="date_to must be after date_from")
            run_date = end.isoformat()
            window_days = (end - start).days
        if window_days is None and not payload.all_time and not (payload.date_from and payload.date_to):
            window_days = 1
        if not payload.all_time and not (payload.date_from and payload.date_to) and window_days not in {1, 3, 7}:
            raise HTTPException(status_code=400, detail="window_days must be 1, 3, or 7 for preset windows")
        if payload.digest_language not in {"zh", "en"}:
            raise HTTPException(status_code=400, detail="digest_language must be zh or en")
        if payload.max_videos_per_source is not None and payload.max_videos_per_source < 1:
            raise HTTPException(status_code=400, detail="max_videos_per_source must be at least 1 or null")
        try:
            result = runner.run(
                source_ids=source_ids,
                run_date=run_date,
                window_days=window_days,
                max_videos_per_source=payload.max_videos_per_source,
                reuse_existing_summaries=payload.reuse_existing_summaries,
                process_missing_videos=payload.process_missing_videos,
                retry_failed_once=payload.retry_failed_once,
                digest_language=payload.digest_language,
            )
            if payload.deliver_after_run:
                _attach_manual_delivery_result(db, settings, result, run_date, payload)
            return result
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/digest-runs/{run_id}")
    def get_digest_run(run_id: int) -> dict[str, Any]:
        runner = digest_runner or _make_digest_runner(db, settings)
        try:
            return runner.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Digest run not found") from exc

    @app.post("/api/digest-runs/{run_id}/videos/{video_id}/retry")
    def retry_digest_run_video(run_id: int, video_id: str, source_id: int | None = None) -> dict[str, Any]:
        try:
            return _retry_digest_run_video(db, settings, run_id, video_id, source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/prompts")
    def list_prompts(group_id: int | None = None, scope: str = "all") -> list[dict[str, Any]]:
        prompt_service = DatabasePromptService(db, settings.prompt_file)
        if scope == "global":
            return prompt_service.list(group_id=None)
        if scope == "group" and group_id is not None:
            return prompt_service.list(group_id=group_id)
        return prompt_service.list(group_id=-1)

    @app.post("/api/prompts")
    def create_prompt(payload: PromptCreate) -> dict[str, Any]:
        try:
            return DatabasePromptService(db, settings.prompt_file).save(
                prompt_type=payload.prompt_type,
                prompt_name=payload.prompt_name,
                language=payload.language,
                group_id=payload.group_id,
                system_prompt=payload.system_prompt or "",
                user_template=payload.user_template,
                activate=payload.activate,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Prompt not found") from exc

    @app.post("/api/prompts/{prompt_id}/activate")
    def activate_prompt(prompt_id: str) -> dict[str, Any]:
        try:
            return DatabasePromptService(db, settings.prompt_file).activate(int(prompt_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Prompt not found") from exc

    @app.post("/api/prompts/{prompt_id}/preview")
    def preview_prompt(prompt_id: str, payload: PromptPreview, group_id: int | None = None) -> dict[str, str]:
        try:
            return DatabasePromptService(db, settings.prompt_file).preview(prompt_id, payload.values, group_id=group_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Prompt not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompts/reset-defaults")
    def reset_default_prompts() -> dict[str, Any]:
        prompts = DatabasePromptService(db, settings.prompt_file).reset_defaults()
        DatabasePromptService(db, settings.prompt_file).save_to_file(settings.prompt_file)
        return {"created": prompts, "path": str(Path(settings.prompt_file).resolve())}

    @app.post("/api/prompts/import")
    def import_prompts() -> dict[str, Any]:
        path = Path(settings.prompt_file)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{path.name} not found")
        count = DatabasePromptService(db, settings.prompt_file).import_from_file(path)
        return {"imported": count}

    @app.post("/api/prompts/save")
    def save_prompts() -> dict[str, Any]:
        path = DatabasePromptService(db, settings.prompt_file).save_to_file(settings.prompt_file)
        return {"path": str(path.resolve())}

    @app.get("/api/prompts/export")
    def export_prompts() -> dict[str, Any]:
        prompt_service = DatabasePromptService(db, settings.prompt_file)
        path = prompt_service.save_to_file(settings.prompt_file)
        return {
            "filename": Path(settings.prompt_file).name,
            "content": Path(path).read_text(encoding="utf-8"),
            "path": str(path.resolve()),
        }

    _mount_static_web(app, settings)
    _start_background_scheduler(app, db, settings, digest_runner)

    return app


def _digest_preview(summary: dict[str, Any]) -> dict[str, Any]:
    content = summary.get("content_markdown") or ""
    return {
        **summary,
        "preview": _preview_markdown(content),
    }


def _preview_markdown(content: str, limit: int = 1800) -> str:
    text = content.strip()
    synthesis = _preview_through_overall_synthesis(text)
    if synthesis:
        return synthesis
    if len(text) <= limit:
        return text
    candidate = text[:limit]
    paragraph_end = max(candidate.rfind("\n\n"), candidate.rfind("\n---\n"))
    sentence_end = max(candidate.rfind("。"), candidate.rfind("."), candidate.rfind("！"), candidate.rfind("？"))
    cut_at = paragraph_end if paragraph_end >= 300 else sentence_end
    if cut_at < 300:
        cut_at = limit
    return candidate[:cut_at].rstrip() + "\n\n…"


def _preview_through_overall_synthesis(text: str) -> str:
    if not text:
        return ""
    headings = list(re.finditer(r"(?m)^#{1,3}\s+(.+?)\s*$", text))
    if not headings:
        return ""
    synthesis_index = next(
        (
            index
            for index, match in enumerate(headings)
            if "overall synthesis" in match.group(1).strip().lower()
            or "整体大总结" in match.group(1).strip()
            or "综合总结" in match.group(1).strip()
        ),
        None,
    )
    if synthesis_index is None:
        return ""
    next_index = synthesis_index + 1
    if next_index < len(headings):
        preview = text[: headings[next_index].start()].rstrip()
    else:
        preview = text.rstrip()
    return preview


def _get_model_profile(db: Database, model_id: int) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM ModelProfiles WHERE model_id = ?", (model_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Model profile not found")
    result = dict(row)
    result["provider"] = _normalize_provider(result["provider"])
    result.pop("display_name", None)
    return result


def _sync_provider_to_env(env_file: Path, provider: str, config: dict[str, Any]) -> None:
    keys = PROVIDER_ENV_KEYS.get(_normalize_provider(provider))
    if not keys:
        return
    updates: dict[str, str] = {}
    if config.get("api_key"):
        updates[keys["api_key"]] = str(config["api_key"])
    if config.get("base_url"):
        updates[keys["base_url"]] = str(config["base_url"])
    if "default_model" in config:
        updates[keys["default_model"]] = str(config["default_model"])
    _update_env_file(env_file, updates)


def _sync_provider_to_settings(settings: Settings, provider: str, config: dict[str, Any]) -> None:
    _sync_provider_config_to_settings(settings, provider, config)


def _sync_active_model_to_env(env_file: Path, settings: Settings, provider: str, model_name: str) -> None:
    settings.llm_provider = _normalize_provider(provider)
    settings.llm_model = model_name
    _update_env_file(env_file, {"LLM_PROVIDER": _normalize_provider(provider), "LLM_MODEL": model_name})


def _proxy_settings_public(settings: Settings) -> dict[str, Any]:
    effective_proxy = settings.youtube_proxy_url
    effective_yt_dlp_proxy = settings.yt_dlp_proxy_url
    return {
        "enabled": bool(effective_proxy),
        "configured": bool(effective_proxy),
        "youtube_proxy_http": settings.youtube_proxy_http,
        "youtube_proxy_https": settings.youtube_proxy_https,
        "iproyal_host": settings.iproyal_proxy_host,
        "iproyal_port": settings.iproyal_proxy_port,
        "iproyal_username": settings.iproyal_proxy_username,
        "iproyal_password_configured": bool(settings.iproyal_proxy_password),
        "yt_dlp_proxy": settings.yt_dlp_proxy,
        "effective_proxy": _mask_proxy_url(effective_proxy),
        "effective_yt_dlp_proxy": _mask_proxy_url(effective_yt_dlp_proxy),
    }


def _youtube_settings_public(settings: Settings) -> dict[str, Any]:
    return {
        "configured": bool(settings.youtube_data_api_key),
        "api_key_configured": bool(settings.youtube_data_api_key),
        "api_key_hint": mask_secret(settings.youtube_data_api_key),
    }


def _mask_proxy_url(proxy_url: str) -> str:
    if "@" not in proxy_url or "://" not in proxy_url:
        return proxy_url
    scheme, rest = proxy_url.split("://", 1)
    return f"{scheme}://***:***@{rest.split('@', 1)[1]}"


def _update_env_file(env_file: Path, updates: dict[str, str]) -> None:
    if not updates:
        return
    path = env_file.resolve() if env_file.exists() else env_file
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    if remaining:
        if output and output[-1].strip():
            output.append("")
        for key, value in remaining.items():
            output.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _sync_access_password_to_database(db: Database, password: str) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO ApplicationSettings(setting_key, setting_value, updated_at)
            VALUES ('YPBRIEF_ACCESS_PASSWORD', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (password,),
        )


def _delivery_env_updates(settings_data: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    updates = {
        "TELEGRAM_ENABLED": "true" if settings_data["telegram_enabled"] else "false",
        "TELEGRAM_CHAT_ID": settings_data["telegram_chat_id"],
        "TELEGRAM_PARSE_MODE": settings_data["telegram_parse_mode"],
        "TELEGRAM_SEND_AS_FILE_IF_TOO_LONG": "true" if settings_data["telegram_send_as_file_if_too_long"] else "false",
        "FEISHU_ENABLED": "true" if settings_data["feishu_enabled"] else "false",
        "EMAIL_ENABLED": "true" if settings_data["email_enabled"] else "false",
        "SMTP_HOST": settings_data["smtp_host"],
        "SMTP_PORT": str(settings_data["smtp_port"]),
        "SMTP_USERNAME": settings_data["smtp_username"],
        "SMTP_USE_TLS": "true" if settings_data["smtp_use_tls"] else "false",
        "SMTP_USE_SSL": "true" if settings_data["smtp_use_ssl"] else "false",
        "EMAIL_FROM": settings_data["email_from"],
        "EMAIL_TO": ",".join(settings_data["email_to"]),
        "EMAIL_SUBJECT_TEMPLATE": settings_data["email_subject_template"],
        "EMAIL_ATTACH_MARKDOWN": "true" if settings_data["email_attach_markdown"] else "false",
    }
    if "telegram_bot_token" in payload:
        updates["TELEGRAM_BOT_TOKEN"] = payload.get("telegram_bot_token") or ""
    if "feishu_webhook_url" in payload:
        updates["FEISHU_WEBHOOK_URL"] = payload.get("feishu_webhook_url") or ""
    if "feishu_secret" in payload:
        updates["FEISHU_SECRET"] = payload.get("feishu_secret") or ""
    if "smtp_password" in payload:
        updates["SMTP_PASSWORD"] = payload.get("smtp_password") or ""
    return updates


def _attach_manual_delivery_result(
    db: Database,
    settings: Settings,
    result: dict[str, Any],
    run_date: str,
    payload: DigestRunCreate,
) -> None:
    delivery = DeliveryService(db, settings)
    run_id = result.get("run_id")
    summary_id = result.get("summary_id")
    channel_flags = {
        "telegram_enabled": payload.telegram_enabled,
        "feishu_enabled": payload.feishu_enabled,
        "email_enabled": payload.email_enabled,
    }
    if summary_id:
        result["deliveries"] = delivery.send_summary(
            int(summary_id),
            int(run_id) if run_id else None,
            **channel_flags,
        )
        return
    is_no_updates = (
        result.get("status") == "no_updates"
        or (
            int(result.get("included_count") or 0) == 0
            and int(result.get("failed_count") or 0) == 0
            and int(result.get("skipped_count") or 0) == 0
        )
    )
    if is_no_updates:
        deliveries = delivery.send_no_updates(
            run_date,
            payload.digest_language,
            int(run_id) if run_id else None,
            **channel_flags,
        )
        result["empty_digest_delivered"] = any(item["status"] == "success" for item in deliveries)
        result["deliveries"] = deliveries
        return
    is_failed = (
        result.get("status") == "failed"
        or int(result.get("failed_count") or 0) > 0
    )
    if is_failed:
        deliveries = delivery.send_failure_notice(
            int(run_id),
            run_date,
            payload.digest_language,
            **channel_flags,
        ) if run_id else []
        result["failure_notice_delivered"] = any(item["status"] == "success" for item in deliveries)
        result["deliveries"] = deliveries
        return
    result["deliveries"] = []


def _start_background_scheduler(app: FastAPI, db: Database, settings: Settings, digest_runner: Any | None) -> None:
    _configure_background_scheduler(app, db, settings, digest_runner)

    def _shutdown_scheduler() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            app.state.scheduler = None

    if hasattr(app, "add_event_handler"):
        app.add_event_handler("shutdown", _shutdown_scheduler)
    else:
        app.router.add_event_handler("shutdown", _shutdown_scheduler)


def _configure_background_scheduler(app: FastAPI, db: Database, settings: Settings, digest_runner: Any | None) -> None:
    current = getattr(app.state, "scheduler", None)
    if current is not None:
        current.shutdown(wait=False)
        app.state.scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except Exception:
        app.state.scheduler = None
        return

    service = _make_scheduler_service(db, settings, digest_runner)
    jobs = [job for job in service.list_jobs() if job["enabled"]]
    if not jobs:
        app.state.scheduler = None
        return
    scheduler = BackgroundScheduler(timezone="UTC")
    for job in jobs:
        hour, minute = [int(part) for part in job["run_time"].split(":", 1)]
        scheduler.add_job(
            lambda job_id=job["job_id"]: _make_scheduler_service(db, settings, digest_runner).run_job_now(job_id, automatic=True),
            CronTrigger(hour=hour, minute=minute, timezone=job["timezone"]),
            id=f"scheduled_job_{job['job_id']}",
            replace_existing=True,
            max_instances=1,
        )
    scheduler.start()
    app.state.scheduler = scheduler


def _public_provider(config: dict[str, Any]) -> dict[str, Any]:
    provider = _normalize_provider(str(config.get("provider") or ""))
    public = {
        **{key: value for key, value in config.items() if key != "api_key"},
        "provider": provider,
        "api_key_configured": bool(config.get("api_key")),
    }
    if provider == "xai":
        public["display_name"] = "xAI"
    return public


def _get_llm_provider_public(db: Database, settings: Settings, provider: str) -> dict[str, Any]:
    config = _get_llm_provider_effective(db, settings, provider)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    return _public_provider(config)


def _upsert_llm_provider_config(
    db: Database,
    *,
    provider: str,
    provider_type: str,
    display_name: str | None,
    base_url: str | None,
    api_key: str | None,
    default_model: str | None,
    enabled: bool,
    notes: str | None,
) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO LLMProviderConfigs(
                provider, provider_type, display_name, base_url, api_key,
                default_model, enabled, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                provider_type=excluded.provider_type,
                display_name=excluded.display_name,
                base_url=excluded.base_url,
                api_key=excluded.api_key,
                default_model=excluded.default_model,
                enabled=excluded.enabled,
                notes=excluded.notes,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                _normalize_provider(provider),
                provider_type,
                display_name,
                base_url,
                api_key,
                default_model,
                1 if enabled else 0,
                notes,
            ),
        )


def _list_llm_providers(db: Database, settings: Settings) -> list[dict[str, Any]]:
    providers: dict[str, dict[str, Any]] = {}
    for provider in BUILTIN_LLM_PROVIDERS:
        config = _get_llm_provider_effective(db, settings, provider)
        if config:
            providers[provider] = config
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM LLMProviderConfigs ORDER BY provider").fetchall()
    for row in rows:
        data = dict(row)
        effective = _get_llm_provider_effective(db, settings, data["provider"])
        if effective:
            providers[effective["provider"]] = effective
    return [_public_provider(providers[key]) for key in sorted(providers)]


def _provider_key_status(db: Database, settings: Settings) -> dict[str, bool]:
    return {
        provider["provider"]: bool(provider["api_key_configured"])
        for provider in _list_llm_providers(db, settings)
    }


def _llm_configured(db: Database, settings: Settings, provider_name: str | None = None) -> bool:
    provider = (provider_name or settings.llm_provider).lower()
    config = _get_llm_provider_effective(db, settings, provider)
    if config is not None:
        return bool(config.get("api_key")) and (
            config["provider_type"] in {"gemini", "claude"} or bool(config.get("base_url"))
        )
    if provider == "gemini":
        return bool(settings.gemini_api_key)
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "claude":
        return bool(settings.anthropic_api_key)
    if provider == "siliconflow":
        return bool(settings.siliconflow_api_key)
    if provider == "openrouter":
        return bool(settings.openrouter_api_key)
    if provider == "xai":
        return bool(settings.xai_api_key)
    if provider == "deepseek":
        return bool(settings.deepseek_api_key)
    if provider == "custom_openai":
        return bool(settings.custom_openai_api_key and settings.custom_openai_base_url)
    return False


def _digest_detail(db: Database, summary: dict[str, Any]) -> dict[str, Any]:
    with db.connect() as conn:
        runs = conn.execute(
            """
            SELECT r.*, j.job_name AS scheduled_job_name
            FROM DailyRuns r
            LEFT JOIN ScheduledJobs j ON j.job_id = r.scheduled_job_id
            WHERE r.summary_id = ?
            ORDER BY r.run_id DESC
            """,
            (summary["summary_id"],),
        ).fetchall()
        run_ids = [row["run_id"] for row in runs]
        videos: list[dict[str, Any]] = []
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            rows = conn.execute(
                f"""
                SELECT drv.run_id, drv.video_id, drv.source_id, drv.status, drv.action,
                       drv.error_message, drv.summary_id AS video_summary_id,
                       v.video_title, v.video_url, v.video_date,
                       c.channel_name,
                       COALESCE(s.source_name, drv.source_name_snapshot) AS source_name,
                       COALESCE(s.display_name, drv.display_name_snapshot) AS display_name,
                       COALESCE(s.source_type, drv.source_type_snapshot) AS source_type
                FROM DailyRunVideos drv
                LEFT JOIN Videos v ON v.video_id = drv.video_id
                LEFT JOIN Channels c ON c.channel_id = v.channel_id
                LEFT JOIN Sources s ON s.source_id = drv.source_id
                WHERE drv.run_id IN ({placeholders})
                ORDER BY drv.status, COALESCE(v.video_date, ''), drv.video_id
                """,
                tuple(run_ids),
            ).fetchall()
            videos = [dict(row) for row in rows]
        if not videos:
            videos = _infer_digest_videos_from_markdown(conn, summary)
    included = [video for video in videos if video["status"] == "included"]
    failed = [video for video in videos if video["status"] in {"failed", "skipped"}]
    latest_run = dict(runs[0]) if runs else {}
    return {
        **_digest_preview(summary),
        "latest_run_id": latest_run.get("run_id"),
        "latest_run_type": latest_run.get("run_type"),
        "latest_run_status": latest_run.get("status"),
        "latest_run_window_start": latest_run.get("window_start"),
        "latest_run_window_end": latest_run.get("window_end"),
        "latest_run_included_count": latest_run.get("included_count"),
        "latest_run_failed_count": latest_run.get("failed_count"),
        "latest_run_skipped_count": latest_run.get("skipped_count"),
        "latest_run_created_at": latest_run.get("created_at"),
        "latest_run_completed_at": latest_run.get("completed_at"),
        "scheduled_job_id": latest_run.get("scheduled_job_id"),
        "scheduled_job_name": latest_run.get("scheduled_job_name"),
        "runs": [dict(row) for row in runs],
        "videos": videos,
        "included_videos": included,
        "failed_videos": failed,
        "included_count": len(included),
        "failed_count": len([video for video in videos if video["status"] == "failed"]),
        "skipped_count": len([video for video in videos if video["status"] == "skipped"]),
    }


def _infer_digest_videos_from_markdown(conn: Any, summary: dict[str, Any]) -> list[dict[str, Any]]:
    refs = _extract_digest_video_refs(summary.get("content_markdown") or "")
    if not refs:
        return []
    rows = conn.execute(
        """
        SELECT NULL AS run_id,
               v.video_id,
               sv.source_id,
               'included' AS status,
               'inferred' AS action,
               NULL AS error_message,
               v.summary_latest_id AS video_summary_id,
               v.video_title,
               v.video_url,
               v.video_date,
               c.channel_name,
               s.source_name,
               s.display_name,
               s.source_type
        FROM Videos v
        JOIN Channels c ON c.channel_id = v.channel_id
        LEFT JOIN SourceVideos sv ON sv.video_id = v.video_id
        LEFT JOIN Sources s ON s.source_id = sv.source_id
        WHERE v.summary_latest_id IS NOT NULL
        ORDER BY COALESCE(v.video_date, '') DESC,
                 COALESCE(v.summarized_at, v.updated_at, v.created_at) DESC,
                 v.video_id
        LIMIT 1000
        """
    ).fetchall()
    candidates = [dict(row) for row in rows]
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref in refs:
        best: dict[str, Any] | None = None
        best_score = 0
        for candidate in candidates:
            video_id = str(candidate.get("video_id") or "")
            if not video_id or video_id in seen:
                continue
            score = _digest_video_match_score(ref, candidate)
            if score > best_score:
                best = candidate
                best_score = score
        if best and best_score >= 72:
            seen.add(str(best["video_id"]))
            matched.append(best)
    return matched


def _extract_digest_video_refs(markdown: str) -> list[dict[str, str | None]]:
    refs: list[dict[str, str | None]] = []
    in_video_section = False
    current: dict[str, str | None] | None = None
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^#\s+Video-by-Video\b", line, flags=re.IGNORECASE):
            in_video_section = True
            continue
        if in_video_section and re.match(r"^#\s+", line):
            break
        if not in_video_section:
            continue
        heading = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if heading:
            current = {"heading": heading.group(1).strip(), "publish_date": None}
            refs.append(current)
            continue
        if current:
            date_match = re.search(r"Publish Date\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", line, flags=re.IGNORECASE)
            if date_match:
                current["publish_date"] = date_match.group(1)
    return refs


def _digest_video_match_score(ref: dict[str, str | None], candidate: dict[str, Any]) -> int:
    heading = _normalize_match_text(ref.get("heading") or "")
    title = _normalize_match_text(candidate.get("video_title") or "")
    channel = _normalize_match_text(candidate.get("channel_name") or "")
    if not heading or not title:
        return 0

    score = 0
    if title == heading:
        score = 100
    elif title in heading:
        score = 95
    elif heading in title:
        score = 90
    else:
        parts = [_normalize_match_text(part) for part in re.split(r"\s+\|\s+|\s+-\s+", ref.get("heading") or "")]
        for part in parts:
            if part and (title in part or part in title):
                score = max(score, 88)
        heading_terms = set(heading.split())
        title_terms = set(title.split())
        if heading_terms and title_terms:
            overlap = len(heading_terms & title_terms) / max(len(title_terms), 1)
            score = max(score, int(overlap * 82))

    if channel and channel in heading:
        score += 4
    publish_date = ref.get("publish_date")
    video_date = candidate.get("video_date")
    if publish_date and video_date:
        score += 8 if publish_date == video_date else -18
    return score


def _normalize_match_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _retry_digest_run_video(
    db: Database,
    settings: Settings,
    run_id: int,
    video_id: str,
    source_id: int | None,
) -> dict[str, Any]:
    with db.connect() as conn:
        run = conn.execute("SELECT * FROM DailyRuns WHERE run_id = ?", (run_id,)).fetchone()
        if run is None:
            raise KeyError("Digest run not found")
        if source_id is None:
            rows = conn.execute(
                "SELECT * FROM DailyRunVideos WHERE run_id = ? AND video_id = ?",
                (run_id, video_id),
            ).fetchall()
            if not rows:
                raise KeyError("Run video not found")
            if len(rows) > 1:
                raise ValueError("source_id is required when a run has multiple rows for this video")
            row = rows[0]
            source_id = row["source_id"]
        else:
            row = conn.execute(
                """
                SELECT *
                FROM DailyRunVideos
                WHERE run_id = ? AND video_id = ? AND source_id = ?
                """,
                (run_id, video_id, source_id),
            ).fetchone()
            if row is None:
                raise KeyError("Run video not found")

    try:
        video = db.get_video(video_id)
        summary_id = int(video["summary_latest_id"]) if video.get("summary_latest_id") else None
        if summary_id is None:
            result = _make_video_processor(db, settings).process(video_id)
            summary_id = result.summary_id
        if summary_id is None:
            raise ValueError("summary was not created")
        status = "included"
        action = "retry"
        error_message = None
    except Exception as exc:
        summary_id = None
        status = "failed"
        action = "retry"
        error_message = str(exc)

    with db.connect() as conn:
        conn.execute(
            """
            UPDATE DailyRunVideos
            SET status = ?, action = ?, error_message = ?, summary_id = ?
            WHERE run_id = ? AND video_id = ? AND source_id IS ?
            """,
            (status, action, error_message, summary_id, run_id, video_id, source_id),
        )
        counts = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'included' THEN 1 ELSE 0 END) AS included_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped_count
            FROM DailyRunVideos
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        conn.execute(
            """
            UPDATE DailyRuns
            SET included_count = ?, failed_count = ?, skipped_count = ?,
                status = CASE WHEN ? > 0 THEN 'completed' ELSE status END,
                completed_at = CURRENT_TIMESTAMP,
                error_message = CASE WHEN ? > 0 THEN NULL ELSE error_message END
            WHERE run_id = ?
            """,
            (
                counts["included_count"] or 0,
                counts["failed_count"] or 0,
                counts["skipped_count"] or 0,
                counts["included_count"] or 0,
                counts["included_count"] or 0,
                run_id,
            ),
        )
        updated = conn.execute(
            """
            SELECT drv.run_id, drv.video_id, drv.source_id, drv.status, drv.action,
                   drv.error_message, drv.summary_id,
                   v.video_title, v.video_url, v.video_date,
                   c.channel_name,
                   COALESCE(s.source_name, drv.source_name_snapshot) AS source_name,
                   COALESCE(s.display_name, drv.display_name_snapshot) AS display_name,
                   COALESCE(s.source_type, drv.source_type_snapshot) AS source_type
            FROM DailyRunVideos drv
            LEFT JOIN Videos v ON v.video_id = drv.video_id
            LEFT JOIN Channels c ON c.channel_id = v.channel_id
            LEFT JOIN Sources s ON s.source_id = drv.source_id
            WHERE drv.run_id = ? AND drv.video_id = ? AND drv.source_id IS ?
            """,
            (run_id, video_id, source_id),
        ).fetchone()
        run_after = conn.execute("SELECT * FROM DailyRuns WHERE run_id = ?", (run_id,)).fetchone()

    return {
        **dict(updated),
        "run": dict(run_after),
    }


def _make_scheduler_service(db: Database, settings: Settings, digest_runner: Any | None) -> SchedulerService:
    class LazyRunner:
        def run(self, **kwargs):
            return _make_digest_runner(db, settings).run(**kwargs)

    runner = digest_runner or LazyRunner()
    return SchedulerService(db=db, settings=settings, runner=runner, delivery=DeliveryService(db, settings))


def _run_scheduled_job_background(
    db: Database,
    settings: Settings,
    digest_runner: Any | None,
    job_id: int,
    now: str | None,
) -> None:
    try:
        _make_scheduler_service(db, settings, digest_runner).run_job_now(job_id, now)
    except Exception:
        logger.exception("Scheduled job %s background run failed", job_id)


def _resolve_requested_source_ids(
    db: Database,
    *,
    source_ids: list[int] | None,
    group_ids: list[int] | None,
    use_all_enabled_sources: bool,
) -> list[int]:
    if use_all_enabled_sources:
        return [int(source["source_id"]) for source in db.list_sources(enabled_only=True)]

    resolved: list[int] = []
    seen: set[int] = set()
    for source_id in source_ids or []:
        normalized = int(source_id)
        if normalized not in seen:
            resolved.append(normalized)
            seen.add(normalized)

    if not group_ids:
        return resolved

    selected_groups = {int(group_id) for group_id in group_ids}
    for source in db.list_sources(enabled_only=True):
        group_id = source.get("group_id")
        if group_id is None or int(group_id) not in selected_groups:
            continue
        source_id = int(source["source_id"])
        if source_id not in seen:
            resolved.append(source_id)
            seen.add(source_id)
    return resolved


def _make_digest_runner(db: Database, settings: Settings) -> DigestRunService:
    if not settings.youtube_data_api_key:
        raise HTTPException(status_code=400, detail="YOUTUBE_DATA_API_KEY is required")
    provider = _provider_from_settings(db, settings)
    youtube = YouTubeDataClient(settings.youtube_data_api_key)
    processor = _make_video_processor(db, settings)
    return DigestRunService(
        db=db,
        youtube=youtube,
        processor=processor,
        digest_service=DailyDigestService(db, provider, settings.export_dir, settings=settings),
    )


def _make_video_processor(db: Database, settings: Settings) -> VideoProcessor:
    if not settings.youtube_data_api_key:
        raise HTTPException(status_code=400, detail="YOUTUBE_DATA_API_KEY is required")
    return VideoProcessor.from_api_key(
        db=db,
        youtube_api_key=settings.youtube_data_api_key,
        transcripts=TranscriptFetcher.from_settings(settings),
        provider=_provider_from_settings(db, settings),
        export_dir=settings.export_dir,
        settings=settings,
    )


def _process_video_url(
    db: Database,
    settings: Settings,
    video_url: str,
    *,
    reuse_existing: bool = True,
    output_language: str | None = None,
) -> dict[str, Any]:
    video_id = parse_video_id(video_url)
    language = (output_language or "auto").strip().lower()
    if language not in {"auto", "zh", "en"}:
        raise ValueError("output_language must be auto, zh, or en")
    try:
        existing = db.get_video(video_id)
    except KeyError:
        existing = None
    if existing and existing.get("summary_latest_id") and reuse_existing and language == "auto":
        return {
            "video_id": video_id,
            "summary_id": existing["summary_latest_id"],
            "reused": True,
            "status": existing["status"],
            "source_vtt": None,
            "transcript_md": None,
            "summary_md": None,
        }

    processor = _make_video_processor(db, settings)
    result = processor.process(video_url) if language == "auto" else processor.process(video_url, output_language=language)
    processed = db.get_video(result.video_id)
    return {
        "video_id": result.video_id,
        "summary_id": result.summary_id,
        "reused": False,
        "status": processed["status"],
        "source_vtt": str(result.source_vtt),
        "transcript_md": str(result.transcript_md),
        "summary_md": str(result.summary_md),
    }


YOUTUBE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?[^ \n\t<>]*v=|shorts/|live/)|youtu\.be/)[^ \n\t<>]+",
    re.IGNORECASE,
)


def _extract_first_youtube_url(text: str) -> str | None:
    match = YOUTUBE_URL_RE.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(").,，。")


def _telegram_sender_allowed(settings: Settings, chat_id: str, user_id: str) -> bool:
    allowed_chat_ids = _csv_set(settings.telegram_bot_allowed_chat_ids)
    allowed_user_ids = _csv_set(settings.telegram_bot_allowed_user_ids)
    if not allowed_chat_ids and not allowed_user_ids:
        return False
    return bool((chat_id and chat_id in allowed_chat_ids) or (user_id and user_id in allowed_user_ids))


def _csv_set(value: str) -> set[str]:
    return {item.strip() for item in (value or "").replace("\n", ",").split(",") if item.strip()}


def _telegram_reply(settings: Settings, chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token or not chat_id:
        return
    _send_telegram_text(settings.telegram_bot_token, chat_id, text, settings.telegram_parse_mode or "Markdown")


def _send_telegram_text(token: str, chat_id: str, text: str, parse_mode: str | None = None) -> None:
    for message in _telegram_message_parts(text):
        _post_telegram_message(token, chat_id, message, parse_mode)


def _format_telegram_video_summary(video: dict[str, Any], summary: dict[str, Any], settings: Settings, reused: bool) -> str:
    lines = [
        f"*{video.get('video_title') or summary.get('title') or video.get('video_id')}*",
        f"{video.get('channel_name') or '-'} · {video.get('video_date') or '-'}",
        "",
        summary.get("content_markdown") or "",
    ]
    detail_url = _video_detail_url(settings, str(video.get("video_id") or ""))
    if detail_url:
        lines.extend(["", f"详情页: {detail_url}"])
    if reused:
        lines.extend(["", "已复用已有总结。"])
    return "\n".join(lines).strip()


def _video_detail_url(settings: Settings, video_id: str) -> str:
    base_url = (settings.telegram_bot_public_base_url or "").strip().rstrip("/")
    if not base_url or not video_id:
        return ""
    return f"{base_url}/videos/{video_id}"


def _provider_from_settings(db: Database, settings: Settings):
    return create_provider_from_database(db, settings)


def datetime_now_date() -> str:
    from datetime import datetime

    return datetime.now().date().isoformat()


def _mount_static_web(app: FastAPI, settings: Settings) -> None:
    configured = getattr(settings, "web_dist_dir", "")
    candidates = [
        Path(configured) if configured else None,
        Path.cwd() / "web" / "dist",
        Path(__file__).resolve().parents[2] / "web" / "dist",
        Path("/app/web/dist"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "index.html").exists():
            app.mount("/", StaticFiles(directory=candidate, html=True), name="web")
            return


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
}
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300
LOGIN_RATE_LIMIT_MAX_FAILURES = 5


def _apply_security_headers(response) -> None:
    for key, value in SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)


def _client_identifier(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _login_rate_limited(failures: dict[str, list[float]], client_id: str) -> bool:
    now = time.time()
    failures[client_id] = [
        timestamp
        for timestamp in failures.get(client_id, [])
        if now - timestamp < LOGIN_RATE_LIMIT_WINDOW_SECONDS
    ]
    return len(failures[client_id]) >= LOGIN_RATE_LIMIT_MAX_FAILURES


def _record_failed_login(failures: dict[str, list[float]], client_id: str) -> None:
    failures.setdefault(client_id, []).append(time.time())


def _clear_failed_logins(failures: dict[str, list[float]], client_id: str) -> None:
    failures.pop(client_id, None)


def _auth_required(settings: Settings) -> bool:
    return bool(getattr(settings, "access_password", "").strip())


def _issue_auth_token(secret: str, ttl_seconds: int = 60 * 60 * 24 * 7) -> tuple[str, int]:
    expires_at = int(time.time()) + ttl_seconds
    nonce = secrets.token_urlsafe(18)
    payload = f"{expires_at}:{nonce}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), "sha256").digest()
    token = f"{payload}:{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"
    return token, expires_at


def _valid_auth_header(header: str, secret: str) -> bool:
    if not header.lower().startswith("bearer "):
        return False
    token = header.split(" ", 1)[1].strip()
    parts = token.split(":")
    if len(parts) != 3:
        return False
    expires_at, nonce, signature = parts
    if not expires_at.isdigit() or int(expires_at) < int(time.time()):
        return False
    payload = f"{expires_at}:{nonce}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), "sha256").digest()
    expected_text = base64.urlsafe_b64encode(expected).decode("ascii").rstrip("=")
    return hmac.compare_digest(signature, expected_text)


app = create_app()
