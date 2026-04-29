from ypbrief.cleaner import TranscriptSegment, clean_transcript


def test_clean_transcript_merges_nearby_segments_and_removes_fillers() -> None:
    segments = [
        TranscriptSegment(start=0.0, duration=1.0, text="嗯 hello   there"),
        TranscriptSegment(start=2.0, duration=1.0, text="like this is   useful"),
        TranscriptSegment(start=8.0, duration=2.0, text="那个 final point"),
    ]

    result = clean_transcript(segments, merge_gap_seconds=2.5)

    assert result.text == "hello there this is useful\nfinal point"
    assert len(result.segments) == 2
    assert result.segments[0].start == 0.0
    assert result.segments[0].duration == 3.0
    assert result.segments[0].text == "hello there this is useful"
    assert result.segments[1].text == "final point"


def test_clean_transcript_drops_empty_segments_after_cleaning() -> None:
    segments = [
        TranscriptSegment(start=0.0, duration=1.0, text="嗯 啊 um like"),
        TranscriptSegment(start=5.0, duration=1.0, text="real content"),
    ]

    result = clean_transcript(segments)

    assert result.text == "real content"
    assert len(result.segments) == 1
    assert result.segments[0].start == 5.0


def test_clean_transcript_decodes_html_entities() -> None:
    segments = [
        TranscriptSegment(start=0.0, duration=1.0, text="Goldman&nbsp;Sachs &amp; markets"),
    ]

    result = clean_transcript(segments)

    assert result.text == "Goldman Sachs & markets"
