from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .database import Database


_VARIABLE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")

DEFAULT_PROMPTS: dict[str, dict[str, Any]] = {
    "video_summary": {
        "prompt_id": 1,
        "prompt_type": "video_summary",
        "prompt_name": "Video Summary Prompt",
        "language": "auto",
        "version": "default",
        "is_active": 1,
        "system_prompt": (
            "You are a professional content research editor. Your job is to turn a video podcast episode into a "
            "high-quality, client-ready summary that is clear, structured, and rich in insights.\n\n"
            "You will receive basic video information, transcript content, and related metadata. Based on these "
            "materials, produce a well-structured summary that highlights the most important information, key "
            "conclusions, and real value of the episode."
        ),
        "user_template": (
            "Follow these requirements strictly:\n"
            "1. The output language must match the video's original primary language. Use English for English videos, "
            "Chinese for Chinese videos, and the video's primary language for other cases.\n"
            "2. Write for clients. Focus on core insights, important viewpoints, concrete data, and practical "
            "value.\n"
            "3. Do not mention any system or processing details.\n"
            "4. Keep the writing professional, precise, and restrained. Avoid fluff, hype, or empty phrases.\n"
            "5. If the transcript is messy or conversational, reorganize it into a clear, logical summary.\n"
            "6. Do not invent information. Only use content supported by the transcript.\n"
            "7. Prioritize conclusions, judgments, data points, timelines, and statements with high reference value.\n"
            "8. If the episode covers multiple topics, focus on the most important and valuable themes.\n\n"
            "Use exactly this structure:\n\n"
            "# Podcast Name\n"
            "{{ channel_name }}\n\n"
            "# Video Title\n"
            "{{ video_title }}\n\n"
            "# Publish Date\n"
            "{{ video_date }}\n\n"
            "# Core Summary\n"
            "Write 2-3 clear sentences that cover:\n"
            "- What this episode is mainly about\n"
            "- The episode's core thesis or main conclusion\n"
            "- The single most important takeaway or value for the audience\n\n"
            "# Key Points\n"
            "List 4-6 bullet points with the most important takeaways.\n"
            "Each point can be 1-2 sentences if needed. Prioritize depth and specificity over extreme brevity.\n"
            "Prioritize points that include data, timelines, clear judgments, or high practical value.\n\n"
            "# Timeline\n"
            "List 3-7 timestamped checkpoints from the episode when reliable timing cues are available from the "
            "transcript.\n"
            "Each item should include:\n"
            "- an approximate timestamp\n"
            "- the topic or segment discussed at that point\n"
            "- a short note on why that moment is useful for review\n"
            "This section is meant to help the reader quickly jump back into the episode.\n"
            "Keep it concise, but do not remove depth from Core Summary, Key Points, or Why It Matters in order to "
            "make room for this section.\n\n"
            "# Why It Matters\n"
            "In 2-4 sentences, explain the broader significance of this episode.\n"
            "Focus on:\n"
            "- Industry, market, policy, or investment implications\n"
            "- Potential downstream impact\n"
            "- Why this matters to investors, decision-makers, or the target audience\n\n"
            "If the implications are limited or uncertain, state that cautiously rather than overstating "
            "significance.\n\n"
            "Make sure the output is information-dense, easy to scan, and suitable for direct use in a daily "
            "digest.\n\n"
            "Here is the source material:\n"
            "- Video URL: {{ video_url }}\n\n"
            "{{ transcript }}"
        ),
        "variables": ["channel_name", "video_date", "video_title", "video_url", "transcript"],
    },
    "daily_digest": {
        "prompt_id": 2,
        "prompt_type": "daily_digest",
        "prompt_name": "Daily Digest Prompt",
        "language": "auto",
        "version": "default",
        "is_active": 1,
        "system_prompt": (
            "You are a professional industry content editor preparing a daily podcast brief for clients.\n\n"
            "You will receive a set of video summaries and related metadata for the day. Your job is not to describe "
            "the workflow. Your job is to help clients quickly understand which podcast sources updated, what the main "
            "topics were, what conclusions mattered most, and which trends deserve continued attention."
        ),
        "user_template": (
            "Follow these requirements strictly:\n"
            "1. The output language must follow the target language for this digest task. If no language is specified, "
            "default to Simplified Chinese.\n"
            "2. Write for clients. The whole digest should focus on information value and distilled conclusions.\n"
            "3. Do not mention any operational or backend details such as failures, skipped videos, transcript "
            "status, model calls, retries, technical implementation, or workflow.\n"
            "4. Start with an overall update overview, then provide an overall synthesis, then individual video "
            "summaries, and finally a forward-looking section on trends to watch.\n"
            "5. The overall synthesis must be cross-video synthesis, not a stitched list of separate summaries.\n"
            "6. Keep the tone professional, concise, and restrained. Avoid repetition, fluff, templated filler, or "
            "hype.\n"
            "7. Prioritize conclusions, changes, trends, judgments, and signals worth continued attention instead of "
            "retelling content at length.\n"
            "8. Individual video summaries should be compact, clear, and easy to scan.\n"
            "9. Do not invent information that is not supported by the source summaries.\n"
            "10. If there are no new videos worth summarizing for the day, produce a short digest that clearly says "
            "there were no new videos worth summarizing today, in a professional natural tone.\n"
            "11. The very first line must be a level-1 title that clearly includes the digest date. Always include "
            "the exact date `{{ run_date }}` in the title.\n"
            "12. Section headings and field labels must use the same language as the digest output. If the target "
            "language is Chinese, use Chinese headings and labels; if it is English, use English headings and labels.\n"
            "13. For each individual video heading, use the provided Source Title exactly as the source identity. "
            "Do not guess, translate, shorten, or replace the source hierarchy.\n\n"
            "Use exactly this structure:\n\n"
            "# Daily Podcast Digest - {{ run_date }}\n"
            "If the output language is Chinese, use `# 每日播客简报 - {{ run_date }}` instead.\n\n"
            "# Daily Update Overview\n"
            "If the output language is Chinese, use `# 每日更新概览` instead.\n"
            "In 2-4 sentences, explain:\n"
            "- how many podcast sources updated today\n"
            "- how many new videos were included in the digest\n"
            "- which themes, directions, or topics dominated today's updates\n\n"
            "# Overall Synthesis\n"
            "If the output language is Chinese, use `# 整体结论` instead.\n"
            "Provide a high-level cross-video synthesis of the day's key conclusions and judgments.\n"
            "Focus on what the situation is right now, what changed, and what clients should understand from today's "
            "updates.\n"
            "Use 3-5 bullet points.\n"
            "Each bullet should contain one clear conclusion or synthesized observation.\n"
            "Do not write this section as one long paragraph.\n\n"
            "Do not focus on future monitoring here.\n\n"
            "# Video-by-Video Summaries\n"
            "If the output language is Chinese, use `# 视频摘要` instead.\n"
            "Use the provided single-video summaries as the primary source.\n"
            "Reformat and condense them into the following structure, sorted by importance (most important first).\n"
            "Keep the original meaning, emphasis, and key insights from the source summaries.\n"
            "Do not introduce new claims or details that are not supported by the provided single-video summaries.\n"
            "Make the language more concise and suitable for daily reading, but do not oversimplify.\n\n"
            "For each video, use exactly this format:\n"
            "## {Source Title}\n"
            "- Publish Date: {Publish Date}\n"
            "- Key Points:\n"
            "  - Point 1 (condensed from the provided summary)\n"
            "  - Point 2\n"
            "  - Point 3\n"
            "- Why It Matters:\n"
            "  Use 1-2 sentences.\n"
            '  This can be adapted from the original "Why It Matters" section in the provided summary, but keep its core meaning intact.\n\n'
            "If the output language is Chinese, use these labels instead: `- 发布日期：`, `- 要点：`, and `- 影响与意义：`.\n\n"
            "# Trends To Watch\n"
            "If the output language is Chinese, use `# 后续关注` instead.\n"
            "Extract 2-4 specific trends, risks, opportunities, or developments worth continued attention in the near "
            "term (next several days to 4 weeks).\n"
            "For each item, clearly state:\n"
            "- What to watch\n"
            "- Why it matters\n"
            "- What concrete signals, events, policy decisions, data releases, or time windows would help verify the direction\n"
            "This section must be forward-looking and additive.\n"
            "Do NOT repeat conclusions already covered in Overall Synthesis.\n"
            "Focus on what happens next and how to verify it, rather than restating today's takeaways.\n"
            "Only mention signals or time windows that are supported by the source material or are a reasonable "
            "near-term extension of it.\n"
            "Do not invent specific dates, catalysts, or thresholds without support.\n"
            "Keep it to 2-4 items maximum and prioritize the most actionable or time-sensitive ones.\n\n"
            "Digest Date: {{ run_date }}\n"
            "Target Output Language: {{ digest_language }}\n\n"
            "{{ summaries }}"
        ),
        "variables": ["digest_language", "run_date", "summaries"],
    },
}


