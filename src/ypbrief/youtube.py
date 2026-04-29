from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlparse
from typing import Protocol

import requests


YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


class HTTPClient(Protocol):
    def get_json(self, url: str, params: dict[str, str]) -> dict:
        ...


class RequestsHTTPClient:
    def get_json(self, url: str, params: dict[str, str]) -> dict:
        response = requests.get(url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            endpoint = url.rstrip("/").rsplit("/", 1)[-1] or "YouTube API"
            detail = _youtube_error_detail(response)
            message = f"YouTube API request failed: {endpoint} returned HTTP {response.status_code}"
            if detail:
                message = f"{message} ({detail})"
            raise RuntimeError(message) from exc
        return response.json()


@dataclass(frozen=True)
class ChannelInfo:
    channel_id: str
    channel_name: str
    channel_url: str
    handle: str | None
    uploads_playlist_id: str


@dataclass(frozen=True)
class VideoInfo:
    video_id: str
    title: str
    url: str
    published_at: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    default_language: str | None = None
    duration_seconds: int | None = None


@dataclass(frozen=True)
class PlaylistInfo:
    playlist_id: str
    playlist_name: str
    playlist_url: str
    channel_id: str | None
    channel_name: str | None
    item_count: int | None = None


class YouTubeDataClient:
    def __init__(self, api_key: str, http: HTTPClient | None = None) -> None:
        self.api_key = api_key
        self.http = http or RequestsHTTPClient()

    def resolve_channel(self, channel_input: str) -> ChannelInfo:
        params = {
            "part": "snippet,contentDetails",
            "key": self.api_key,
        }
        normalized = channel_input.strip().rstrip("/")
        if normalized.startswith("http"):
            normalized = normalized.split("/")[-1]
        if normalized.startswith("@"):
            params["forHandle"] = normalized[1:]
        elif normalized.startswith("UC"):
            params["id"] = normalized
        else:
            params["forHandle"] = normalized

        data = self.http.get_json(f"{YOUTUBE_API}/channels", params)
        items = data.get("items", [])
        if not items:
            raise ValueError(f"Channel not found: {channel_input}")

        item = items[0]
        channel_id = item["id"]
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        uploads = content_details.get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            raise ValueError(f"Uploads playlist not found for channel: {channel_input}")

        handle = snippet.get("customUrl")
        return ChannelInfo(
            channel_id=channel_id,
            channel_name=snippet.get("title", channel_id),
            channel_url=f"https://www.youtube.com/channel/{channel_id}",
            handle=handle,
            uploads_playlist_id=uploads,
        )

    def iter_uploads(self, uploads_playlist_id: str, limit: int | None = None) -> list[VideoInfo]:
        videos: list[VideoInfo] = []
        page_token: str | None = None
        while True:
            params = {
                "part": "snippet",
                "playlistId": uploads_playlist_id,
                "maxResults": "50",
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self.http.get_json(f"{YOUTUBE_API}/playlistItems", params)
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId")
                if not video_id:
                    continue
                videos.append(
                    VideoInfo(
                        video_id=video_id,
                        title=snippet.get("title", video_id),
                        url=f"https://youtu.be/{video_id}",
                        published_at=snippet.get("publishedAt"),
                    )
                )
                if limit is not None and len(videos) >= limit:
                    return self._hydrate_video_details(videos)
            page_token = data.get("nextPageToken")
            if not page_token:
                return self._hydrate_video_details(videos)

    def get_video(self, video_input: str) -> VideoInfo:
        video_id = extract_video_id(video_input)
        params = {
            "part": "snippet,contentDetails",
            "id": video_id,
            "key": self.api_key,
        }
        data = self.http.get_json(f"{YOUTUBE_API}/videos", params)
        items = data.get("items", [])
        if not items:
            raise ValueError(f"Video not found: {video_input}")

        item = items[0]
        snippet = item.get("snippet", {})
        return VideoInfo(
            video_id=video_id,
            title=snippet.get("title", video_id),
            url=f"https://www.youtube.com/watch?v={video_id}",
            published_at=snippet.get("publishedAt"),
            channel_id=snippet.get("channelId"),
            channel_name=snippet.get("channelTitle"),
            default_language=snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage"),
            duration_seconds=parse_iso8601_duration(item.get("contentDetails", {}).get("duration")),
        )

    def get_playlist(self, playlist_input: str) -> PlaylistInfo:
        playlist_id = extract_playlist_id(playlist_input)
        params = {
            "part": "snippet,contentDetails",
            "id": playlist_id,
            "key": self.api_key,
        }
        data = self.http.get_json(f"{YOUTUBE_API}/playlists", params)
        items = data.get("items", [])
        if not items:
            raise ValueError(f"Playlist not found: {playlist_input}")

        item = items[0]
        snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})
        return PlaylistInfo(
            playlist_id=playlist_id,
            playlist_name=snippet.get("title", playlist_id),
            playlist_url=f"https://www.youtube.com/playlist?list={playlist_id}",
            channel_id=snippet.get("channelId"),
            channel_name=snippet.get("channelTitle"),
            item_count=content.get("itemCount"),
        )

    def iter_playlist_items(self, playlist_input: str, limit: int | None = None) -> list[VideoInfo]:
        playlist_id = extract_playlist_id(playlist_input)
        videos: list[VideoInfo] = []
        page_token: str | None = None
        while True:
            params = {
                "part": "snippet,contentDetails,status",
                "playlistId": playlist_id,
                "maxResults": "50",
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self.http.get_json(f"{YOUTUBE_API}/playlistItems", params)
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId") or item.get("contentDetails", {}).get("videoId")
                if not video_id:
                    continue
                videos.append(
                    VideoInfo(
                        video_id=video_id,
                        title=snippet.get("title", video_id),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        published_at=snippet.get("publishedAt"),
                        channel_id=snippet.get("videoOwnerChannelId") or snippet.get("channelId"),
                        channel_name=snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle"),
                    )
                )
                if limit is not None and len(videos) >= limit:
                    return self._hydrate_video_details(videos)
            page_token = data.get("nextPageToken")
            if not page_token:
                return self._hydrate_video_details(videos)

    def _hydrate_video_details(self, videos: list[VideoInfo]) -> list[VideoInfo]:
        ids = [video.video_id for video in videos if video.video_id]
        if not ids:
            return videos
        details: dict[str, dict] = {}
        for start in range(0, len(ids), 50):
            params = {
                "part": "snippet,contentDetails",
                "id": ",".join(ids[start:start + 50]),
                "key": self.api_key,
            }
            data = self.http.get_json(f"{YOUTUBE_API}/videos", params)
            for item in data.get("items", []):
                video_id = item.get("id")
                if video_id:
                    details[video_id] = item
        hydrated: list[VideoInfo] = []
        for video in videos:
            item = details.get(video.video_id, {})
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            hydrated.append(
                VideoInfo(
                    video_id=video.video_id,
                    title=snippet.get("title") or video.title,
                    url=video.url,
                    published_at=snippet.get("publishedAt") or video.published_at,
                    channel_id=snippet.get("channelId") or video.channel_id,
                    channel_name=snippet.get("channelTitle") or video.channel_name,
                    default_language=snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or video.default_language,
                    duration_seconds=parse_iso8601_duration(content.get("duration")) or video.duration_seconds,
                )
            )
        return hydrated


def extract_video_id(video_input: str) -> str:
    value = video_input.strip()
    if not value:
        raise ValueError("Video input is empty")
    if not value.startswith("http"):
        return value

    parsed = urlparse(value)
    if parsed.netloc.endswith("youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id:
            return video_id
    query_video = parse_qs(parsed.query).get("v", [""])[0]
    if query_video:
        return query_video
    if "/shorts/" in parsed.path:
        return parsed.path.split("/shorts/", 1)[1].strip("/").split("/")[0]
    raise ValueError(f"Could not parse YouTube video id: {video_input}")


def extract_playlist_id(playlist_input: str) -> str:
    value = playlist_input.strip()
    if not value:
        raise ValueError("Playlist input is empty")
    if value.startswith("PL") or value.startswith("UU") or value.startswith("OLAK5uy_"):
        return value
    if value.startswith("http"):
        parsed = urlparse(value)
        playlist_id = parse_qs(parsed.query).get("list", [""])[0]
        if playlist_id:
            return playlist_id
    raise ValueError(f"Could not parse YouTube playlist id: {playlist_input}")


def parse_iso8601_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        value,
    )
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _youtube_error_detail(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.reason or ""
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return response.reason or ""
    message = str(error.get("message") or "").strip()
    errors = error.get("errors")
    reason = ""
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            reason = str(first.get("reason") or "").strip()
    if message and reason:
        return f"{reason}: {message}"
    return message or reason or response.reason or ""
