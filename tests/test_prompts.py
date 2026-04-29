from pathlib import Path

from ypbrief.prompts import PromptFileService


def test_prompt_file_service_loads_defaults_and_persists_updates(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompts.yaml"
    service = PromptFileService(prompt_file)

    prompts = service.list()
    updated = service.save(
        "daily_digest",
        system_prompt="系统提示词",
        user_template="日报 {{ summaries }} {{ run_date }} {{ digest_language }}",
    )
    reloaded = PromptFileService(prompt_file).get("daily_digest")

    assert len(prompts) == 2
    assert prompts[0]["prompt_type"] == "video_summary"
    assert updated["system_prompt"] == "系统提示词"
    assert reloaded["user_template"] == "日报 {{ summaries }} {{ run_date }} {{ digest_language }}"
    assert prompt_file.exists()


def test_daily_digest_default_prompt_separates_current_synthesis_and_forward_watch(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompts.yaml"
    service = PromptFileService(prompt_file)

    daily = service.get("daily_digest")

    assert "what the situation is right now" in daily["user_template"]
    assert "What to watch" in daily["user_template"]
    assert "how to verify it" in daily["user_template"]
    assert "Use the provided single-video summaries as the primary source" in daily["user_template"]
    assert "Do not introduce new claims or details" in daily["user_template"]


def test_video_summary_default_prompt_emphasizes_core_summary_and_decision_value(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompts.yaml"
    service = PromptFileService(prompt_file)

    video = service.get("video_summary")

    assert "Write 2-3 clear sentences" in video["user_template"]
    assert "List 4-6 bullet points" in video["user_template"]
    assert "Each point can be 1-2 sentences if needed" in video["user_template"]
    assert "# Timeline" in video["user_template"]
    assert "List 3-7 timestamped checkpoints" in video["user_template"]
    assert "Why this matters to investors, decision-makers, or the target audience" in video["user_template"]
    assert "If the implications are limited or uncertain" in video["user_template"]


def test_prompt_file_service_preview_rejects_unknown_variable(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompts.yaml"
    service = PromptFileService(prompt_file)
    service.save(
        "video_summary",
        system_prompt="",
        user_template="Summarize {{ transcript }} and {{ missing }}.",
    )

    try:
        service.preview("video_summary", {"transcript": "hello"})
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected unknown variable to fail")