class DatabasePromptService:
    def __init__(self, db: Database, fallback_path: str | Path | None = None) -> None:
        self.db = db
        self.fallback_path = Path(fallback_path) if fallback_path else None

    def ensure_defaults(self) -> None:
        existing = self.db.list_prompt_templates(group_id=None)
        if not existing and self.fallback_path and self.fallback_path.exists():
            self.import_from_file(self.fallback_path)
            existing = self.db.list_prompt_templates(group_id=None)
        by_type = {row["prompt_type"] for row in existing if row.get("group_id") is None}
        for prompt_type, default in DEFAULT_PROMPTS.items():
            if prompt_type not in by_type:
                self.db.create_prompt_template(
                    prompt_type=prompt_type,
                    prompt_name=default["prompt_name"],
                    version=default["version"],
                    language=default["language"],
                    group_id=None,
                    system_prompt=default["system_prompt"],
                    user_template=default["user_template"],
                    variables_json=json.dumps(default["variables"]),
                    is_active=True,
                )

    def list(self, group_id: int | None = -1) -> list[dict[str, Any]]:
        self.ensure_defaults()
        prompts = self.db.list_prompt_templates(group_id=group_id)
        for item in prompts:
            item["variables"] = self._decode_variables(item.get("variables_json"))
        return prompts

    def get(self, prompt_ref: str | int, group_id: int | None = None) -> dict[str, Any]:
        self.ensure_defaults()
        if isinstance(prompt_ref, int) or str(prompt_ref).isdigit():
            prompt = self.db.get_prompt_template(int(prompt_ref))
            prompt["variables"] = self._decode_variables(prompt.get("variables_json"))
            return prompt
        prompt_type = str(prompt_ref).strip()
        candidates = self.db.list_prompt_templates(group_id=group_id if group_id is not None else -1)
        chosen = _select_prompt(candidates, prompt_type=prompt_type, group_id=group_id)
        if chosen is None and group_id is not None:
            chosen = _select_prompt(candidates, prompt_type=prompt_type, group_id=None)
        if chosen is None:
            default = DEFAULT_PROMPTS.get(prompt_type)
            if default is None:
                raise KeyError(prompt_ref)
            return copy.deepcopy(default)
        chosen["variables"] = self._decode_variables(chosen.get("variables_json"))
        return chosen

    def save(
        self,
        *,
        prompt_type: str,
        system_prompt: str,
        user_template: str,
        prompt_name: str | None = None,
        language: str = "auto",
        group_id: int | None = None,
        activate: bool = True,
        notes: str | None = None,
        skip_bootstrap: bool = False,
    ) -> dict[str, Any]:
        if not skip_bootstrap:
            self.ensure_defaults()
        existing = [
            item
            for item in self.db.list_prompt_templates(group_id=group_id)
            if item["prompt_type"] == prompt_type and item.get("group_id") == group_id
        ]
        version = f"v{len(existing) + 1}"
        default = DEFAULT_PROMPTS.get(prompt_type)
        saved = self.db.create_prompt_template(
            prompt_type=prompt_type,
            prompt_name=prompt_name or (default["prompt_name"] if default else prompt_type),
            version=version,
            language=language,
            group_id=group_id,
            system_prompt=system_prompt,
            user_template=user_template,
            variables_json=json.dumps(sorted(_template_variables(user_template))),
            is_active=activate,
            notes=notes,
        )
        saved["variables"] = self._decode_variables(saved.get("variables_json"))
        return saved

    def activate(self, prompt_id: int) -> dict[str, Any]:
        prompt = self.db.activate_prompt_template(prompt_id)
        prompt["variables"] = self._decode_variables(prompt.get("variables_json"))
        return prompt

    def reset_defaults(self) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for prompt_type, default in DEFAULT_PROMPTS.items():
            created.append(
                self.save(
                    prompt_type=prompt_type,
                    prompt_name=default["prompt_name"],
                    language=default["language"],
                    system_prompt=default["system_prompt"],
                    user_template=default["user_template"],
                    activate=True,
                )
            )
        return created

    def preview(self, prompt_ref: str | int, values: dict[str, Any], group_id: int | None = None) -> dict[str, str]:
        prompt = self.get(prompt_ref, group_id=group_id)
        system_prompt = _render(prompt.get("system_prompt") or "", values)
        user_prompt = _render(prompt["user_template"], values)
        return {"system_prompt": system_prompt, "user_prompt": user_prompt}

    def export_payload(self) -> dict[str, Any]:
        self.ensure_defaults()
        groups: dict[str, dict[str, Any]] = {}
        for prompt in self.list(group_id=-1):
            variables = prompt.get("variables") or self._decode_variables(prompt.get("variables_json"))
            record = {
                "prompt_name": prompt["prompt_name"],
                "language": prompt["language"],
                "system_prompt": prompt.get("system_prompt") or "",
                "user_template": prompt["user_template"],
                "variables": variables,
            }
            group_name = prompt.get("group_name")
            if group_name:
                groups.setdefault(group_name, {})[prompt["prompt_type"]] = record
            else:
                groups.setdefault("__global__", {})[prompt["prompt_type"]] = record
        payload: dict[str, Any] = {"prompts": {"global": groups.pop("__global__", {})}}
        if groups:
            payload["prompts"]["groups"] = groups
        return payload

    def save_to_file(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml.safe_dump(self.export_payload(), allow_unicode=True, sort_keys=False), encoding="utf-8")
        return output_path

    def import_from_file(self, path: str | Path) -> int:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        imported = 0
        prompt_root = payload.get("prompts")
        if prompt_root is None:
            prompt_root = {
                "global": {
                    key: value
                    for key, value in payload.items()
                    if key in DEFAULT_PROMPTS
                }
            }
        global_prompts = prompt_root.get("global", {})
        for prompt_type, value in global_prompts.items():
            self.save(
                prompt_type=prompt_type,
                prompt_name=value.get("prompt_name") or DEFAULT_PROMPTS[prompt_type]["prompt_name"],
                language=value.get("language") or DEFAULT_PROMPTS[prompt_type]["language"],
                system_prompt=value.get("system_prompt") or "",
                user_template=value.get("user_template") or DEFAULT_PROMPTS[prompt_type]["user_template"],
                group_id=None,
                activate=True,
                skip_bootstrap=True,
            )
            imported += 1
        for group_name, prompts in (prompt_root.get("groups") or {}).items():
            group_id = _group_id_by_name(self.db, group_name)
            if group_id is None:
                continue
            for prompt_type, value in prompts.items():
                self.save(
                    prompt_type=prompt_type,
                    prompt_name=value.get("prompt_name") or DEFAULT_PROMPTS[prompt_type]["prompt_name"],
                    language=value.get("language") or DEFAULT_PROMPTS[prompt_type]["language"],
                    system_prompt=value.get("system_prompt") or "",
                    user_template=value.get("user_template") or DEFAULT_PROMPTS[prompt_type]["user_template"],
                    group_id=group_id,
                    activate=True,
                    skip_bootstrap=True,
                )
                imported += 1
        return imported

    @staticmethod
    def _decode_variables(raw: str | list[str] | None) -> list[str]:
        if isinstance(raw, list):
            return raw
        if not raw:
            return []
        return list(json.loads(raw))


