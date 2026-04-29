from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Protocol

from .config import Settings
from .database import Database
from .prompts import DEFAULT_PROMPTS, DatabasePromptService
from .text_normalization import clean_summary_markdown
from .video_processor import MIN_SUMMARY_VIDEO_SECONDS


class DigestProvider(Protocol):
    name: str
    model: str

    def summarize(self, prompt: str, transcript: str) -> str:
        ...


class VideoDiscoverySource(Protocol):
    def resolve_channel(self, channel_input: str):
        ...

    def iter_playlist_items(self, playlist_input: str, limit: int | None = None):
        ...

    def iter_uploads(self, uploads_playlist_id: str, limit: int | None = None):
        ...

    def get_video(self, video_input: str):
        ...


class VideoProcessorLike(Protocol):
    def process(self, video_input: str):
        ...


@dataclass(frozen=True)
class DailyDigestResult:
    summary_id: int
    video_count: int
    daily_summary: Path
    videos_manifest: Path
    failed_manifest: Path


class DailyDigestService:
    def __init__(self, db: Database, provider: DigestProvider, export_dir: str | Path, settings: Settings | None = None) -> None:
        self.db = db
        self.provider = provider
        self.export_dir = Path(export_dir)
        self.settings = settings or Settings()

    def summarize_videos(
        self,
        video_ids: list[str],
        run_date: str,
        digest_language: str | None = None,
        source_ids_by_video: dict[str, int] | None = None,
    ) -> DailyDigestResult:
        if not video_ids:
            raise ValueError("At least one video_id is required")

        videos = [
            self._get_video_with_latest_summary(video_id, (source_ids_by_video or {}).get(video_id))
            for video_id in video_ids
        ]
        digest_input = "\n\n---\n\n".join(_render_video_block(video) for video in videos)
        prompt, fallback_input = _default_daily_prompt_input(digest_input, run_date, digest_language)
        prompt_version = "daily-v1"
        try:
            prompt_service = DatabasePromptService(self.db, self.settings.prompt_file)
            active_prompt = prompt_service.get("daily_digest")
            rendered = prompt_service.preview(
                "daily_digest",
                {
                    "summaries": digest_input,
                    "run_date": run_date,
                    "digest_language": digest_language or getattr(self.settings, "scheduler_digest_language", "zh") or "zh",
                },
            )
            prompt = rendered["system_prompt"] or prompt
            digest_input = rendered["user_prompt"]
            prompt_version = f"db:{active_prompt.get('version') or 'daily_digest'}"
        except KeyError:
            digest_input = fallback_input
        content = clean_summary_markdown(self.provider.summarize(prompt, digest_input))
        summary_id = self.db.save_summary(
            summary_type="digest",
            content_markdown=content,
            provider=self.provider.name,
            model=self.provider.model,
            range_start=run_date,
            range_end=run_date,
            provider_base_url=getattr(self.provider, "base_url", None),
            prompt_version=prompt_version,
        )

        daily_summary, videos_manifest, failed_manifest = daily_artifact_paths(self.export_dir, run_date)
        daily_summary.write_text(f"{content.rstrip()}\n", encoding="utf-8")
        videos_manifest.write_text(_render_videos_manifest(videos), encoding="utf-8")
        failed_manifest.write_text(
            "# Failed Videos\n\nNo failures in this daily-summary run.\n",
            encoding="utf-8",
        )

        return DailyDigestResult(
            summary_id=summary_id,
            video_count=len(videos),
            daily_summary=daily_summary,
            videos_manifest=videos_manifest,
            failed_manifest=failed_manifest,
        )

    def _get_video_with_latest_summary(self, video_id: str, source_id: int | None = None) -> dict:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT v.video_id, v.video_title, v.video_url, v.video_date,
                       c.channel_name, s.summary_id, s.content_markdown
                FROM Videos v
                JOIN Channels c ON c.channel_id = v.channel_id
                JOIN Summaries s ON s.summary_id = v.summary_latest_id
                WHERE v.video_id = ?
                """,
                (video_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Video {video_id} has no latest saved summary")
        video = dict(row)
        source = self._get_digest_source(video_id, source_id)
        video["source_title"] = _source_title(video, source)
        return video

    def _get_digest_source(self, video_id: str, source_id: int | None) -> dict | None:
        with self.db.connect() as conn:
            if source_id is not None:
                row = conn.execute(
                    """
                    SELECT source_type, source_name, display_name, channel_name, playlist_id
                    FROM Sources
                    WHERE source_id = ?
                    """,
                    (source_id,),
                ).fetchone()
                return dict(row) if row else None
            row = conn.execute(
                """
                SELECT s.source_type, s.source_name, s.display_name, s.channel_name, s.playlist_id
                FROM SourceVideos sv
                JOIN Sources s ON s.source_id = sv.source_id
                WHERE sv.video_id = ?
                ORDER BY
                    CASE s.source_type WHEN 'playlist' THEN 0 WHEN 'channel' THEN 1 ELSE 2 END,
                    sv.discovered_at DESC,
                    s.source_id
                LIMIT 1
                """,
                (video_id,),
            ).fetchone()
        return dict(row) if row else None


class DigestRunService:
    def __init__(
        self,
        db: Database,
        youtube: VideoDiscoverySource,
        processor: VideoProcessorLike,
        digest_service: DailyDigestService,
    ) -> None:
        self.db = db
        self.youtube = youtube
        self.processor = processor
        self.digest_service = digest_service

    def run(
        self,
        source_ids: list[int],
        run_date: str,
        window_days: int | None,
        max_videos_per_source: int | None = 10,
        reuse_existing_summaries: bool = True,
        process_missing_videos: bool = True,
        retry_failed_once: bool = True,
        digest_language: str | None = None,
    ) -> dict:
        if not source_ids:
            raise ValueError("At least one source_id is required")
        window_start, window_end = _window(run_date, window_days)
        run_id = self._create_run(source_ids, window_start, window_end)
        included: list[str] = []
        source_ids_by_video: dict[str, int] = {}
        failed: list[tuple[str, int, str]] = []
        skipped: list[tuple[str, int, str]] = []

        try:
            for source in [self.db.get_source(source_id) for source_id in source_ids]:
                candidates = self._discover(source, max_videos_per_source)
                selected_videos = _select_videos(candidates, window_start, window_end, max_videos_per_source)
                for position, video in enumerate(selected_videos, start=1):
                    published = _date_part(getattr(video, "published_at", None))
                    video_id = getattr(video, "video_id", "")
                    if not video_id:
                        continue
                    channel_id = getattr(video, "channel_id", None) or source.get("channel_id") or f"channel-{video_id}"
                    channel_name = getattr(video, "channel_name", None) or source.get("channel_name") or channel_id
                    self.db.upsert_channel(channel_id, channel_name, f"https://www.youtube.com/channel/{channel_id}")
                    self.db.upsert_video(
                        video_id=video_id,
                        channel_id=channel_id,
                        video_title=getattr(video, "title", video_id),
                        video_url=getattr(video, "url", f"https://www.youtube.com/watch?v={video_id}"),
                        video_date=published,
                        duration=getattr(video, "duration_seconds", None),
                    )
                    self._record_source_video(source["source_id"], video_id, position, published)

                    video_status = self._video_status(video_id)
                    if video_status == "failed" and not retry_failed_once:
                        skipped.append((video_id, source["source_id"], "previously failed"))
                        self._record_run_video(run_id, video_id, source["source_id"], "skipped", "skip", "previously failed", None)
                        continue

                    summary_id = self._latest_summary_id(video_id) if reuse_existing_summaries else None
                    try:
                        if summary_id is None:
                            if not process_missing_videos:
                                skipped.append((video_id, source["source_id"], "missing summary"))
                                self._record_run_video(run_id, video_id, source["source_id"], "skipped", "skip", "missing summary", None)
                                continue
                            self.processor.process(video_id)
                            summary_id = self._latest_summary_id(video_id)
                        if summary_id is None:
                            raise ValueError("summary was not created")
                        included.append(video_id)
                        source_ids_by_video.setdefault(video_id, int(source["source_id"]))
                        self._record_run_video(run_id, video_id, source["source_id"], "included", "include", None, summary_id)
                    except Exception as exc:
                        failed.append((video_id, source["source_id"], str(exc)))
                        self._record_run_video(run_id, video_id, source["source_id"], "failed", "process", str(exc), None)

            unique_included = list(dict.fromkeys(included))
            summary_id = None
            if unique_included:
                digest = self.digest_service.summarize_videos(
                    unique_included,
                    run_date=run_date,
                    digest_language=digest_language,
                    source_ids_by_video=source_ids_by_video,
                )
                summary_id = digest.summary_id
                _write_failed_manifest(digest.failed_manifest, failed, skipped)

            status = "completed" if summary_id is not None else "failed"
            self._complete_run(run_id, status, summary_id, len(unique_included), len(failed), len(skipped), None if summary_id else "No videos included")
            return self.get_run(run_id)
        except Exception as exc:
            self._complete_run(run_id, "failed", None, len(set(included)), len(failed), len(skipped), str(exc))
            raise

    def get_run(self, run_id: int) -> dict:
        with self.db.connect() as conn:
            run = conn.execute("SELECT * FROM DailyRuns WHERE run_id = ?", (run_id,)).fetchone()
            videos = conn.execute("SELECT * FROM DailyRunVideos WHERE run_id = ? ORDER BY video_id", (run_id,)).fetchall()
        if run is None:
            raise KeyError(run_id)
        data = dict(run)
        data["videos"] = [dict(row) for row in videos]
        return data

    def _discover(self, source: dict, limit: int | None):
        candidate_limit = None if limit is None else max(limit * 3, 20)
        if source["source_type"] == "playlist":
            return self.youtube.iter_playlist_items(source["url"], limit=candidate_limit)
        if source["source_type"] == "channel":
            channel_id = source.get("channel_id") or source["youtube_id"]
            channel = self.db.get_channel(channel_id)
            uploads_playlist_id = channel.get("uploads_playlist_id")
            if not uploads_playlist_id:
                refreshed = self.youtube.resolve_channel(channel_id)
                self.db.upsert_channel(
                    refreshed.channel_id,
                    refreshed.channel_name,
                    refreshed.channel_url,
                    refreshed.handle,
                    refreshed.uploads_playlist_id,
                )
                uploads_playlist_id = refreshed.uploads_playlist_id
            if not uploads_playlist_id:
                raise ValueError(f"Uploads playlist not found for channel source: {source.get('source_name') or channel_id}")
            return self.youtube.iter_uploads(uploads_playlist_id, limit=candidate_limit)
        if source["source_type"] == "video":
            return [self.youtube.get_video(source["url"])]
        raise ValueError(f"Unsupported source type: {source['source_type']}")

    def _create_run(self, source_ids: list[int], window_start: str | None, window_end: str | None) -> int:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO DailyRuns(run_type, status, window_start, window_end, source_ids_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("manual", "running", window_start, window_end, json.dumps(source_ids)),
            )
            return int(cursor.lastrowid)

    def _complete_run(
        self,
        run_id: int,
        status: str,
        summary_id: int | None,
        included: int,
        failed: int,
        skipped: int,
        error_message: str | None,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE DailyRuns
                SET status = ?, summary_id = ?, included_count = ?, failed_count = ?,
                    skipped_count = ?, completed_at = CURRENT_TIMESTAMP, error_message = ?
                WHERE run_id = ?
                """,
                (status, summary_id, included, failed, skipped, error_message, run_id),
            )

    def _record_source_video(self, source_id: int, video_id: str, position: int, published: str | None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO SourceVideos(source_id, video_id, source_position, published_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id, video_id) DO UPDATE SET
                    source_position=excluded.source_position,
                    published_at=excluded.published_at,
                    discovered_at=CURRENT_TIMESTAMP
                """,
                (source_id, video_id, position, published),
            )

    def _record_run_video(
        self,
        run_id: int,
        video_id: str,
        source_id: int,
        status: str,
        action: str,
        error_message: str | None,
        summary_id: int | None,
    ) -> None:
        source_name_snapshot = None
        display_name_snapshot = None
        source_type_snapshot = None
        try:
            source = self.db.get_source(source_id)
            source_name_snapshot = source.get("source_name")
            display_name_snapshot = source.get("display_name")
            source_type_snapshot = source.get("source_type")
        except KeyError:
            pass
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO DailyRunVideos(
                    run_id, video_id, source_id, source_name_snapshot, display_name_snapshot,
                    source_type_snapshot, status, action, error_message, summary_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    video_id,
                    source_id,
                    source_name_snapshot,
                    display_name_snapshot,
                    source_type_snapshot,
                    status,
                    action,
                    error_message,
                    summary_id,
                ),
            )

    def _latest_summary_id(self, video_id: str) -> int | None:
        try:
            video = self.db.get_video(video_id)
        except KeyError:
            return None
        return int(video["summary_latest_id"]) if video.get("summary_latest_id") else None

    def _video_status(self, video_id: str) -> str | None:
        try:
            video = self.db.get_video(video_id)
        except KeyError:
            return None
        return video.get("status")


def _default_daily_prompt_input(digest_input: str, run_date: str, digest_language: str | None) -> tuple[str, str]:
    default = DEFAULT_PROMPTS["daily_digest"]
    values = {
        "summaries": digest_input,
        "run_date": run_date,
        "digest_language": digest_language or "zh",
    }
    system_prompt = str(default["system_prompt"])
    user_prompt = str(default["user_template"])
    for key, value in values.items():
        user_prompt = user_prompt.replace("{{ " + key + " }}", str(value))
        user_prompt = user_prompt.replace("{{" + key + "}}", str(value))
    return system_prompt, user_prompt


def daily_artifact_paths(export_dir: str | Path, run_date: str, now: datetime | None = None) -> tuple[Path, Path, Path]:
    output_dir = Path(export_dir) / "daily" / run_date
    output_dir.mkdir(parents=True, exist_ok=True)
    names = ("daily-summary", "videos", "failed")
    base_paths = tuple(output_dir / f"{name}.md" for name in names)
    if not any(path.exists() for path in base_paths):
        return base_paths

    timestamp = (now or datetime.now()).strftime("%H%M%S")
    attempt = 0
    while True:
        suffix = timestamp if attempt == 0 else f"{timestamp}-{attempt + 1}"
        paths = tuple(output_dir / f"{name}-{suffix}.md" for name in names)
        if not any(path.exists() for path in paths):
            return paths
        attempt += 1


def _render_video_block(video: dict) -> str:
    source_title = video.get("source_title") or f"{video['channel_name']} | {video['video_title']}"
    return (
        f"## {source_title}\n"
        f"Source Title: {source_title}\n"
        f"Channel: {video['channel_name']}\n"
        f"Video ID: {video['video_id']}\n"
        f"Date: {video.get('video_date') or ''}\n"
        f"URL: {video['video_url']}\n\n"
        f"{video['content_markdown']}"
    )


def _render_videos_manifest(videos: list[dict]) -> str:
    lines = ["# Processed Videos", ""]
    for video in videos:
        lines.append(
            " | ".join(
                [
                    f"- {video.get('source_title') or video['channel_name']}",
                    video.get("video_date") or "",
                    f"`{video['video_id']}`",
                    video["video_title"],
                    video["video_url"],
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _source_title(video: dict, source: dict | None) -> str:
    channel_name = _clean_label(
        (source or {}).get("channel_name")
        or video.get("channel_name")
        or ""
    )
    video_title = _clean_label(video.get("video_title") or video.get("video_id") or "")
    if source and source.get("source_type") == "playlist":
        playlist_name = _clean_label(source.get("display_name") or source.get("source_name") or source.get("playlist_id") or "")
        return " | ".join(part for part in [channel_name, playlist_name, video_title] if part)
    if source and source.get("source_type") == "channel":
        channel_label = _clean_label(source.get("channel_name") or source.get("source_name") or channel_name)
        return " | ".join(part for part in [channel_label, video_title] if part)
    return " | ".join(part for part in [channel_name, video_title] if part)


def _clean_label(value: str | None) -> str:
    return (value or "").strip()


def _select_videos(videos, window_start: str | None, window_end: str | None, limit: int | None):
    usable = [
        video
        for video in videos
        if getattr(video, "video_id", "")
        and _in_window(_date_part(getattr(video, "published_at", None)), window_start, window_end)
        and not _is_unusable_video(video)
    ]
    selected = sorted(usable, key=_published_sort_key, reverse=True)
    return selected if limit is None else selected[:limit]


def _is_unusable_video(video) -> bool:
    title = (getattr(video, "title", "") or "").strip().lower()
    duration = getattr(video, "duration_seconds", None)
    return title in {"private video", "deleted video"} or (
        duration is not None and duration <= MIN_SUMMARY_VIDEO_SECONDS
    )


def _published_sort_key(video) -> str:
    return getattr(video, "published_at", "") or ""


def _window(run_date: str, window_days: int | None) -> tuple[str | None, str]:
    end = date.fromisoformat(run_date)
    if window_days is None:
        return None, end.isoformat()
    start = end - timedelta(days=window_days)
    return start.isoformat(), end.isoformat()


def _date_part(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def _in_window(value: str | None, start: str | None, end: str | None) -> bool:
    if not value:
        return False
    if start is None:
        return True if end is None else value < end
    if end is None:
        return start <= value
    return start <= value < end


def _write_failed_manifest(path: Path, failed: list[tuple[str, int, str]], skipped: list[tuple[str, int, str]]) -> None:
    lines = ["# Failed Videos", ""]
    if not failed and not skipped:
        lines.append("No failures in this daily-summary run.")
    for video_id, source_id, error in failed:
        lines.append(f"- failed | source={source_id} | `{video_id}` | {error}")
    for video_id, source_id, reason in skipped:
        lines.append(f"- skipped | source={source_id} | `{video_id}` | {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
