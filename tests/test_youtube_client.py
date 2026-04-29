import requests

from ypbrief.youtube import RequestsHTTPClient, YouTubeDataClient, parse_iso8601_duration


class FakeHTTP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_json(self, url: str, params: dict[str, str]) -> dict:
        self.calls.append((url, params))
        if "channels" in url:
            return {
                "items": [
                    {
                        "id": "UC123",
                        "snippet": {"title": "Test Channel", "customUrl": "@test"},
                        "contentDetails": {
                            "relatedPlaylists": {"uploads": "UU123"}
                        },
                    }
                ]
            }
        if "playlistItems" in url and "pageToken" not in params:
            return {
                "nextPageToken": "next",
                "items": [
                    {
                        "snippet": {
                            "resourceId": {"videoId": "vid1"},
                            "title": "Episode 1",
                            "publishedAt": "2026-04-25T00:00:00Z",
                        }
                    }
                ],
            }
        return {
            "items": [
                {
                    "snippet": {
                        "resourceId": {"videoId": "vid2"},
                        "title": "Episode 2",
                        "publishedAt": "2026-04-26T00:00:00Z",
                    }
                }
            ]
        }


def test_youtube_client_resolves_handle_and_paginates_uploads() -> None:
    http = FakeHTTP()
    client = YouTubeDataClient(api_key="yt-key", http=http)

    channel = client.resolve_channel("@test")
    videos = list(client.iter_uploads(channel.uploads_playlist_id))

    assert channel.channel_id == "UC123"
    assert channel.uploads_playlist_id == "UU123"
    assert [video.video_id for video in videos] == ["vid1", "vid2"]
    assert http.calls[0][1]["forHandle"] == "test"
    assert http.calls[1][1]["playlistId"] == "UU123"
    assert http.calls[2][1]["pageToken"] == "next"


def test_youtube_client_limits_upload_pagination_before_next_page() -> None:
    http = FakeHTTP()
    client = YouTubeDataClient(api_key="yt-key", http=http)

    videos = client.iter_uploads("UU123", limit=1)

    assert [video.video_id for video in videos] == ["vid1"]
    assert [call[0].rsplit("/", 1)[-1] for call in http.calls] == ["playlistItems", "videos"]
    assert "pageToken" not in http.calls[0][1]
    assert http.calls[1][1]["id"] == "vid1"


class PlaylistHTTP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_json(self, url: str, params: dict[str, str]) -> dict:
        self.calls.append((url, params))
        if "playlists" in url:
            return {
                "items": [
                    {
                        "id": "PL123",
                        "snippet": {
                            "title": "Test Playlist",
                            "channelId": "UC123",
                            "channelTitle": "Test Channel",
                        },
                        "contentDetails": {"itemCount": 2},
                    }
                ]
            }
        if "videos" in url:
            return {
                "items": [
                    {
                        "id": "vid1",
                        "snippet": {
                            "title": "Episode 1",
                            "publishedAt": "2026-04-25T00:00:00Z",
                            "channelId": "UC123",
                            "channelTitle": "Test Channel",
                        },
                        "contentDetails": {"duration": "PT1M59S"},
                    }
                ]
            }
        return {
            "items": [
                {
                    "snippet": {
                        "position": 0,
                        "resourceId": {"videoId": "vid1"},
                        "title": "Episode 1",
                        "publishedAt": "2026-04-25T00:00:00Z",
                        "videoOwnerChannelTitle": "Test Channel",
                    }
                }
            ]
        }


def test_youtube_client_reads_playlist_metadata_and_items() -> None:
    http = PlaylistHTTP()
    client = YouTubeDataClient(api_key="yt-key", http=http)

    playlist = client.get_playlist("https://www.youtube.com/playlist?list=PL123")
    videos = client.iter_playlist_items("PL123", limit=1)

    assert playlist.playlist_id == "PL123"
    assert playlist.playlist_name == "Test Playlist"
    assert playlist.channel_name == "Test Channel"
    assert playlist.item_count == 2
    assert [video.video_id for video in videos] == ["vid1"]
    assert [video.duration_seconds for video in videos] == [119]
    assert http.calls[0][1]["id"] == "PL123"
    assert http.calls[1][1]["playlistId"] == "PL123"
    assert http.calls[2][1]["part"] == "snippet,contentDetails"


def test_parse_iso8601_duration_to_seconds() -> None:
    assert parse_iso8601_duration("PT1M59S") == 119
    assert parse_iso8601_duration("PT2M") == 120
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration(None) is None


def test_requests_http_client_sanitizes_youtube_api_key_in_errors(monkeypatch) -> None:
    class Response:
        status_code = 400
        reason = "Bad Request"

        def raise_for_status(self):
            raise requests.HTTPError("400 Client Error: key=secret-key")

        def json(self):
            return {"error": {"message": "Missing playlistId", "errors": [{"reason": "required"}]}}

    def fake_get(url: str, params: dict[str, str], timeout: int):
        assert params["key"] == "secret-key"
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)

    try:
        RequestsHTTPClient().get_json(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            {"part": "snippet", "key": "secret-key"},
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected sanitized RuntimeError")

    assert "playlistItems returned HTTP 400" in message
    assert "required: Missing playlistId" in message
    assert "secret-key" not in message
    assert "googleapis.com" not in message
