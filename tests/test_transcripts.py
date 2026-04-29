import sys
import types
from pathlib import Path
import builtins

from ypbrief.cleaner import TranscriptSegment
from ypbrief.config import Settings
from ypbrief.transcripts import (
    TranscriptFetchError,
    TranscriptFetchResult,
    TranscriptFetcher,
    _fetch_with_yt_dlp_language_attempt,
    _extract_direct_caption_languages,
    parse_youtube_vtt_text,
    preferred_subtitle_languages,
    select_yt_dlp_language,
    subtitle_language_attempts,
    fetch_with_yt_dlp,
)


def test_transcript_fetcher_uses_primary_source_first() -> None:
    fetcher = TranscriptFetcher(
        primary=lambda video_id, languages: [
            TranscriptSegment(start=0.0, duration=1.0, text=f"primary {video_id}")
        ],
        fallback=lambda video_id, languages: [
            TranscriptSegment(start=0.0, duration=1.0, text="fallback")
        ],
    )

    result = fetcher.fetch("abc123", languages=["en"])

    assert result.source == "primary"
    assert result.segments[0].text == "primary abc123"


def test_transcript_fetcher_defaults_to_yt_dlp_only() -> None:
    calls = []

    def ytdlp(video_id: str, languages: list[str]) -> list[TranscriptSegment]:
        calls.append("yt-dlp")
        return [TranscriptSegment(start=0.0, duration=1.0, text="yt-dlp text")]

    fetcher = TranscriptFetcher(backends=[("yt-dlp", ytdlp)])

    result = fetcher.fetch("abc123", languages=["en"])

    assert result.source == "yt-dlp"
    assert result.segments[0].text == "yt-dlp text"
    assert calls == ["yt-dlp"]


def test_transcript_fetcher_preserves_backend_source_vtt() -> None:
    def ytdlp(video_id: str, languages: list[str]) -> TranscriptFetchResult:
        return TranscriptFetchResult(
            source="yt-dlp",
            source_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nyt-dlp text\n",
            segments=[TranscriptSegment(start=0.0, duration=1.0, text="yt-dlp text")],
        )

    fetcher = TranscriptFetcher(backends=[("yt-dlp", ytdlp)])

    result = fetcher.fetch("abc123", languages=["en"])

    assert result.source == "yt-dlp"
    assert result.source_vtt is not None
    assert result.source_vtt.startswith("WEBVTT")


def test_transcript_fetcher_uses_fallback_when_primary_fails() -> None:
    def fail_primary(video_id: str, languages: list[str]) -> list[TranscriptSegment]:
        raise TranscriptFetchError("primary failed")

    fetcher = TranscriptFetcher(
        primary=fail_primary,
        fallback=lambda video_id, languages: [
            TranscriptSegment(start=5.0, duration=2.0, text="fallback text")
        ],
    )

    result = fetcher.fetch("abc123", languages=["en"])

    assert result.source == "fallback"
    assert result.segments[0].text == "fallback text"


def test_preferred_subtitle_languages_match_video_language_first() -> None:
    assert preferred_subtitle_languages("en")[:3] == ["en-US", "en", "en-GB"]
    assert preferred_subtitle_languages("zh")[:3] == ["zh-Hans", "zh-Hant", "zh"]
    assert preferred_subtitle_languages("zh-Hant")[:3] == ["zh-Hant", "zh", "zh-Hans"]


def test_subtitle_language_attempts_try_single_languages_in_priority_order() -> None:
    assert subtitle_language_attempts(["en-US", "en", "en-GB"]) == [
        ["en-US"],
        ["en"],
        ["en-GB"],
    ]


def test_extract_direct_caption_languages_ignores_translation_only_entries() -> None:
    info = {
        "subtitles": {
            "en": [{"ext": "vtt", "url": "https://example.com/en.vtt"}],
        },
        "automatic_captions": {
            "hi": [{"ext": "vtt", "url": "https://example.com/hi.vtt"}],
            "ab": [{"ext": "vtt", "url": "https://example.com/ab.vtt?tlang=ab"}],
            "zh-Hans": [{"ext": "vtt", "url": "https://example.com/zh.vtt?tlang=zh-Hans"}],
        },
    }

    assert _extract_direct_caption_languages(info) == ["en", "hi"]


def test_select_yt_dlp_language_prefers_matching_direct_caption_language() -> None:
    assert select_yt_dlp_language(["en-US", "en", "en-GB"], ["en", "hi"]) == "en"


