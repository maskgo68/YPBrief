from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    duration: float
    text: str

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class CleanTranscript:
    text: str
    segments: list[TranscriptSegment]


DEFAULT_FILLERS = {
    "um",
    "uh",
    "erm",
    "ah",
    "like",
    "you know",
    "i mean",
    "嗯",
    "啊",
    "呃",
    "额",
    "那个",
    "这个",
    "就是",
}


def _clean_text(text: str, fillers: set[str]) -> str:
    cleaned = html.unescape(text).replace("\xa0", " ")
    for phrase in sorted(fillers, key=len, reverse=True):
        if re.search(r"[A-Za-z]", phrase):
            cleaned = re.sub(rf"\b{re.escape(phrase)}\b", " ", cleaned, flags=re.IGNORECASE)
        else:
            cleaned = cleaned.replace(phrase, " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.!?;:，。！？；：])", r"\1", cleaned)
    return cleaned.strip(" \t\r\n,，.。")


def clean_transcript(
    segments: list[TranscriptSegment],
    merge_gap_seconds: float = 2.5,
    filler_words: set[str] | None = None,
) -> CleanTranscript:
    fillers = filler_words or DEFAULT_FILLERS
    cleaned_segments = [
        TranscriptSegment(segment.start, segment.duration, text)
        for segment in segments
        if (text := _clean_text(segment.text, fillers))
    ]

    merged: list[TranscriptSegment] = []
    for segment in cleaned_segments:
        if not merged:
            merged.append(segment)
            continue

        previous = merged[-1]
        gap = segment.start - previous.end
        if gap <= merge_gap_seconds:
            end = max(previous.end, segment.end)
            merged[-1] = TranscriptSegment(
                start=previous.start,
                duration=end - previous.start,
                text=f"{previous.text} {segment.text}".strip(),
            )
        else:
            merged.append(segment)

    return CleanTranscript(
        text="\n".join(segment.text for segment in merged),
        segments=merged,
    )
