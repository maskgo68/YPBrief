from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
from typing import Callable
from urllib.parse import parse_qs, urlparse

from .cleaner import TranscriptSegment
from .config import Settings


class TranscriptFetchError(RuntimeError):
    pass


YT_DLP_DEPENDENCY_MESSAGE = "Install ypbrief[transcripts] to use yt-dlp transcript fetching"


@dataclass(frozen=True)
class TranscriptFetchResult:
    source: str
    segments: list[TranscriptSegment]
    source_vtt: str | None = None


TranscriptSource = Callable[[str, list[str]], list[TranscriptSegment] | TranscriptFetchResult]
TranscriptBackend = tuple[str, TranscriptSource]


class TranscriptFetcher:
    def __init__(
        self,
        primary: TranscriptSource | None = None,
        fallback: TranscriptSource | None = None,
        backends: list[TranscriptBackend] | None = None,
        proxy_http: str = "",
        proxy_https: str = "",
        yt_dlp_cookies_file: str = "",
        yt_dlp_cookies_from_browser: str = "",
        yt_dlp_proxy: str = "",
        yt_dlp_sleep_interval: int = 2,
        yt_dlp_max_sleep_interval: int = 8,
        yt_dlp_retries: int = 3,
    ) -> None:
        if backends is not None:
            self.backends = backends
        elif primary is not None or fallback is not None:
            self.backends = []
            if primary is not None:
                self.backends.append(("primary", primary))
            if fallback is not None:
                self.backends.append(("fallback", fallback))
        else:
            proxy = yt_dlp_proxy or proxy_https or proxy_http

            def ytdlp_backend(video_id: str, languages: list[str]) -> TranscriptFetchResult:
                return fetch_with_yt_dlp(
                    video_id,
                    languages,
                    cookies_file=yt_dlp_cookies_file,
                    cookies_from_browser=yt_dlp_cookies_from_browser,
                    proxy=proxy,
                    sleep_interval=yt_dlp_sleep_interval,
                    max_sleep_interval=yt_dlp_max_sleep_interval,
                    retries=yt_dlp_retries,
                )

            self.backends = [("yt-dlp", ytdlp_backend)]
        self.proxy_http = proxy_http
        self.proxy_https = proxy_https
        self.yt_dlp_cookies_file = yt_dlp_cookies_file
        self.yt_dlp_cookies_from_browser = yt_dlp_cookies_from_browser
        self.yt_dlp_proxy = yt_dlp_proxy
        self.yt_dlp_sleep_interval = yt_dlp_sleep_interval
        self.yt_dlp_max_sleep_interval = yt_dlp_max_sleep_interval
        self.yt_dlp_retries = yt_dlp_retries

    @classmethod
    def from_settings(cls, settings: Settings) -> "TranscriptFetcher":
        proxy_url = settings.youtube_proxy_url
        yt_dlp_proxy = settings.yt_dlp_proxy_url

        def ytdlp_backend(video_id: str, languages: list[str]) -> TranscriptFetchResult:
            return fetch_with_yt_dlp(
                video_id,
                languages,
                cookies_file=str(settings.yt_dlp_cookies_file),
                cookies_from_browser=settings.yt_dlp_cookies_from_browser,
                proxy=yt_dlp_proxy,
                sleep_interval=int(settings.yt_dlp_sleep_interval),
                max_sleep_interval=int(settings.yt_dlp_max_sleep_interval),
                retries=int(settings.yt_dlp_retries),
            )

        return cls(
            backends=[("yt-dlp", ytdlp_backend)],
            proxy_http=settings.youtube_proxy_http or proxy_url,
            proxy_https=settings.youtube_proxy_https or proxy_url,
            yt_dlp_cookies_file=str(settings.yt_dlp_cookies_file),
            yt_dlp_cookies_from_browser=settings.yt_dlp_cookies_from_browser,
            yt_dlp_proxy=yt_dlp_proxy,
            yt_dlp_sleep_interval=int(settings.yt_dlp_sleep_interval),
            yt_dlp_max_sleep_interval=int(settings.yt_dlp_max_sleep_interval),
            yt_dlp_retries=int(settings.yt_dlp_retries),
        )

    def fetch(self, video_id: str, languages: list[str] | None = None) -> TranscriptFetchResult:
        preferred_languages = languages or preferred_subtitle_languages("en")
        errors: list[str] = []
        for name, backend in self.backends:
            try:
                result = backend(video_id, preferred_languages)
                if isinstance(result, TranscriptFetchResult):
                    return TranscriptFetchResult(
                        source=name,
                        segments=result.segments,
                        source_vtt=result.source_vtt,
                    )
                return TranscriptFetchResult(source=name, segments=result)
            except Exception as exc:
                errors.append(f"{name}={exc}")
        raise TranscriptFetchError(f"Could not fetch transcript for {video_id}: " + "; ".join(errors))


