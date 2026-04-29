from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


PUBLIC_TEMPLATE_FILES = [
    ROOT / "key.env.example",
    ROOT / "prompts.example.yaml",
    ROOT / "sources.example.yaml",
]


SENSITIVE_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-[0-9A-Za-z_-]{20,}"),
    re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"geo\.iproyal\.com", re.IGNORECASE),
]


def test_gitignore_excludes_real_key_env() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "key.env" in gitignore
    assert "!key.env.example" in gitignore
    assert "sources.yaml" in gitignore
    assert "!sources.example.yaml" in gitignore
    assert "prompts.yaml" in gitignore
    assert "!prompts.example.yaml" in gitignore
    assert "actions-exports/" in gitignore
    assert "PRD*.md" in gitignore
    assert "PRD doc/" in gitignore
    assert "findings.md" in gitignore
    assert "progress.md" in gitignore
    assert "task_plan.md" in gitignore
    assert ".envrc" in gitignore
    assert "*.p12" in gitignore
    assert "*.sql" in gitignore
    assert "npm-debug.log*" in gitignore


def test_dockerignore_excludes_local_secrets_runtime_data_and_build_artifacts() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    for pattern in [
        "key.env",
        "!key.env.example",
        ".envrc",
        "sources.yaml",
        "sources.example.yaml",
        "prompts.yaml",
        "prompts.example.yaml",
        "PRD*.md",
        "PRD doc/",
        "findings.md",
        "progress.md",
        "task_plan.md",
        "data/",
        "exports/",
        "actions-exports/",
        "logs/",
        ".ypbrief-actions/",
        "secrets/",
        "*cookies*.txt",
        "*.p12",
        "*.pfx",
        "*.secret",
        "*.db",
        "*.sql",
        "*.tar.gz",
        ".git/",
        ".github/",
        "web/node_modules/",
        "web/dist/",
        "web/.cache/",
        "tests/",
        "scripts/",
        "run.bat",
        "README*.md",
        "docker-compose.yml",
        ".pytest_cache/",
        "__pycache__/",
        "npm-debug.log*",
    ]:
        assert pattern in dockerignore


def test_public_example_files_do_not_contain_known_private_values() -> None:
    for path in PUBLIC_TEMPLATE_FILES:
        text = path.read_text(encoding="utf-8")

        for pattern in SENSITIVE_PATTERNS:
            assert pattern.search(text) is None, f"{path.name} contains sensitive-looking value: {pattern.pattern}"

        assert "PLMUnYee" not in text
        assert "PLSiLS" not in text
        assert "PLc1ZOe" not in text
        assert "PLIyi" not in text
        assert "PLe4PRej" not in text
        assert "PLn5MTSA" not in text


def test_docker_compose_uses_single_published_image_service_and_bind_mounts() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ypbrief:" in compose
    assert "image: supergo6/ypbrief:latest" in compose
    assert "build:" not in compose
    assert "YPBRIEF_ENV_FILE=/app/data/key.env" in compose
    assert "./data:/app/data" in compose
    assert "./exports:/app/exports" in compose
    assert "./logs:/app/logs" in compose
    assert "ypbrief-cli" not in compose
    assert "ypbrief-web" not in compose
    assert "ypbrief-scheduler" not in compose
    assert "uvicorn" in compose
    assert "reserved for" not in compose
    assert "48787:48787" in compose
    assert "SCHEDULER_ENABLED=true" in compose
    assert "volumes:\n  ypbrief-data:" not in compose


def test_dockerfile_builds_frontend_and_serves_fastapi_image() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:" in dockerfile
    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "COPY --from=web-build" in dockerfile
    assert "COPY key.env.example ./key.env.example" in dockerfile
    assert "EXPOSE 48787" in dockerfile
    assert "COPY docker-entrypoint.sh" in dockerfile
    assert 'ENV YPBRIEF_ENV_FILE=/app/data/key.env' in dockerfile
    assert 'ENTRYPOINT ["./docker-entrypoint.sh"]' in dockerfile
    assert '"python", "-m", "uvicorn"' in dockerfile
    assert '"--port", "48787"' in dockerfile


def test_docker_entrypoint_bootstraps_persistent_key_env() -> None:
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert "YPBRIEF_ENV_FILE:=/app/data/key.env" in entrypoint
    assert 'cp /app/key.env.example "$YPBRIEF_ENV_FILE"' in entrypoint
    assert 'YPBRIEF_ACCESS_PASSWORD="$password"' in entrypoint
    assert '"YPBRIEF_DB_PATH": "/app/data/ypbrief.db"' in entrypoint
    assert '"YPBRIEF_EXPORT_DIR": "/app/exports"' in entrypoint
    assert '"YPBRIEF_LOG_DIR": "/app/logs"' in entrypoint
    assert '"SCHEDULER_ENABLED": "true"' in entrypoint
    assert 'exec "$@"' in entrypoint


def test_github_actions_workflow_uses_safe_allowlist() -> None:
    workflow = (ROOT / ".github" / "workflows" / "github-actions-daily.yml").read_text(encoding="utf-8")

    assert "python scripts/github_actions_daily.py" in workflow
    assert "git add -f -- sources.yaml" in workflow
    assert "git add -f -- prompts.yaml" in workflow
    assert "actions-exports/daily/**/*.md" in workflow
    assert "actions-exports/videos/**/summary.md" in workflow
    assert "contents: write" in workflow
    assert "key.env" not in workflow
    assert "source.vtt" not in workflow
    assert "transcript.md" not in workflow
    assert "*.db" not in workflow


def test_key_env_example_lists_required_provider_keys() -> None:
    example = (ROOT / "key.env.example").read_text(encoding="utf-8")

    for key in [
        "YOUTUBE_DATA_API_KEY=",
        "OPENAI_API_KEY=",
        "OPENAI_BASE_URL=",
        "GEMINI_API_KEY=",
        "GEMINI_BASE_URL=",
        "SILICONFLOW_API_KEY=",
        "ANTHROPIC_API_KEY=",
        "ANTHROPIC_BASE_URL=",
        "XAI_API_KEY=",
        "DEEPSEEK_API_KEY=",
        "OPENROUTER_API_KEY=",
        "OPENROUTER_BASE_URL=",
        "CUSTOM_OPENAI_API_KEY=",
        "CUSTOM_OPENAI_BASE_URL=",
        "YPBRIEF_PROMPT_FILE=",
    ]:
        assert key in example

    for model_key in [
        "LLM_MODEL=",
        "OPENAI_MODEL=",
        "GEMINI_MODEL=",
        "SILICONFLOW_MODEL=",
        "CLAUDE_MODEL=",
        "XAI_MODEL=",
        "DEEPSEEK_MODEL=",
        "OPENROUTER_MODEL=",
        "CUSTOM_OPENAI_MODEL=",
    ]:
        assert model_key not in example
