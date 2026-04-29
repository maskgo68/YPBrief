from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

import yaml

from .database import Database
from .youtube import YouTubeDataClient, extract_playlist_id, extract_video_id


SourceType = Literal["channel", "playlist", "video"]


def detect_source_type(source_input: str) -> SourceType:
    value = source_input.strip()
    if not value:
        raise ValueError("Source input is empty")

    if _looks_like_channel(value):
        return "channel"
    if _looks_like_playlist(value):
        return "playlist"
    return "video"


def parse_playlist_id(source_input: str) -> str:
    return extract_playlist_id(source_input)


class SourceService:
    def __init__(self, db: Database, youtube: YouTubeDataClient) -> None:
        self.db = db
        self.youtube = youtube

    def add(
        self,
        source_input: str,
        source_type: SourceType | None = None,
        name: str | None = None,
        display_name: str | None = None,
        enabled: bool = True,
        group_id: int | None = None,
        skip_existing: bool = False,
    ) -> dict[str, Any]:
        resolved_type = source_type or detect_source_type(source_input)
        if resolved_type == "channel":
            source_id = self._add_channel(source_input, name=name, display_name=display_name, enabled=enabled, skip_existing=skip_existing)
        elif resolved_type == "playlist":
            source_id = self._add_playlist(source_input, name=name, display_name=display_name, enabled=enabled, skip_existing=skip_existing)
        elif resolved_type == "video":
            source_id = self._add_video(source_input, name=name, display_name=display_name, enabled=enabled, skip_existing=skip_existing)
        else:
            raise ValueError(f"Unsupported source type: {resolved_type}")
        if group_id is not None:
            return self.db.update_source(source_id, group_id=group_id)
        return self.db.get_source(source_id)

    def bulk_add_lines(
        self,
        lines: list[str],
        *,
        group_id: int | None = None,
        source_type: SourceType | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "created": [],
            "duplicates": [],
            "failed": [],
            "ignored": 0,
        }
        seen_inputs: set[str] = set()
        for index, raw_line in enumerate(lines, start=1):
            line = _clean_bulk_line(raw_line)
            if not line:
                result["ignored"] += 1
                continue
            dedupe_key = line.lower()
            if dedupe_key in seen_inputs:
                result["duplicates"].append({"line": index, "input": line, "reason": "duplicate in upload"})
                continue
            seen_inputs.add(dedupe_key)
            try:
                source = self.add(
                    line,
                    source_type=source_type,
                    enabled=True,
                    group_id=group_id,
                    skip_existing=True,
                )
                result["created"].append(source)
            except DuplicateSourceError as exc:
                result["duplicates"].append({"line": index, "input": line, "reason": "already exists", "source": exc.source})
            except Exception as exc:
                result["failed"].append({"line": index, "input": line, "error": str(exc)})
        return result

    def list(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        return self.db.list_sources(enabled_only=enabled_only)

    def get(self, source_id: int) -> dict[str, Any]:
        return self.db.get_source(source_id)

    def enable(self, source_id: int) -> None:
        self.db.set_source_enabled(source_id, True)

    def disable(self, source_id: int) -> None:
        self.db.set_source_enabled(source_id, False)

    def delete(self, source_id: int) -> None:
        self.db.delete_source(source_id)

    def import_yaml(self, path: str | Path) -> int:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        groups = data.get("groups", [])
        sources = data.get("sources", [])
        if groups and not isinstance(groups, list):
            raise ValueError("sources.yaml must contain a list under 'groups'")
        if not isinstance(sources, list):
            raise ValueError("sources.yaml must contain a list under 'sources'")

        group_map: dict[str, int] = {}
        for item in groups:
            if not isinstance(item, dict):
                raise ValueError("Each group entry must be a mapping")
            group_name = str(item.get("group_name") or item.get("name") or "").strip()
            if not group_name:
                raise ValueError("Each group entry must include group_name or name")
            group = self.db.save_source_group(
                group_name=group_name,
                display_name=item.get("display_name"),
                description=item.get("description"),
                enabled=bool(item.get("enabled", True)),
                digest_title=item.get("digest_title"),
                digest_language=item.get("digest_language") or "zh",
                run_time=item.get("run_time") or "07:00",
                timezone=item.get("timezone") or "Asia/Shanghai",
                max_videos_per_source=int(item.get("max_videos_per_source") or 10),
                telegram_enabled=item.get("telegram_enabled"),
                email_enabled=item.get("email_enabled"),
                group_id=_resolve_existing_group_id(self.db, group_name),
            )
            group_map[group_name] = int(group["group_id"])

        count = 0
        for item in sources:
            if not isinstance(item, dict):
                raise ValueError("Each source entry must be a mapping")
            source_input = item.get("url") or item.get("id")
            if not source_input:
                raise ValueError("Each source entry must include url or id")
            group_name = str(item.get("group") or "").strip()
            group_id = group_map.get(group_name) if group_name else None
            if group_id is None and group_name:
                group_id = _resolve_existing_group_id(self.db, group_name)
            self.add(
                str(source_input),
                source_type=item.get("type"),
                display_name=item.get("display_name") or item.get("name"),
                enabled=bool(item.get("enabled", True)),
                group_id=group_id,
            )
            count += 1
        return count

    def export_yaml(self, path: str | Path) -> None:
        rows = self.list()
        groups = self.db.list_source_groups()
        data = {
            "groups": [
                {
                    "group_name": row["group_name"],
                    "display_name": row.get("display_name"),
                    "description": row.get("description"),
                    "enabled": bool(row["enabled"]),
                    "digest_title": row.get("digest_title"),
                    "digest_language": row.get("digest_language"),
                    "run_time": row.get("run_time"),
                    "timezone": row.get("timezone"),
                    "max_videos_per_source": row.get("max_videos_per_source"),
                }
                for row in groups
            ],
            "sources": [
                {
                    "type": row["source_type"],
                    "name": row["source_name"],
                    "display_name": row.get("display_name"),
                    "url": row["url"],
                    "enabled": bool(row["enabled"]),
                    "group": row.get("group_name"),
                }
                for row in rows
            ]
        }
        Path(path).write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _add_channel(
        self,
        source_input: str,
        name: str | None,
        display_name: str | None,
        enabled: bool,
        skip_existing: bool = False,
    ) -> int:
        channel = self.youtube.resolve_channel(source_input)
        existing = self.db.get_source_by_identity("channel", channel.channel_id)
        if skip_existing and existing:
            raise DuplicateSourceError(existing)
        self.db.upsert_channel(
            channel.channel_id,
            channel.channel_name,
            channel.channel_url,
            handle=channel.handle,
            uploads_playlist_id=channel.uploads_playlist_id,
        )
        return self.db.upsert_source(
            source_type="channel",
            source_name=name or channel.channel_name,
            display_name=display_name,
            youtube_id=channel.channel_id,
            url=channel.channel_url,
            channel_id=channel.channel_id,
            channel_name=channel.channel_name,
            enabled=enabled,
        )

    def _add_playlist(
        self,
        source_input: str,
        name: str | None,
        display_name: str | None,
        enabled: bool,
        skip_existing: bool = False,
    ) -> int:
        playlist = self.youtube.get_playlist(source_input)
        existing = self.db.get_source_by_identity("playlist", playlist.playlist_id)
        if skip_existing and existing:
            raise DuplicateSourceError(existing)
        return self.db.upsert_source(
            source_type="playlist",
            source_name=name or playlist.playlist_name,
            display_name=display_name,
            youtube_id=playlist.playlist_id,
            url=playlist.playlist_url,
            channel_id=playlist.channel_id,
            channel_name=playlist.channel_name,
            playlist_id=playlist.playlist_id,
            enabled=enabled,
        )

    def _add_video(
        self,
        source_input: str,
        name: str | None,
        display_name: str | None,
        enabled: bool,
        skip_existing: bool = False,
    ) -> int:
        video = self.youtube.get_video(source_input)
        existing = self.db.get_source_by_identity("video", video.video_id)
        if skip_existing and existing:
            raise DuplicateSourceError(existing)
        return self.db.upsert_source(
            source_type="video",
            source_name=name or video.title,
            display_name=display_name,
            youtube_id=video.video_id,
            url=video.url,
            channel_id=video.channel_id,
            channel_name=video.channel_name,
            enabled=enabled,
        )


class DuplicateSourceError(ValueError):
    def __init__(self, source: dict[str, Any]) -> None:
        self.source = source
        super().__init__(f"Source already exists: {source.get('source_name') or source.get('youtube_id')}")


def _clean_bulk_line(value: str) -> str:
    line = value.strip()
    if not line or line.startswith("#"):
        return ""
    if "#" in line:
        line = line.split("#", 1)[0].strip()
    return line


def _looks_like_channel(value: str) -> bool:
    if value.startswith("@") or value.startswith("UC"):
        return True
    if not value.startswith("http"):
        return False
    parsed = urlparse(value)
    path = parsed.path.strip("/")
    return path.startswith("@") or path.startswith(("channel/", "c/", "user/"))


def _looks_like_playlist(value: str) -> bool:
    if value.startswith(("PL", "UU", "OLAK5uy_")):
        return True
    if not value.startswith("http"):
        return False
    parsed = urlparse(value)
    return bool(parse_qs(parsed.query).get("list")) and not bool(parse_qs(parsed.query).get("v"))


def _resolve_existing_group_id(db: Database, group_name: str | None) -> int | None:
    name = (group_name or "").strip()
    if not name:
        return None
    for group in db.list_source_groups():
        if group["group_name"] == name:
            return int(group["group_id"])
    return None
