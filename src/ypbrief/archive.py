from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Protocol

from .cleaner import clean_transcript
from .database import Database
from .transcripts import TranscriptFetcher, TranscriptFetchResult
from .youtube import ChannelInfo, YouTubeDataClient


class YouTubeSource(Protocol):
    def resolve_channel(self, channel_input: str) -> ChannelInfo:
        ...

    def iter_uploads(self, uploads_playlist_id: str, limit: int | None = None):
        ...


class TranscriptSource(Protocol):
    def fetch(self, video_id: str, languages: list[str] | None = None) -> TranscriptFetchResult:
        ...


class ArchiveService:
    def __init__(
        self,
        db: Database,
        youtube: YouTubeSource | None = None,
        transcripts: TranscriptSource | None = None,
    ) -> None:
        self.db = db
        self.youtube = youtube
        self.transcripts = transcripts or TranscriptFetcher()

    @classmethod
    def from_api_key(cls, db: Database, youtube_api_key: str) -> "ArchiveService":
        return cls(db=db, youtube=YouTubeDataClient(youtube_api_key))

    def add_channel(self, channel_input: str) -> ChannelInfo:
        if self.youtube is None:
            raise ValueError("YouTube source is required to add channels")
        channel = self.youtube.resolve_channel(channel_input)
        self.db.upsert_channel(
            channel_id=channel.channel_id,
            channel_name=channel.channel_name,
            channel_url=channel.channel_url,
            handle=channel.handle,
            uploads_playlist_id=channel.uploads_playlist_id,
        )
        return channel

    def update_channel(self, channel_ref: str, languages: list[str] | None = None) -> dict[str, int]:
        if self.youtube is None:
            raise ValueError("YouTube source is required to update channels")

        channel = self.db.get_channel(channel_ref)
        uploads_playlist_id = channel.get("uploads_playlist_id")
        if not uploads_playlist_id:
            raise ValueError(f"Channel {channel_ref} does not have uploads_playlist_id")

        stats = {
            "videos_seen": 0,
            "transcripts_saved": 0,
            "failed": 0,
        }
        for video in self.youtube.iter_uploads(uploads_playlist_id):
            stats["videos_seen"] += 1
            self.db.upsert_video(
                video_id=video.video_id,
                channel_id=channel["channel_id"],
                video_title=video.title,
                video_url=video.url,
                video_date=(video.published_at or "")[:10] or None,
            )
            try:
                transcript_result = self.transcripts.fetch(video.video_id, languages=languages)
                cleaned = clean_transcript(transcript_result.segments)
                raw_json = json.dumps(
                    {
                        "source": transcript_result.source,
                        "segments": [asdict(segment) for segment in transcript_result.segments],
                    },
                    ensure_ascii=False,
                )
                self.db.save_transcript(
                    video_id=video.video_id,
                    raw_json=raw_json,
                    clean_text=cleaned.text,
                    segments=cleaned.segments,
                    raw_vtt=transcript_result.source_vtt,
                )
                stats["transcripts_saved"] += 1
            except Exception as exc:
                self.db.mark_video_failed(video.video_id, str(exc))
                stats["failed"] += 1
        return stats