def test_select_yt_dlp_language_falls_back_to_first_direct_caption_language() -> None:
    assert select_yt_dlp_language(["en-US", "en", "en-GB"], ["hi"]) == "hi"


def test_fetch_with_yt_dlp_falls_back_to_any_available_subtitles(monkeypatch) -> None:
    attempts: list[list[str]] = []

    def fake_attempt(**kwargs):
        languages = kwargs["languages"]
        attempts.append(languages)
        if languages == ["hi"]:
            return TranscriptFetchResult(
                source="yt-dlp",
                source_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nfallback\n",
                segments=[TranscriptSegment(start=0.0, duration=1.0, text="fallback")],
            )
        raise TranscriptFetchError(f"missing {'/'.join(languages)}")

    monkeypatch.setattr("ypbrief.transcripts._fetch_with_yt_dlp_language_attempt", fake_attempt)
    monkeypatch.setattr("ypbrief.transcripts._discover_yt_dlp_direct_caption_languages", lambda *args, **kwargs: ["hi"])

    result = fetch_with_yt_dlp(
        video_id="abc123",
        languages=["en-US", "en"],
        cookies_file="",
        cookies_from_browser="",
        proxy="",
        sleep_interval=0,
        max_sleep_interval=0,
        retries=0,
    )

    assert attempts == [["hi"]]
    assert result.segments[0].text == "fallback"


def test_fetch_with_yt_dlp_uses_legacy_language_attempts_only_when_direct_languages_are_unavailable(monkeypatch) -> None:
    attempts: list[list[str]] = []

    def fake_attempt(**kwargs):
        languages = kwargs["languages"]
        attempts.append(languages)
        if languages == ["en"]:
            return TranscriptFetchResult(
                source="yt-dlp",
                source_vtt="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nenglish\n",
                segments=[TranscriptSegment(start=0.0, duration=1.0, text="english")],
            )
        raise TranscriptFetchError(f"missing {'/'.join(languages)}")

    monkeypatch.setattr("ypbrief.transcripts._fetch_with_yt_dlp_language_attempt", fake_attempt)
    monkeypatch.setattr("ypbrief.transcripts._discover_yt_dlp_direct_caption_languages", lambda *args, **kwargs: [])

    result = fetch_with_yt_dlp(
        video_id="abc123",
        languages=["en-US", "en"],
        cookies_file="",
        cookies_from_browser="",
        proxy="",
        sleep_interval=0,
        max_sleep_interval=0,
        retries=0,
    )

    assert attempts == [["en-US"], ["en"]]
    assert result.segments[0].text == "english"


def test_yt_dlp_language_attempt_does_not_depend_on_outer_import_scope(tmp_path) -> None:
    try:
        _fetch_with_yt_dlp_language_attempt(
            video_id="missing",
            video_url="https://www.youtube.com/watch?v=missing",
            languages=["en"],
            cookies_file="",
            cookies_from_browser="",
            proxy="",
            sleep_interval=0,
            max_sleep_interval=0,
            retries=0,
        )
    except TranscriptFetchError as exc:
        assert "yt_dlp" not in str(exc)


def test_yt_dlp_language_attempt_returns_downloaded_vtt_text(monkeypatch) -> None:
    vtt_text = """WEBVTT

00:00:00.000 --> 00:00:01.000
hello world
"""

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, video_url: str, download: bool):
            output_dir = Path(self.options["outtmpl"]).parent
            (output_dir / "abc123.en.vtt").write_text(vtt_text, encoding="utf-8")
            return {"id": "abc123"}

    fake_yt_dlp = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_yt_dlp)

    result = _fetch_with_yt_dlp_language_attempt(
        video_id="abc123",
        video_url="https://www.youtube.com/watch?v=abc123",
        languages=["en"],
        cookies_file="",
        cookies_from_browser="",
        proxy="",
        sleep_interval=0,
        max_sleep_interval=0,
        retries=0,
    )

    assert result.source_vtt == vtt_text
    assert result.segments[0].text == "hello world"


