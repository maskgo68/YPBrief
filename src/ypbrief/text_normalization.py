from __future__ import annotations

import re


_BULLET_LINE_RE = re.compile(r"(?m)^([ \t]*)＊(?=\s+)")
_NUMERIC_RANGE_RE = re.compile(r"(?<=\d)\s*每\s*(?=\d)")


def clean_summary_markdown(text: str) -> str:
    if not text:
        return text

    cleaned = _BULLET_LINE_RE.sub(r"\1*", text)
    cleaned = _NUMERIC_RANGE_RE.sub("-", cleaned)
    cleaned = cleaned.replace("※", '"')
    cleaned = cleaned.replace("〞", '"')
    return cleaned
