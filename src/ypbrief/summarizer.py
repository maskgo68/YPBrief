from __future__ import annotations

from .config import Settings
from .database import Database
from .llm import SummaryProvider
from .prompts import DatabasePromptService
from .text_normalization import clean_summary_markdown


class Summarizer:
    def __init__(self, db: Database, provider: SummaryProvider, settings: Settings | None = None) -> None:
        self.db = db
        self.provider = provider
        self.settings = settings or Settings()

    def summarize_video(self, video_id: str, output_language: str | None = None) -> int:
        video = self.db.get_video(video_id)
        transcript = video.get("transcript_clean")
        if not transcript:
            raise ValueError(f"Video {video_id} has no cleaned transcript")
        language_instruction = _language_instruction(output_language)

        prompt_version = "v1"
        prompt = _default_video_prompt(video)
        try:
            prompt_service = DatabasePromptService(self.db, self.settings.prompt_file)
            active_prompt = prompt_service.get("video_summary")
            rendered = prompt_service.preview(
                "video_summary",
                {
                    "video_title": video["video_title"],
                    "video_url": video["video_url"],
                    "channel_name": video.get("channel_name") or video.get("channel_id") or "",
                    "video_date": video.get("video_date") or "",
                    "transcript": transcript,
                },
            )
            prompt = rendered["system_prompt"] or prompt
            transcript = rendered["user_prompt"] if rendered["system_prompt"] else transcript
            prompt_version = f"db:{active_prompt.get('version') or 'video_summary'}"
        except KeyError:
            pass
        if language_instruction:
            transcript = f"{transcript.rstrip()}\n\n{language_instruction}"
        content = clean_summary_markdown(self.provider.summarize(prompt, transcript))
        provider_base_url = getattr(self.provider, "base_url", None)
        return self.db.save_summary(
            summary_type="video",
            content_markdown=content,
            provider=self.provider.name,
            model=self.provider.model,
            video_id=video_id,
            channel_id=video["channel_id"],
            provider_base_url=provider_base_url,
            prompt_version=prompt_version,
        )


def _default_video_prompt(video: dict) -> str:
    return (
        "Summarize this YouTube podcast episode in Markdown.\n"
        f"Title: {video['video_title']}\n"
        f"Video URL: {video['video_url']}\n"
        "Include key points, decisions, and useful timestamps when possible."
    )


def _language_instruction(output_language: str | None) -> str:
    language = (output_language or "auto").strip().lower()
    if language in {"", "auto"}:
        return ""
    if language in {"zh", "zh-cn", "chinese"}:
        return "Output language override: write the final summary in Simplified Chinese."
    if language in {"en", "english"}:
        return "Output language override: write the final summary in English."
    raise ValueError("output_language must be auto, zh, or en")
