from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .config import Settings
from .database import Database
from .delivery import DeliveryService, as_bool


class SchedulerService:
    def __init__(self, db: Database, settings: Settings, runner: Any, delivery: DeliveryService | None = None) -> None:
        self.db = db
        self.settings = settings
        self.runner = runner
        self.delivery = delivery or DeliveryService(db, settings)

    def list_jobs(self) -> list[dict[str, Any]]:
        self.db.ensure_default_scheduled_job(self._default_job_payload())
        return self.db.list_scheduled_jobs()

    def get_job(self, job_id: int) -> dict[str, Any]:
        return self.db.get_scheduled_job(job_id)

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.db.save_scheduled_job(**payload)

    def update_job(self, job_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.db.save_scheduled_job(job_id=job_id, **payload)

    def delete_job(self, job_id: int) -> None:
        self.db.delete_scheduled_job(job_id)

    def list_job_runs(self, job_id: int, limit: int = 20) -> list[dict[str, Any]]:
        self.db.get_scheduled_job(job_id)
        return self.db.list_scheduled_job_runs(job_id, limit=limit)

    def run_job_now(self, job_id: int, now: str | None = None, automatic: bool = False) -> dict[str, Any]:
        job = self.db.get_scheduled_job(job_id)
        run_date = self.window_end_date(now, job["timezone"])
        digest_date = self.previous_day(now, job["timezone"])
        if automatic:
            existing = self._existing_job_run(job_id, run_date, job["window_mode"])
            if existing is not None:
                return {**existing, "skipped_duplicate": True}
        run_type = "scheduled" if automatic else "scheduled_manual"
        return self._run_digest(
            source_ids=self._resolve_job_source_ids(job),
            run_date=run_date,
            window_days=self._window_days(job["window_mode"]),
            max_videos_per_source=job["max_videos_per_source"],
            process_missing_videos=job["process_missing_videos"],
            retry_failed_once=job["retry_failed_once"],
            digest_date=digest_date,
            digest_language=job["digest_language"],
            mark_run=lambda run_id: self._mark_job_run(run_id, job_id, run_type),
            send_empty_digest=job["send_empty_digest"],
            telegram_enabled=job["telegram_enabled"],
            email_enabled=job["email_enabled"],
        )

    @staticmethod
    def previous_day(now: str | None, timezone: str) -> str:
        current = SchedulerService.window_end_date(now, timezone)
        from datetime import date

        return (date.fromisoformat(current) - timedelta(days=1)).isoformat()

    @staticmethod
    def window_end_date(now: str | None, timezone: str) -> str:
        tz = ZoneInfo(timezone)
        if now:
            current = datetime.fromisoformat(now).astimezone(tz)
        else:
            current = datetime.now(tz)
        return current.date().isoformat()

    def _default_job_payload(self) -> dict[str, Any]:
        source_ids = [
            int(item.strip())
            for item in self.settings.scheduler_source_ids.split(",")
            if item.strip().isdigit()
        ]
        source_scope = self.settings.scheduler_source_scope or "all_enabled"
        digest_language = self.settings.scheduler_digest_language if self.settings.scheduler_digest_language in {"zh", "en"} else "zh"
        return {
            "job_name": "Default Daily Job",
            "enabled": as_bool(self.settings.scheduler_enabled),
            "timezone": self.settings.scheduler_timezone or "Asia/Shanghai",
            "run_time": self.settings.scheduler_run_time or "07:00",
            "digest_language": digest_language,
            "scope_type": "sources" if source_scope == "selected" and source_ids else "all_enabled",
            "source_ids": source_ids,
            "window_mode": "last_1",
            "max_videos_per_source": int(self.settings.scheduler_max_videos_per_source or 10),
            "process_missing_videos": True,
            "retry_failed_once": True,
            "send_empty_digest": as_bool(self.settings.scheduler_send_empty_digest),
            "telegram_enabled": True,
            "email_enabled": False,
        }

    def _is_no_updates(self, result: dict[str, Any]) -> bool:
        return (
            not result.get("summary_id")
            and int(result.get("included_count") or 0) == 0
            and int(result.get("failed_count") or 0) == 0
            and int(result.get("skipped_count") or 0) == 0
        )

    def _run_digest(
        self,
        *,
        source_ids: list[int],
        run_date: str,
        window_days: int | None,
        max_videos_per_source: int | None,
        process_missing_videos: bool,
        retry_failed_once: bool,
        digest_date: str,
        digest_language: str,
        mark_run: Callable[[int | None], None],
        send_empty_digest: bool,
        telegram_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> dict[str, Any]:
        if not source_ids:
            raise ValueError("At least one source is required")
        result = self.runner.run(
            source_ids=source_ids,
            run_date=run_date,
            window_days=window_days,
            max_videos_per_source=max_videos_per_source,
            reuse_existing_summaries=True,
            process_missing_videos=process_missing_videos,
            retry_failed_once=retry_failed_once,
            digest_language=digest_language,
        )
        return self._finalize_run_result(
            result,
            digest_date=digest_date,
            digest_language=digest_language,
            mark_run=mark_run,
            send_empty_digest=send_empty_digest,
            telegram_enabled=telegram_enabled,
            email_enabled=email_enabled,
        )

    def _finalize_run_result(
        self,
        result: dict[str, Any],
        *,
        digest_date: str,
        digest_language: str,
        mark_run: Callable[[int | None], None],
        send_empty_digest: bool,
        telegram_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> dict[str, Any]:
        finalized = dict(result)
        run_id = finalized.get("run_id")
        mark_run(run_id)
        if self._is_no_updates(finalized):
            return self._finalize_no_updates(
                finalized,
                digest_date=digest_date,
                digest_language=digest_language,
                send_empty_digest=send_empty_digest,
                telegram_enabled=telegram_enabled,
                email_enabled=email_enabled,
            )
        if finalized.get("summary_id"):
            finalized["deliveries"] = self.delivery.send_summary(
                int(finalized["summary_id"]),
                run_id,
                telegram_enabled=telegram_enabled,
                email_enabled=email_enabled,
            )
        return finalized

    def _finalize_no_updates(
        self,
        result: dict[str, Any],
        *,
        digest_date: str,
        digest_language: str,
        send_empty_digest: bool,
        telegram_enabled: bool | None = None,
        email_enabled: bool | None = None,
    ) -> dict[str, Any]:
        run_id = result.get("run_id")
        self._mark_no_updates(run_id)
        result["status"] = "no_updates"
        result["error_message"] = None
        if not send_empty_digest:
            result["empty_digest_delivered"] = False
            result["deliveries"] = []
            return result
        deliveries = self.delivery.send_no_updates(
            digest_date,
            digest_language,
            run_id,
            telegram_enabled=telegram_enabled,
            email_enabled=email_enabled,
        )
        result["empty_digest_delivered"] = any(item["status"] == "success" for item in deliveries)
        result["deliveries"] = deliveries
        return result

    def _mark_no_updates(self, run_id: int | None) -> None:
        if not run_id:
            return
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE DailyRuns
                SET status = 'no_updates', error_message = NULL, completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)
                WHERE run_id = ?
                """,
                (run_id,),
            )

    def _mark_job_run(self, run_id: int | None, job_id: int, run_type: str) -> None:
        if not run_id:
            return
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE DailyRuns SET run_type = ?, scheduled_job_id = ? WHERE run_id = ?",
                (run_type, job_id, run_id),
            )

    def _existing_job_run(self, job_id: int, run_date: str, window_mode: str) -> dict[str, Any] | None:
        window_days = self._window_days(window_mode)
        with self.db.connect() as conn:
            if window_days is None:
                row = conn.execute(
                    """
                    SELECT *
                    FROM DailyRuns
                    WHERE run_type = 'scheduled'
                      AND scheduled_job_id = ?
                      AND window_start IS NULL
                      AND window_end = ?
                    ORDER BY run_id DESC
                    LIMIT 1
                    """,
                    (job_id, run_date),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT *
                    FROM DailyRuns
                    WHERE run_type = 'scheduled'
                      AND scheduled_job_id = ?
                      AND window_start = date(?, ?)
                      AND window_end = ?
                    ORDER BY run_id DESC
                    LIMIT 1
                    """,
                    (job_id, run_date, f"-{window_days} day", run_date),
                ).fetchone()
        return dict(row) if row else None

    def _resolve_job_source_ids(self, job: dict[str, Any]) -> list[int]:
        sources = self.db.list_sources(enabled_only=True)
        if job["scope_type"] == "all_enabled":
            return [int(source["source_id"]) for source in sources]
        if job["scope_type"] == "groups":
            group_ids = {int(item) for item in job["group_ids"]}
            return [int(source["source_id"]) for source in sources if source.get("group_id") in group_ids]
        requested = {int(item) for item in job["source_ids"]}
        return [int(source["source_id"]) for source in sources if int(source["source_id"]) in requested]

    @staticmethod
    def _window_days(window_mode: str) -> int | None:
        if window_mode == "all_time":
            return None
        return {
            "last_1": 1,
            "last_3": 3,
            "last_7": 7,
        }.get(window_mode, 1)