def test_transcript_fetcher_can_be_configured_from_settings() -> None:
    settings = Settings(
        youtube_proxy_enabled="true",
        iproyal_proxy_host="geo.iproyal.com",
        iproyal_proxy_port="12321",
        iproyal_proxy_username="user",
        iproyal_proxy_password="pass",
        yt_dlp_cookies_file="./secrets/youtube-cookies.txt",
        yt_dlp_sleep_interval="3",
        yt_dlp_max_sleep_interval="9",
        yt_dlp_retries="4",
    ).with_base_dir(__import__("pathlib").Path("D:/project"))

    fetcher = TranscriptFetcher.from_settings(settings)

    assert fetcher.proxy_http == "http://user:pass@geo.iproyal.com:12321"
    assert fetcher.proxy_https == "http://user:pass@geo.iproyal.com:12321"
    assert fetcher.yt_dlp_cookies_file.endswith("secrets\\youtube-cookies.txt") or fetcher.yt_dlp_cookies_file.endswith("secrets/youtube-cookies.txt")
    assert fetcher.yt_dlp_sleep_interval == 3
    assert fetcher.yt_dlp_max_sleep_interval == 9
    assert fetcher.yt_dlp_retries == 4


def test_transcript_fetcher_default_backend_passes_yt_dlp_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_fetch(video_id: str, languages: list[str], **kwargs: object) -> TranscriptFetchResult:
        captured.update(kwargs)
        return TranscriptFetchResult(
            source="yt-dlp",
            segments=[TranscriptSegment(start=0.0, duration=1.0, text=f"text {video_id}")],
            source_vtt="WEBVTT",
        )

    monkeypatch.setattr("ypbrief.transcripts.fetch_with_yt_dlp", fake_fetch)
    fetcher = TranscriptFetcher(
        yt_dlp_cookies_file="cookies.txt",
        yt_dlp_cookies_from_browser="chrome",
        yt_dlp_proxy="http://proxy.example.test:8080",
        yt_dlp_sleep_interval=3,
        yt_dlp_max_sleep_interval=9,
        yt_dlp_retries=4,
    )

    result = fetcher.fetch("abc123", languages=["en"])

    assert result.segments[0].text == "text abc123"
    assert captured == {
        "cookies_file": "cookies.txt",
        "cookies_from_browser": "chrome",
        "proxy": "http://proxy.example.test:8080",
        "sleep_interval": 3,
        "max_sleep_interval": 9,
        "retries": 4,
    }


def test_transcript_fetcher_default_backend_uses_http_proxy_fallback(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_fetch(video_id: str, languages: list[str], **kwargs: object) -> TranscriptFetchResult:
        captured.update(kwargs)
        return TranscriptFetchResult(
            source="yt-dlp",
            segments=[TranscriptSegment(start=0.0, duration=1.0, text="text")],
        )

    monkeypatch.setattr("ypbrief.transcripts.fetch_with_yt_dlp", fake_fetch)
    TranscriptFetcher(proxy_https="http://https-proxy.example.test:8080").fetch("abc123", languages=["en"])

    assert captured["proxy"] == "http://https-proxy.example.test:8080"


def test_yt_dlp_backend_import_errors_reference_current_extra(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yt_dlp":
            raise ImportError("missing yt_dlp")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    for action in (
        lambda: fetch_with_yt_dlp("abc123", ["en"]),
        lambda: _fetch_with_yt_dlp_language_attempt(
            video_id="abc123",
            video_url="https://www.youtube.com/watch?v=abc123",
            languages=["en"],
            cookies_file="",
            cookies_from_browser="",
            proxy="",
            sleep_interval=0,
            max_sleep_interval=0,
            retries=0,
        ),
    ):
        try:
            action()
        except TranscriptFetchError as exc:
            assert "ypbrief[transcripts]" in str(exc)
            legacy_extra = "ypbrief[" + "fallback]"
            assert legacy_extra not in str(exc)
        else:
            raise AssertionError("expected TranscriptFetchError when yt_dlp is unavailable")


def test_parse_youtube_vtt_text_keeps_only_rolling_caption_increments() -> None:
    vtt_text = """WEBVTT

00:00:00.320 --> 00:00:02.230 align:start position:0%
Markets<00:00:00.840><c> have</c><00:00:01.000><c> entered</c>

00:00:02.230 --> 00:00:02.240 align:start position:0%
Markets have entered

00:00:02.240 --> 00:00:04.670 align:start position:0%
Markets have entered
environment.<00:00:03.320><c> Inflation</c><00:00:04.000><c> is</c>

00:00:04.670 --> 00:00:04.680 align:start position:0%
environment. Inflation is

00:00:04.680 --> 00:00:06.750 align:start position:0%
environment. Inflation is
anchored<00:00:05.240><c> where</c><00:00:05.360><c> it</c><00:00:05.480><c> once</c><00:00:05.720><c> was.</c>
"""

    segments = parse_youtube_vtt_text(vtt_text)

    assert [segment.text for segment in segments] == [
        "Markets have entered",
        "environment. Inflation is",
        "anchored where it once was.",
    ]