def preferred_subtitle_languages(video_language: str | None) -> list[str]:
    normalized = (video_language or "en").strip()
    if normalized in {"zh-Hant", "zh-TW", "zh-HK"}:
        return ["zh-Hant", "zh", "zh-Hans"]
    if normalized.startswith("zh"):
        return ["zh-Hans", "zh-Hant", "zh"]
    if normalized in {"en-US", "en"}:
        return ["en-US", "en", "en-GB"]
    if normalized.startswith("en-"):
        return [normalized, "en", "en-US", "en-GB"]
    return [normalized]


def subtitle_language_attempts(languages: list[str]) -> list[list[str]]:
    seen: set[str] = set()
    attempts: list[list[str]] = []
    for language in languages:
        if language in seen:
            continue
        seen.add(language)
        attempts.append([language])
    return attempts


def select_yt_dlp_language(languages: list[str], direct_caption_languages: list[str] | None = None) -> str | None:
    direct_languages = _dedupe_languages(direct_caption_languages or [])
    if not direct_languages:
        return None

    direct_set = set(direct_languages)
    for language in languages:
        if language in direct_set:
            return language
    return direct_languages[0]


def _dedupe_languages(languages: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for language in languages:
        if language in seen:
            continue
        seen.add(language)
        ordered.append(language)
    return ordered


def fetch_with_yt_dlp(
    video_id: str,
    languages: list[str],
    cookies_file: str = "",
    cookies_from_browser: str = "",
    proxy: str = "",
    sleep_interval: int = 2,
    max_sleep_interval: int = 8,
    retries: int = 3,
) -> TranscriptFetchResult:
    try:
        import yt_dlp
    except ImportError as exc:
        raise TranscriptFetchError(YT_DLP_DEPENDENCY_MESSAGE) from exc

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        direct_caption_languages = _discover_yt_dlp_direct_caption_languages(
            video_url=video_url,
            cookies_file=cookies_file,
            cookies_from_browser=cookies_from_browser,
            proxy=proxy,
        )
    except Exception:
        direct_caption_languages = []
    selected_language = select_yt_dlp_language(languages, direct_caption_languages)
    errors: list[str] = []
    if selected_language:
        try:
            return _fetch_with_yt_dlp_language_attempt(
                video_id=video_id,
                video_url=video_url,
                languages=[selected_language],
                cookies_file=cookies_file,
                cookies_from_browser=cookies_from_browser,
                proxy=proxy,
                sleep_interval=sleep_interval,
                max_sleep_interval=max_sleep_interval,
                retries=retries,
            )
        except Exception as exc:
            errors.append(f"{selected_language}={exc}")
            raise TranscriptFetchError(f"yt-dlp could not fetch subtitles for {video_id}: " + "; ".join(errors))

    for language_attempt in subtitle_language_attempts(languages):
        try:
            return _fetch_with_yt_dlp_language_attempt(
                video_id=video_id,
                video_url=video_url,
                languages=language_attempt,
                cookies_file=cookies_file,
                cookies_from_browser=cookies_from_browser,
                proxy=proxy,
                sleep_interval=sleep_interval,
                max_sleep_interval=max_sleep_interval,
                retries=retries,
            )
        except Exception as exc:
            errors.append(f"{'/'.join(language_attempt)}={exc}")
    raise TranscriptFetchError(f"yt-dlp could not fetch subtitles for {video_id}: " + "; ".join(errors))


def _discover_yt_dlp_direct_caption_languages(
    video_url: str,
    cookies_file: str,
    cookies_from_browser: str,
    proxy: str,
) -> list[str]:
    try:
        import yt_dlp
    except ImportError as exc:
        raise TranscriptFetchError(YT_DLP_DEPENDENCY_MESSAGE) from exc

    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
    }
    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies_file and Path(cookies_file).exists():
        ydl_opts["cookiefile"] = cookies_file
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
    return _extract_direct_caption_languages(info)


