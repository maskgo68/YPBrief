from pathlib import Path

from ypbrief.cleaner import TranscriptSegment
from ypbrief.config import Settings
from ypbrief.database import Database
from ypbrief.prompts import PromptFileService
from ypbrief.summarizer import Summarizer


class FakeProvider:
    name = "openai"
    model = "fake-model"
    base_url = "https://example.test/v1"

    def summarize(self, prompt: str, transcript: str) -> str:
        assert "正式单视频提示词" in prompt
        assert "hello world" in transcript
        return "# Summary\n\n- Useful episode."


class PromptCapturingProvider:
    name = "openai"
    model = "fake-model"
    base_url = "https://example.test/v1"

    def __init__(self, content: str) -> None:
        self.content = content
        self.last_prompt = ""
        self.last_transcript = ""

    def summarize(self, prompt: str, transcript: str) -> str:
        self.last_prompt = prompt
        self.last_transcript = transcript
        return self.content


def test_summarizer_saves_video_summary(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Test Channel", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1")
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )

    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "video_summary",
        system_prompt="正式单视频提示词",
        user_template="标题：{{ video_title }}\n正文：{{ transcript }}",
    )

    summary_id = Summarizer(
        db=db,
        provider=FakeProvider(),
        settings=Settings(prompt_file=prompt_file),
    ).summarize_video("vid1")

    summary = db.get_summary(summary_id)
    video = db.get_video("vid1")

    assert summary["content_markdown"].startswith("# Summary")
    assert summary["provider_base_url"] == "https://example.test/v1"
    assert video["status"] == "summarized"


def test_summarizer_uses_human_readable_channel_name_in_prompt(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Readable Podcast", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1")
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )

    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "video_summary",
        system_prompt="正式单视频提示词",
        user_template="Podcast={{ channel_name }}\nTranscript={{ transcript }}",
    )
    provider = PromptCapturingProvider("# Summary")

    Summarizer(
        db=db,
        provider=provider,
        settings=Settings(prompt_file=prompt_file),
    ).summarize_video("vid1")

    assert "Readable Podcast" in provider.last_transcript
    assert "UC123" not in provider.last_transcript


def test_summarizer_can_override_video_summary_language(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Readable Podcast", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1")
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )

    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "video_summary",
        system_prompt="正式单视频提示词",
        user_template="正文：{{ transcript }}",
    )
    provider = PromptCapturingProvider("# Summary")

    Summarizer(
        db=db,
        provider=provider,
        settings=Settings(prompt_file=prompt_file),
    ).summarize_video("vid1", output_language="zh")

    assert "Output language override: write the final summary in Simplified Chinese." in provider.last_transcript


def test_summarizer_cleans_common_llm_artifacts_before_saving(tmp_path: Path) -> None:
    db = Database(tmp_path / "ypbrief.db")
    db.initialize()
    db.upsert_channel("UC123", "Readable Podcast", "https://youtube.com/channel/UC123")
    db.upsert_video("vid1", "UC123", "Episode 1", "https://youtu.be/vid1")
    db.save_transcript(
        video_id="vid1",
        raw_json="[]",
        clean_text="hello world",
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
    )

    prompt_file = tmp_path / "prompts.yaml"
    PromptFileService(prompt_file).save(
        "video_summary",
        system_prompt="正式单视频提示词",
        user_template="正文：{{ transcript }}",
    )
    provider = PromptCapturingProvider("# Summary\n\n＊ point 1\n※quoted〞\nrange 50每80%")

    summary_id = Summarizer(
        db=db,
        provider=provider,
        settings=Settings(prompt_file=prompt_file),
    ).summarize_video("vid1")

    summary = db.get_summary(summary_id)

    assert "* point 1" in summary["content_markdown"]
    assert "※" not in summary["content_markdown"]
    assert "〞" not in summary["content_markdown"]
    assert "50-80%" in summary["content_markdown"]
