from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from pathlib import Path
from typing import Any

from .database import Database


_RESERVED_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class TranscriptExport:
    source: Path
    transcript: Path


class Exporter:
    def __init__(self, db: Database, export_dir: str | Path) -> None:
        self.db = db
        self.export_dir = Path(export_dir)

    def export_transcript(self, video_id: str, file_format: str = "md") -> TranscriptExport:
        data = self.db.get_video_transcript(video_id)
        transcript = data.get("transcript_clean")
        if not transcript:
            raise ValueError(f"Video {video_id} has no cleaned transcript")
        raw_source = data.get("transcript_raw_vtt")
        if not raw_source:
            raise ValueError(f"Video {video_id} has no source VTT transcript data")
        if file_format not in {"md", "txt"}:
            raise ValueError("Unsupported transcript export format. Use md or txt.")

        podcast_date = _display_date(data.get("video_date"))
        downloaded_at = _display_datetime(data.get("fetched_at"))
        video_dir = _video_export_dir(self.export_dir, data, podcast_date)
        video_dir.mkdir(parents=True, exist_ok=True)
        source_output = video_dir / "source.vtt"
        transcript_output = video_dir / f"transcript.{file_format}"
        if file_format == "txt":
            body = _render_text(data, podcast_date, downloaded_at, transcript)
        else:
            body = _render_markdown(data, podcast_date, downloaded_at, transcript)

        source_output.write_text(f"{raw_source.rstrip()}\n", encoding="utf-8")
        transcript_output.write_text(body, encoding="utf-8")
        return TranscriptExport(source=source_output, transcript=transcript_output)

    def export_summary(self, video_id: str, summary_id: int | None = None) -> Path:
        data = self.db.get_video_transcript(video_id)
        video = self.db.get_video(video_id)
        selected_summary_id = summary_id or video.get("summary_latest_id")
        if not selected_summary_id:
            raise ValueError(f"Video {video_id} has no summary")
        summary = self.db.get_summary(int(selected_summary_id))

        podcast_date = _display_date(data.get("video_date"))
        downloaded_at = _display_datetime(data.get("fetched_at"))
        video_dir = _video_export_dir(self.export_dir, data, podcast_date)
        video_dir.mkdir(parents=True, exist_ok=True)
        output = video_dir / "summary.md"
        body = _render_summary_markdown(data, podcast_date, downloaded_at, summary)
        output.write_text(body, encoding="utf-8")
        return output


def _display_date(value: str | None) -> str:
    date = (value or "").strip()
    return date[:10] if date else "unknown-podcast-date"


def _display_datetime(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "unknown-download-time"
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw[:19].replace("T", " ")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _video_export_dir(export_dir: Path, data: dict[str, Any], podcast_date: str) -> Path:
    podcast = _safe_filename_part(data.get("channel_name"), fallback="podcast", max_length=60)
    video = _safe_filename_part(data.get("video_title"), fallback=data["video_id"], max_length=120)
    date = _safe_filename_part(podcast_date, fallback="unknown-podcast-date", max_length=20)
    video_id = _safe_filename_part(data.get("video_id"), fallback="unknown-video-id", max_length=32)
    return export_dir / "videos" / podcast / f"{date} - {video_id} - {video}"


def _safe_filename_part(value: str | None, fallback: str, max_length: int) -> str:
    cleaned = _RESERVED_FILENAME_CHARS.sub(" ", (value or "").strip())
    cleaned = _WHITESPACE.sub(" ", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned or fallback


def _render_markdown(data: dict, podcast_date: str, downloaded_at: str, transcript: str) -> str:
    return (
        f"# {data['channel_name']}\n\n"
        f"## {data['video_title']}\n\n"
        f"Podcast Date: {podcast_date}\n"
        f"Downloaded At: {downloaded_at}\n"
        f"Video ID: {data['video_id']}\n"
        f"URL: {data['video_url']}\n\n"
        "## Transcript\n\n"
        f"{transcript}\n"
    )


def _render_text(data: dict, podcast_date: str, downloaded_at: str, transcript: str) -> str:
    return (
        f"Podcast: {data['channel_name']}\n"
        f"Video: {data['video_title']}\n"
        f"Podcast Date: {podcast_date}\n"
        f"Downloaded At: {downloaded_at}\n"
        f"Video ID: {data['video_id']}\n"
        f"URL: {data['video_url']}\n\n"
        "Transcript:\n\n"
        f"{transcript}\n"
    )


def _render_summary_markdown(
    data: dict,
    podcast_date: str,
    downloaded_at: str,
    summary: dict[str, Any],
) -> str:
    return (
        f"# {data['channel_name']}\n\n"
        f"## {data['video_title']}\n\n"
        f"Podcast Date: {podcast_date}\n"
        f"Downloaded At: {downloaded_at}\n"
        f"Video ID: {data['video_id']}\n"
        f"URL: {data['video_url']}\n"
        f"Summary ID: {summary['summary_id']}\n"
        f"Provider: {summary['model_provider']}\n"
        f"Model: {summary['model_name']}\n\n"
        "## Summary\n\n"
        f"{summary['content_markdown'].rstrip()}\n"
    )