def _extract_direct_caption_languages(info: dict) -> list[str]:
    languages: list[str] = []
    seen: set[str] = set()
    for field in ("subtitles", "automatic_captions"):
        entries = info.get(field) or {}
        for language, formats in entries.items():
            if language in seen:
                continue
            if any(_is_direct_caption_format(item) for item in (formats or [])):
                seen.add(language)
                languages.append(language)
    return languages


def _is_direct_caption_format(item: dict) -> bool:
    tlang = item.get("tlang")
    if tlang:
        return False
    url = item.get("url") or ""
    query = parse_qs(urlparse(url).query)
    return "tlang" not in query


def _fetch_with_yt_dlp_language_attempt(
    video_id: str,
    video_url: str,
    languages: list[str],
    cookies_file: str,
    cookies_from_browser: str,
    proxy: str,
    sleep_interval: int,
    max_sleep_interval: int,
    retries: int,
) -> TranscriptFetchResult:
    try:
        import yt_dlp
    except ImportError as exc:
        raise TranscriptFetchError(YT_DLP_DEPENDENCY_MESSAGE) from exc

    with tempfile.TemporaryDirectory() as tmp_dir:
        ydl_opts = {
            "outtmpl": str(Path(tmp_dir) / "%(id)s"),
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "vtt",
            "subtitleslangs": [*languages, "-live_chat"],
            "writeinfojson": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "sleep_interval": sleep_interval,
            "max_sleep_interval": max_sleep_interval,
            "retries": retries,
            "fragment_retries": retries,
        }
        if proxy:
            ydl_opts["proxy"] = proxy
        if cookies_file and Path(cookies_file).exists():
            ydl_opts["cookiefile"] = cookies_file
        if cookies_from_browser:
            ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(video_url, download=True)
        except Exception as exc:
            raise TranscriptFetchError(str(exc)) from exc

        vtt_files = sorted(Path(tmp_dir).glob(f"{video_id}*.vtt"))
        if not vtt_files:
            raise TranscriptFetchError(f"yt-dlp did not download VTT subtitles for {video_id}")

        selected_vtt = _select_vtt_file(vtt_files, languages)
        source_vtt = selected_vtt.read_text(encoding="utf-8", errors="ignore")
        segments = parse_youtube_vtt_text(source_vtt)
        if not segments:
            raise TranscriptFetchError(f"yt-dlp downloaded empty subtitles for {video_id}")
        return TranscriptFetchResult(source="yt-dlp", segments=segments, source_vtt=source_vtt)


def _select_vtt_file(vtt_files: list[Path], languages: list[str]) -> Path:
    language_rank = {language: index for index, language in enumerate(languages)}

    def rank(path: Path) -> tuple[int, str]:
        name = path.name
        for language, index in language_rank.items():
            if f".{language}." in name or name.endswith(f".{language}.vtt"):
                return (index, name)
        return (len(language_rank), name)

    return sorted(vtt_files, key=rank)[0]


def parse_youtube_vtt_text(vtt_text: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    previous_visible_text = ""
    previous_incremental_text = ""
    for block in re.split(r"\n\s*\n", vtt_text.replace("\r\n", "\n")):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue

        timing_line = lines[timing_index]
        text_lines = lines[timing_index + 1 :]
        if not text_lines:
            continue

        start_seconds, end_seconds = _parse_vtt_timing(timing_line)
        visible_text = _normalize_vtt_caption_text(" ".join(text_lines))
        if not visible_text:
            continue

        incremental_text = _caption_increment(previous_visible_text, visible_text)
        previous_visible_text = visible_text
        if not incremental_text or incremental_text == previous_incremental_text:
            continue
        previous_incremental_text = incremental_text
        segments.append(
            TranscriptSegment(
                start=start_seconds,
                duration=max(0.0, end_seconds - start_seconds),
                text=incremental_text,
            )
        )
    return segments


def _parse_vtt_timing(timing_line: str) -> tuple[float, float]:
    start, rest = timing_line.split("-->", 1)
    end = rest.strip().split()[0]
    return _timestamp_to_seconds(start.strip()), _timestamp_to_seconds(end.strip())


def _timestamp_to_seconds(timestamp: str) -> float:
    parts = timestamp.split(":")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def _normalize_vtt_caption_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _caption_increment(previous_text: str, current_text: str) -> str:
    if not previous_text:
        return current_text
    if current_text == previous_text:
        return ""
    if current_text.startswith(previous_text):
        return current_text[len(previous_text) :].strip()
    return current_text
