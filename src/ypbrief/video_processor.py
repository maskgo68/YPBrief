from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .cleaner import clean_transcript
from .config import Settings
from .database import Database
from .exporter import Exporter
from .summarizer import SummaryProvider, Summarizer
from .transcripts import TranscriptFetchResult, preferred_subtitle_languages
from .youtube import VideoInfo, YouTubeDataClient, extract_video_id


MIN_SUMMARY_VIDEO_SECONDS = 300


class YouTubeVideoSource(Protocol):
    def get_video(self, video_input: str) -> VideoInfo:
        ...


class TranscriptSource(Protocol):
    def fetch(self, video_id: str, languages: list[str] | None = None) -> TranscriptFetchResult:
        ...


@dataclass(frozen=True)
class VideoProcessResult:
    video_id: str
    summary_id: int
    source_vtt: Path
    transcript_md: Path
    summary_md: Path


def parse_video_id(video_input: str) -> str:
    return extract_video_id(video_input)


class VideoProcessor:
    def __init__(
        self,
        db: Database,
        youtube: YouTubeVideoSource,
        transcripts: TranscriptSource,
        provider: SummaryProvider,
        export_dir: str | Path,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.youtube = youtube
        self.transcripts = transcripts
        self.summarizer = Summarizer(db=db, provider=provider, settings=settings)
        self.exporter = Exporter(db=db, export_dir=export_dir)

    @classmethod
    def from_api_key(
        cls,
        db: Database,
        youtube_api_key: str,
        transcripts: TranscriptSource,
        provider: SummaryProvider,
        export_dir: str | Path,
        settings: Settings | None = None,
    ) -> "VideoProcessor":
        return cls(
            db=db,
            youtube=YouTubeDataClient(youtube_api_key),
            transcripts=transcripts,
            provider=provider,
            export_dir=export_dir,
            settings=settings,
        )

    def process(self, video_input: str, output_language: str | None = None) -> VideoProcessResult:
        video = self.youtube.get_video(video_input)
        channel_id = video.channel_id or f"channel-{video.video_id}"
        channel_name = video.channel_name or channel_id
        self.db.upsert_channel(
            channel_id=channel_id,
            channel_name=channel_name,
            channel_url=f"https://www.youtube.com/channel/{channel_id}",
        )
        self.db.upsert_video(
            video_id=video.video_id,
            channel_id=channel_id,
            video_title=video.title,
            video_url=video.url,
            video_date=(video.published_at or "")[:10] or None,
            duration=video.duration_seconds,
        )
        if _is_short_video(video.duration_seconds):
            reason = (
                f"short_video: duration {video.duration_seconds} seconds is shorter than "
                f"{MIN_SUMMARY_VIDEO_SECONDS} seconds"
            )
            self.db.mark_video_skipped(video.video_id, reason)
            raise ValueError(reason)

        languages = preferred_subtitle_languages(video.default_language or "en")
        transcript_result = self.transcripts.fetch(video.video_id, languages=languages)
        cleaned = clean_transcript(transcript_result.segments)
        raw_json = json.dumps(
            {
                "source": transcript_result.source,
                "language_priority": languages,
                "segments": [asdict(segment) for segment in transcript_result.segments],
            },
            ensure_ascii=False,
        )
        self.db.save_transcript(
            video_id=video.video_id,
            raw_json=raw_json,
            raw_vtt=transcript_result.source_vtt,
            clean_text=cleaned.text,
            segments=cleaned.segments,
        )
        transcript_export = self.exporter.export_transcript(video.video_id)
        summary_id = self.summarizer.summarize_video(video.video_id, output_language=output_language)
        summary_md = self.exporter.export_summary(video.video_id, summary_id=summary_id)
        return VideoProcessResult(
            video_id=video.video_id,
            summary_id=summary_id,
            source_vtt=transcript_export.source,
            transcript_md=transcript_export.transcript,
            summary_md=summary_md,
        )


def _is_short_video(duration_seconds: int | None) -> bool:
    return duration_seconds is not None and duration_seconds <= MIN_SUMMARY_VIDEO_SECONDS