class PromptFileService:
    def __init__(self, path: str | Path = "prompts.yaml") -> None:
        self.path = Path(path)

    def list(self) -> list[dict[str, Any]]:
        prompts = self._load_legacy()
        return [copy.deepcopy(prompts[key]) for key in sorted(prompts, key=lambda item: prompts[item]["prompt_id"])]

    def get(self, prompt_ref: str | int) -> dict[str, Any]:
        key = self._resolve_key(prompt_ref)
        return copy.deepcopy(self._load_legacy()[key])

    def save(self, prompt_type: str, system_prompt: str, user_template: str) -> dict[str, Any]:
        prompts = self._load_legacy()
        key = self._resolve_key(prompt_type)
        prompt = prompts[key]
        prompt["system_prompt"] = system_prompt
        prompt["user_template"] = user_template
        prompt["variables"] = sorted(_template_variables(user_template))
        self._write_legacy(prompts)
        return copy.deepcopy(prompt)

    def reset_defaults(self) -> list[dict[str, Any]]:
        prompts = copy.deepcopy(DEFAULT_PROMPTS)
        self._write_legacy(prompts)
        return [copy.deepcopy(prompts[key]) for key in sorted(prompts, key=lambda item: prompts[item]["prompt_id"])]

    def preview(self, prompt_ref: str | int, values: dict[str, Any]) -> dict[str, str]:
        prompt = self.get(prompt_ref)
        system_prompt = _render(prompt.get("system_prompt") or "", values)
        user_prompt = _render(prompt["user_template"], values)
        return {"system_prompt": system_prompt, "user_prompt": user_prompt}

    def _load_legacy(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            prompts = copy.deepcopy(DEFAULT_PROMPTS)
            self._write_legacy(prompts)
            return prompts
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        prompt_root = raw.get("prompts", {}).get("global") if isinstance(raw.get("prompts"), dict) else raw
        prompts: dict[str, dict[str, Any]] = {}
        for key, default_prompt in DEFAULT_PROMPTS.items():
            current = (prompt_root or {}).get(key) or {}
            prompts[key] = {
                **copy.deepcopy(default_prompt),
                **current,
                "prompt_type": key,
                "prompt_id": default_prompt["prompt_id"],
                "variables": current.get("variables")
                or sorted(_template_variables(current.get("user_template") or default_prompt["user_template"])),
            }
        return prompts

    def _write_legacy(self, prompts: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        output: dict[str, Any] = {}
        for key in sorted(prompts, key=lambda item: prompts[item]["prompt_id"]):
            prompt = prompts[key]
            output[key] = {
                "prompt_name": prompt["prompt_name"],
                "language": prompt["language"],
                "system_prompt": prompt["system_prompt"],
                "user_template": prompt["user_template"],
                "variables": prompt["variables"],
            }
        self.path.write_text(yaml.safe_dump(output, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _resolve_key(self, prompt_ref: str | int) -> str:
        prompts = self._load_legacy()
        if isinstance(prompt_ref, int):
            for key, prompt in prompts.items():
                if prompt["prompt_id"] == prompt_ref:
                    return key
            raise KeyError(prompt_ref)
        text = str(prompt_ref).strip()
        if text in prompts:
            return text
        if text.isdigit():
            return self._resolve_key(int(text))
        raise KeyError(prompt_ref)


def _select_prompt(candidates: list[dict[str, Any]], *, prompt_type: str, group_id: int | None) -> dict[str, Any] | None:
    scoped = [
        item for item in candidates
        if item["prompt_type"] == prompt_type and item.get("group_id") == group_id
    ]
    active = [item for item in scoped if item.get("is_active")]
    if active:
        return sorted(active, key=lambda item: item["prompt_id"], reverse=True)[0]
    if scoped:
        return sorted(scoped, key=lambda item: item["prompt_id"], reverse=True)[0]
    return None


def _group_id_by_name(db: Database, group_name: str) -> int | None:
    name = group_name.strip()
    if not name:
        return None
    for group in db.list_source_groups():
        if group["group_name"] == name:
            return int(group["group_id"])
    return None


def _render(template: str, values: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise ValueError(f"Missing prompt variable: {name}")
        return str(values[name])

    return _VARIABLE.sub(replace, template)


def _template_variables(template: str) -> set[str]:
    return set(_VARIABLE.findall(template))
