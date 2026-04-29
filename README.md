# YPBrief

YouTube Podcast Brief.

YPBrief is a self-hosted scheduled podcast digest runner for people who monitor recurring YouTube sources.

It watches your configured YouTube channels and playlists, collects metadata and subtitles, generates single-video summaries, combines new updates into readable daily or scheduled briefs, and delivers them through Telegram or Email. The Web UI is designed as a practical operator console for source management, prompt tuning, manual runs, scheduled jobs, reading, export, and troubleshooting.

YPBrief is not a general knowledge base, video player, or automation canvas. Its main purpose is simple: turn recurring long-form YouTube sources into traceable, repeatable, human-readable briefs.

## Who It Is For

YPBrief is useful when you regularly monitor YouTube podcasts, interviews, research channels, market commentary, product talks, or expert discussions, and want the important updates summarized without checking every source manually.

Typical users include:

- investors and analysts monitoring market commentary
- researchers following domain experts and long-form interviews
- operators who need daily or weekly source updates
- content teams tracking specific channels or playlists
- individuals who want a private self-hosted digest workflow

The product is strongest when your sources are recurring and structured: a fixed set of channels, playlists, or topic groups that should be checked repeatedly.

## What It Does

Core workflow:

```text
YouTube channels / playlists / videos
-> YouTube Data API metadata
-> yt-dlp subtitle download
-> cleaned transcript
-> single-video summary
-> daily or scheduled digest
-> Telegram / Email / Web UI
```

Main features:

- Manage YouTube channels, playlists, and single-video sources.
- Bulk import sources from pasted text or `.txt` files, with duplicate detection.
- Organize sources into groups such as investing, technology, healthcare, or research.
- Generate one-off summaries for a single YouTube URL from the Dashboard.
- Generate manual digests for selected sources, selected groups, rolling windows, custom date ranges, or all history.
- Create scheduled jobs with their own source scope, language, time window, run time, and delivery channels.
- Preserve same-day repeated digest runs as separate history entries.
- Reuse already processed transcripts and single-video summaries when generating later digests.
- Store original VTT subtitles, cleaned transcripts, single-video summaries, digest summaries, run records, and delivery logs locally.
- Copy or download both summaries and transcripts from the video detail page.
- Browse videos chronologically or grouped by channel.
- Edit prompts for single-video summaries and daily digests.
- Configure multiple LLM providers and switch active models from the Web UI.
- Send digests through Telegram and Email.
- Use an optional Telegram Bot Inbox for authorized one-link video summarization.
- Protect the Web UI with a single access password and rotate it from Settings.

## Product Boundaries

YPBrief deliberately focuses on scheduled digest generation.

It is not meant to replace Notion, Airtable, Obsidian, Readwise, n8n, or a full knowledge base. Those tools are better for long-term note management, tagging, database views, flexible automation, and knowledge retrieval. YPBrief keeps a database and local archive so that the digest pipeline is reproducible and debuggable, but the primary output is still the brief.

Compared with a generic automation workflow, YPBrief packages the recurring YouTube digest use case into one dedicated system: sources, groups, prompts, transcripts, summaries, run history, scheduled jobs, delivery, and maintenance views are all part of the same workflow.

## Architecture

YPBrief is built as a small self-hosted web application:

- Backend: `FastAPI`
- Frontend: `React + Vite`
- Database: `SQLite + FTS5`
- Scheduler: `APScheduler`
- Subtitle backend: `yt-dlp`
- LLM layer: provider adapters for multiple model services
- Delivery: Telegram Bot API and SMTP Email
- Deployment: local Python, Docker/VPS, or GitHub Actions Lite

Runtime behavior:

- YouTube Data API is used for channel, playlist, video metadata, and duration lookup.
- `yt-dlp` is used for subtitle discovery and VTT download.
- Subtitle selection prefers the video's primary language, then common English/Chinese subtitle tracks, then falls back to any available original caption track.
- Videos with known duration of 300 seconds or less are skipped to avoid Shorts, trailers, and low-information clips.
- Markdown is the main human-readable export format.
- SQLite stores structured runtime state, including sources, groups, videos, transcripts, summaries, digest runs, scheduled jobs, settings, and delivery logs.

## Project Structure

```text
src/ypbrief/                         Core backend services and domain logic
src/ypbrief_api/app.py               FastAPI server, API routes, auth, scheduler wiring, and Web UI static hosting
web/                                 React + Vite frontend source
tests/                               Automated backend, API, deployment, and Actions Lite tests
.github/workflows/github-actions-daily.yml
                                     GitHub Actions Lite workflow
scripts/github_actions_daily.py      GitHub Actions Lite runner script
scripts/tee_run.py                   Local helper used by run.bat logging
Dockerfile                           Production Docker image definition
docker-entrypoint.sh                 Container first-boot configuration bootstrap
docker-compose.yml                   Optional single-service Compose deployment
run.bat                              Windows local launcher
pyproject.toml                       Python package metadata and dependencies
key.env.example                      Public configuration template copied by Docker first boot
prompts.example.yaml                 Prompt template example for reference/import
sources.example.yaml                 Source/group import example
.gitignore                           Public repository safety rules
.dockerignore                        Docker build context safety rules
```

Repository-only or local-only directories:

```text
actions-exports/   GitHub Actions Lite Markdown outputs; private fork/local only
data/              SQLite database, runtime state, and Docker key.env; local/VPS only
exports/           VTT, transcript, video summary, and digest archive; local/VPS only
logs/              Runtime logs; local/VPS only
PRD doc/           Internal planning docs; not part of public release or Docker image
Project Evaluation/
                   Internal evaluation notes; not part of public release or Docker image
web/node_modules/  Local frontend dependencies; rebuildable
web/dist/          Built frontend output; generated locally or inside Docker build
```

Important backend modules:

- `config.py`: reads `key.env` and environment variables, resolves paths, proxy settings, provider keys, delivery settings, and runtime defaults.
- `database.py`: owns SQLite schema creation, migrations, and persistence helpers for sources, videos, transcripts, summaries, runs, jobs, settings, providers, prompts, and delivery logs.
- `youtube.py`: wraps YouTube Data API metadata discovery for videos, channels, playlists, publication dates, and durations.
- `sources.py`: manages source creation, source groups, YAML import/export, bulk add, duplicate handling, and channel/playlist/video source normalization.
- `transcripts.py`: fetches subtitle metadata and VTT files through `yt-dlp`, applying language fallback, cookies, and proxy settings.
- `cleaner.py`: cleans subtitle segments into readable transcript text.
- `video_processor.py`: orchestrates single-video metadata lookup, subtitle fetch, transcript cleaning, summary generation, status updates, and export.
- `summarizer.py`: generates single-video summaries using rendered prompts and configured LLM providers.
- `daily.py`: builds manual, scheduled, and Actions Lite digest inputs from video summaries; handles date windows, reuse, retry, digest generation, and daily Markdown export.
- `scheduler.py`: manages scheduled jobs, run-now execution, APScheduler integration, run history, and per-job delivery behavior.
- `delivery.py`: sends Telegram and Email messages, splits long Telegram messages, masks sensitive values, and records delivery logs.
- `prompts.py`: manages default prompts, database-backed prompts, group-specific prompts, active prompt lookup, preview, import/export, and legacy YAML prompt compatibility.
- `provider_config.py`: resolves active model/provider configuration from SQLite first and `key.env` fallback second.
- `llm.py`: contains provider adapters for OpenAI-compatible APIs, Gemini, Claude, Grok/xAI, DeepSeek, SiliconFlow, OpenRouter, and custom providers.
- `exporter.py`: writes transcript, summary, metadata, and server-side export artifacts.
- `archive.py`: writes digest archive files while preventing same-day overwrite.
- `text_normalization.py`: contains light output cleanup helpers.
- `cli.py`: provides command-line operations for local/scripted use.

API and deployment entry points:

- `src/ypbrief_api/app.py`: creates the FastAPI app, registers API routes, serves the built Web UI, enforces auth, wires background scheduler startup, and coordinates settings updates back to `key.env`.
- `.github/workflows/github-actions-daily.yml`: GitHub Actions Lite workflow for scheduled/manual no-server digest runs.
- `scripts/github_actions_daily.py`: one-shot Actions Lite runner that creates a temporary `key.env` and SQLite database, imports `sources.yaml`, calls shared core services, prunes non-retained artifacts, prints delivery results, and leaves only allowed Markdown outputs.
- `Dockerfile`: builds the frontend in a Node stage, then packages the Python backend, built Web UI, and `key.env.example` into a slim runtime image.
- `docker-entrypoint.sh`: creates `/app/data/key.env` on first boot, fills Docker runtime paths, generates the initial access password, then starts Uvicorn.
- `run.bat`: Windows local launcher for backend and frontend development/runtime.

Frontend entry points:

- `web/src/App.tsx`: main React application, including Dashboard, Sources, Videos, Daily Digests, Prompts, Automation, Settings, auth flow, and UI state.
- `web/src/api.ts`: API client helper with bearer-token handling and compact error extraction for JSON and HTML proxy errors.
- `web/src/types.ts`: shared frontend data types matching API payloads.
- `web/src/main.tsx`: React application bootstrap.
- `web/src/App.css`: application styling.
- `web/public/`: favicon and icon assets.

Test coverage is organized by subsystem:

- `tests/test_api.py`: FastAPI routes and Web UI/API integration behavior.
- `tests/test_github_actions_daily.py`: Actions Lite config parsing, allowlist behavior, cleanup, dry-run, and delivery logging.
- `tests/test_deployment_artifacts.py`: repository and deployment safety expectations.
- `tests/test_daily.py`, `tests/test_scheduler.py`-related coverage in API tests: digest and automation behavior.
- Other `tests/test_*.py` files cover config, sources, transcripts, prompts, providers, delivery, exporter, CLI, and YouTube helpers.

## Runtime Data

YPBrief keeps your working data outside the application code:

```text
data/             SQLite database, runtime state, and Docker key.env
exports/          VTT files, cleaned transcripts, video summaries, and digest exports
actions-exports/  GitHub Actions Lite retained Markdown outputs
logs/             runtime logs
key.env           local secrets and configuration for non-Docker local runs
sources.yaml      local/private source snapshot; public repos should use sources.example.yaml
prompts.yaml      local/private prompt snapshot; public repos should use prompts.example.yaml
```

The most important file is the SQLite database:

```text
data/ypbrief.db
```

It stores sources, groups, videos, transcripts, summaries, digest runs, scheduled jobs, delivery logs, model settings, prompts, and other runtime state.

Runtime source of truth differs by mode:

- Local and Docker/VPS: SQLite is the source of truth. `sources.yaml` and `prompts.yaml` are import/export snapshots, not the live database.
- GitHub Actions Lite: `sources.yaml` in the private fork is the source configuration for each run. The SQLite database is temporary and discarded after the workflow.
- Docker first boot: the image contains only `key.env.example`; the real `key.env` is generated in the mounted `data/` directory.

## Publication Rules

YPBrief supports three running modes, but they do not share the same upload rules.

| File or directory | Public GitHub source repo | Docker image/build context | Private GitHub Actions fork | Local / VPS runtime |
| --- | --- | --- | --- | --- |
| `src/`, `web/`, `Dockerfile`, `docker-entrypoint.sh`, `pyproject.toml` | yes | yes | yes | yes |
| `.github/workflows/`, `scripts/github_actions_daily.py`, tests | yes | no | yes | optional |
| `key.env.example` | yes | yes | yes | template only |
| `sources.example.yaml`, `prompts.example.yaml` | yes | no | yes | import/reference only |
| `sources.yaml`, `prompts.yaml` | no | no | allowed in private fork | local snapshot only |
| `actions-exports/` | no | no | allowed in private fork | Actions output only |
| `data/`, `exports/`, `logs/`, `key.env` | no | no | no | yes |
| databases, cookies, API keys, proxy credentials, Telegram/SMTP credentials | no | no | Secrets only | yes |
| `PRD doc/`, `Project Evaluation/` | no | no | no | internal docs only |
| `web/node_modules/`, `web/dist/`, caches | no | no | no | rebuildable local files |

The public repository should be a clean product source package: code, examples, tests, Docker files, GitHub Actions workflow, and documentation. It should not include private source lists, generated summaries, local databases, runtime exports, or credentials.

The Docker image is stricter than the public repository. It only needs the backend package, the built frontend, `key.env.example`, and the container entrypoint. GitHub Actions files, tests, helper scripts, source examples, prompt examples, README, internal docs, and runtime outputs are deliberately excluded from `.dockerignore`.

GitHub Actions Lite is the exception: in your own private fork, `sources.yaml` and generated Markdown under `actions-exports/` may be committed if you accept that everyone with access to that private repository can read them. Keep `key.env`, SQLite databases, VTT subtitles, full transcripts, logs, and credentials out of the fork.

## Requirements

- Python `>= 3.10`
- Node.js `>= 20` if you want local frontend development
- Docker if you prefer container deployment
- A YouTube Data API key
- At least one LLM provider API key
- Optional proxy or cookies if your server has unstable YouTube subtitle access

The YouTube Data API has a generous free quota for metadata lookup. For personal or small-team use, YouTube API usage is usually free. Proxy is disabled by default and is only needed if your server IP has poor YouTube access quality, such as frequent subtitle throttling, blocking, or anti-bot errors. If your VPS or local network can access YouTube subtitles reliably, do not configure a proxy.

## Configuration

YPBrief uses a shared configuration model across local and Docker deployments:

- SQLite is the runtime source of truth for sources, groups, prompts, models, summaries, runs, and scheduled jobs.
- `key.env` stores secrets and startup fallback values.
- Settings saved in the Web UI are written back to the runtime configuration where applicable and applied immediately.

Minimum settings:

```env
YOUTUBE_DATA_API_KEY=

LLM_PROVIDER=gemini
GEMINI_API_KEY=

YPBRIEF_ACCESS_PASSWORD=
```

Model names are intentionally omitted from the default env template. Add `LLM_MODEL` or a provider-specific `*_MODEL` field manually, or configure models in the Web UI.

### YouTube Data API

To get a YouTube Data API key:

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable `YouTube Data API v3`.
4. Create an API key under `APIs & Services -> Credentials`.
5. Put the key in `YOUTUBE_DATA_API_KEY`.

YPBrief uses this key for metadata, channel, playlist, and duration lookup. It does not use the YouTube API to play videos.

### Proxy

Proxy is disabled by default. Only enable it when subtitle access is unstable in your environment, usually because the server IP is rate-limited, blocked, or otherwise has poor YouTube access quality.

The proxy configuration is not tied to one provider. Any standard HTTP/HTTPS proxy can be used through the generic proxy URL settings:

```env
YOUTUBE_PROXY_ENABLED=true
YOUTUBE_PROXY_HTTP=http://username:password@host:port
YOUTUBE_PROXY_HTTPS=http://username:password@host:port
YT_DLP_PROXY=http://username:password@host:port
```

`YOUTUBE_PROXY_HTTP` / `YOUTUBE_PROXY_HTTPS` are used by Python metadata and subtitle helper requests. `YT_DLP_PROXY` is passed directly to `yt-dlp` for subtitle discovery and download. In most deployments, using the same HTTP proxy URL for all three is enough.

YPBrief also supports an IPRoyal-style split configuration as a convenience:

```env
YOUTUBE_PROXY_ENABLED=true
IPROYAL_PROXY_HOST=geo.iproyal.com
IPROYAL_PROXY_PORT=12321
IPROYAL_PROXY_USERNAME=your_username
IPROYAL_PROXY_PASSWORD=your_password
```

Those `IPROYAL_PROXY_*` fields simply build the same kind of proxy URL internally. If another proxy provider gives you host, port, username, and password, prefer the generic `YOUTUBE_PROXY_HTTP`, `YOUTUBE_PROXY_HTTPS`, and `YT_DLP_PROXY` fields unless you intentionally want to reuse the split fields. For maximum compatibility, use HTTP/HTTPS proxy URLs; SOCKS proxy support depends on the underlying Python and `yt-dlp` environment.

If you do not need a proxy:

```env
YOUTUBE_PROXY_ENABLED=false
```

### LLM Providers

YPBrief supports OpenAI, Gemini, Claude, SiliconFlow, OpenRouter, Grok/xAI, DeepSeek, and custom OpenAI-compatible providers.

The usual setup pattern is:

1. Add the provider API key.
2. Set the default provider and model.
3. Start the app.
4. Adjust active provider/model later from the Web UI.

Provider endpoint URLs include stable defaults where possible. Model names are intentionally not hardcoded as product defaults because provider model catalogs change quickly; configure `LLM_MODEL` or the provider-specific `*_MODEL` field before running summaries.

### Delivery

Telegram and Email delivery are optional.

Telegram requires:

- bot token
- chat ID
- optional allowlist/webhook settings for inbound Telegram Bot Inbox

Email requires:

- SMTP host and port
- SMTP username and password
- sender address
- recipient addresses

You can leave delivery disabled while testing the summarization pipeline.

## Local Installation

Create and activate a Python environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -e ".[transcripts,llm,dev]"
```

Create local configuration:

```bash
copy key.env.example key.env
```

Initialize the database:

```bash
ypbrief --env-file key.env init-db
```

Start on Windows:

```bash
run.bat
```

Default local URLs:

```text
API:    http://127.0.0.1:48787
Web UI: http://127.0.0.1:45173
```

Manual backend start:

```bash
python -m uvicorn ypbrief_api.app:app --host 127.0.0.1 --port 48787
```

Manual frontend dev server:

```bash
cd web
npm install
npm run dev -- --host 127.0.0.1 --port 45173 --strictPort
```

## Docker Deployment

Recommended VPS deployment:

```bash
docker run -d \
  --name ypbrief \
  --restart unless-stopped \
  -p 48787:48787 \
  -v /root/ypbrief/data:/app/data \
  -v /root/ypbrief/exports:/app/exports \
  -v /root/ypbrief/logs:/app/logs \
  supergo6/ypbrief:latest
```

On first boot, the container creates `/root/ypbrief/data/key.env` from the bundled template and generates an initial random `YPBRIEF_ACCESS_PASSWORD`.

View the initial password:

```bash
docker logs ypbrief
```

Or filter only the password line:

```bash
docker logs ypbrief 2>&1 | grep YPBRIEF_ACCESS_PASSWORD
```

Then open:

```text
http://YOUR_SERVER_IP:48787
```

You can also place YPBrief behind your own reverse proxy or access gateway.

### Docker Compose

An optional Compose file is included:

```bash
docker compose up -d
```

It maps local `./data`, `./exports`, and `./logs` directories into the container.

## GitHub Actions Lite

GitHub Actions Lite is YPBrief's no-server mode for users who only want a scheduled brief and do not need the Web UI.

This is one of the main deployment options:

- no VPS
- no always-on backend
- no Web UI
- scheduled or manually triggered GitHub Actions runs
- Markdown output committed back to a private fork
- Telegram or Email delivery after each run

It is not a replacement for the Docker/VPS version. It is a lighter mode for fixed-source scheduled digests. Each run starts from the repository configuration, creates a temporary database, generates the brief, sends delivery, keeps only selected Markdown outputs, and then exits:

```text
schedule / manual Run workflow
-> checkout repo
-> install Python dependencies
-> create temporary key.env from GitHub Secrets
-> import sources.yaml into a temporary SQLite database
-> fetch YouTube metadata and subtitles
-> generate single-video summaries
-> generate the daily digest
-> send Telegram / Email
-> commit Markdown outputs
```

What this mode is good for:

- personal daily YouTube podcast briefs without renting a VPS
- private scheduled monitoring of a small fixed source list
- low-maintenance "run once per day and send me the digest" workflows
- testing YPBrief before moving to the full Docker/VPS deployment

What has been verified:

- manual workflow runs can process fixed sources from `sources.yaml`
- `all_time` plus `max_videos_per_source` can be used for smoke testing recent historical videos
- generated daily Markdown is saved under `actions-exports/daily/`
- single-video summaries are saved under `actions-exports/videos/**/summary.md`
- Telegram delivery works when `TELEGRAM_CHAT_ID` points to a chat the bot can access
- proxy configuration is often necessary on GitHub-hosted runners because their IPs may be rate-limited or challenged by YouTube subtitle access

Use Docker/VPS instead if you need:

- Web UI source management
- long-term SQLite history
- full transcript and VTT archive
- maintenance views and manual retry tools
- multiple scheduled jobs managed from the browser
- future Skill/MCP service mode

Recommended privacy model:

- Keep the upstream project public if desired.
- Fork it into your own private repository for real use.
- Store API keys and tokens in GitHub Secrets.
- Store ordinary defaults in GitHub Variables.
- Store sources in `sources.yaml` inside the private fork.
- Commit only digest Markdown and single-video `summary.md` outputs.

The default repository ignore rules are conservative for Docker/VPS use: real runtime files such as `sources.yaml`, `prompts.yaml`, `exports/`, `actions-exports/`, databases, logs, and secrets are protected from accidental public commits. The Actions workflow uses an explicit private-fork allowlist and force-adds only the intended files: `sources.yaml`, optional `prompts.yaml`, daily digest Markdown, and single-video `summary.md`.

### GitHub Actions Setup

1. Fork the project into a private repository.
2. Copy `sources.example.yaml` to `sources.yaml` inside that private fork and edit your real channels/playlists there.
3. In `Settings -> Secrets and variables -> Actions`, add the required Secrets.

Required Secrets:

```text
YOUTUBE_DATA_API_KEY
LLM_PROVIDER
LLM_MODEL
GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY / ...
```

Use the API key that matches your selected `LLM_PROVIDER`. For example, `LLM_PROVIDER=grok` should be paired with `XAI_API_KEY`; `LLM_PROVIDER=gemini` should be paired with `GEMINI_API_KEY`.

Required for Telegram delivery:

```text
TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Recommended for GitHub-hosted runners when subtitle fetching is unstable:

```text
YOUTUBE_PROXY_ENABLED
YOUTUBE_PROXY_HTTP
YOUTUBE_PROXY_HTTPS
YT_DLP_PROXY
```

Optional for Email delivery:

```text
EMAIL_ENABLED
SMTP_HOST
SMTP_USERNAME
SMTP_PASSWORD
EMAIL_FROM
EMAIL_TO
```

Proxy secrets are optional in principle, but strongly recommended for GitHub Actions if subtitle fetching fails or is inconsistent. You can either use the generic proxy URL secrets above, or the split provider fields:

```text
IPROYAL_PROXY_HOST
IPROYAL_PROXY_PORT
IPROYAL_PROXY_USERNAME
IPROYAL_PROXY_PASSWORD
```

The split fields are named for IPRoyal because that was the first tested provider, but they only compose a normal HTTP proxy URL. Other proxy providers are also fine when configured through the generic `YOUTUBE_PROXY_HTTP`, `YOUTUBE_PROXY_HTTPS`, and `YT_DLP_PROXY` secrets.

Minimal private `sources.yaml` example:

```yaml
groups:
  - group_name: technology
    display_name: Technology
    enabled: true
    digest_title: Technology Daily Digest
    digest_language: zh
    run_time: "07:00"
    timezone: Asia/Shanghai
    max_videos_per_source: 2

sources:
  - type: channel
    name: All-In Podcast
    display_name: All-In Podcast
    url: https://www.youtube.com/@allin
    enabled: true
    group: technology
```

4. Add optional Variables for non-secret defaults:

```text
YPBRIEF_ACTIONS_TIMEZONE=Asia/Shanghai
YPBRIEF_ACTIONS_WINDOW=last_1
YPBRIEF_ACTIONS_GROUP=all
YPBRIEF_ACTIONS_LANGUAGE=zh
YPBRIEF_ACTIONS_MAX_VIDEOS_PER_SOURCE=10
```

5. Open `Actions -> YPBrief Daily -> Run workflow` for a manual test.
6. Keep the repository private if `sources.yaml` or generated summaries should remain private.

Useful manual test inputs:

```text
window=last_3
group=all
language=zh
max_videos_per_source=1
dry_run=false
```

For a stronger end-to-end test against recent historical content:

```text
window=all_time
group=all
language=zh
max_videos_per_source=2
dry_run=false
```

The workflow file is `.github/workflows/github-actions-daily.yml`, and the runner script is `scripts/github_actions_daily.py`.

For a local smoke test before pushing to GitHub, run the script with your local env file:

```bash
python scripts/github_actions_daily.py --env-file key.env --dry-run --window last_7 --max-videos-per-source 3
```

`--env-file key.env` is only a local testing convenience. In GitHub Actions, credentials still come from Secrets and the workflow creates a temporary `key.env` during the run. `--dry-run` skips Telegram/Email delivery and git commit, but it still calls YouTube and the configured LLM.

GitHub Actions Lite writes its retained Markdown outputs to `actions-exports/`, not the normal Docker/VPS `exports/` directory. This keeps local smoke tests and private-fork Actions artifacts separate from the full Web UI archive.

Delivery troubleshooting:

- If the run says `delivery telegram success`, the bot API accepted the message.
- If Telegram returns `Bad Request: chat not found`, the most common causes are a wrong `TELEGRAM_CHAT_ID`, the user has not sent `/start` to the bot, the bot is not in the target group, or the bot is not an admin in the target channel.
- If `included=0` and no digest content arrives, check whether the selected `window` actually contains new videos. Use `last_3`, `last_7`, or `all_time` with a small `max_videos_per_source` for testing.
- GitHub schedule times are UTC and not exact to the minute; manual `Run workflow` is the best way to test configuration.

GitHub Actions Lite should not commit:

- `key.env`
- SQLite databases
- VTT subtitle files
- full transcripts
- metadata files
- logs
- cookies
- provider keys or delivery credentials

This mode is best for fixed-source daily digests. Use Docker/VPS if you need the Web UI, long-term SQLite history, maintenance views, full transcript archive, or future Skill/MCP service mode.

## Docker Backup And Migration

The Docker image does not contain your history. Your persistent state is stored in the mounted host directory:

```text
/root/ypbrief/data/      SQLite database and key.env
/root/ypbrief/exports/   VTT, transcripts, summaries, and digest exports
/root/ypbrief/logs/      logs
```

To migrate to another server:

```bash
docker stop ypbrief
cd /root
tar -czf ypbrief-backup.tar.gz ypbrief
```

Copy `ypbrief-backup.tar.gz` to the new server, then:

```bash
cd /root
tar -xzf ypbrief-backup.tar.gz
docker run -d \
  --name ypbrief \
  --restart unless-stopped \
  -p 48787:48787 \
  -v /root/ypbrief/data:/app/data \
  -v /root/ypbrief/exports:/app/exports \
  -v /root/ypbrief/logs:/app/logs \
  supergo6/ypbrief:latest
```

The key files to preserve are:

- `/root/ypbrief/data/ypbrief.db`
- `/root/ypbrief/data/key.env`
- `/root/ypbrief/exports/`

## Updating Docker

```bash
docker pull supergo6/ypbrief:latest
docker stop ypbrief
docker rm ypbrief
docker run -d \
  --name ypbrief \
  --restart unless-stopped \
  -p 48787:48787 \
  -v /root/ypbrief/data:/app/data \
  -v /root/ypbrief/exports:/app/exports \
  -v /root/ypbrief/logs:/app/logs \
  supergo6/ypbrief:latest
```

Back up `/root/ypbrief` before major upgrades.

## Web UI Pages

- Dashboard: latest digest preview, recent summaries, and one-off YouTube URL summarization.
- Daily Digests: manual digest generation, digest history, detail view, copy/export/download, rerun, and delivery.
- Videos: video list, channel-grouped browsing, reading view, maintenance view, transcript, summary, copy/download actions, and manual processing.
- Sources: source and group management, bulk import, export, and backup-oriented source maintenance.
- Prompts: editable prompts for single-video summaries and daily digests.
- Automation: scheduled jobs, source scope, time windows, language, delivery settings, and run history.
- Settings: YouTube API, proxy, LLM providers/models, Telegram, Email, and access password rotation.

## Common CLI Commands

Show resolved config:

```bash
ypbrief --env-file key.env config
```

Add a source:

```bash
ypbrief --env-file key.env source add "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

Process one video:

```bash
ypbrief --env-file key.env video process "https://www.youtube.com/watch?v=VIDEO_ID"
```

Summarize an existing video:

```bash
ypbrief --env-file key.env summarize video VIDEO_ID
```

Export transcript:

```bash
ypbrief --env-file key.env export transcript --video-id VIDEO_ID --format md
```

Export summary:

```bash
ypbrief --env-file key.env export summary --video-id VIDEO_ID
```

## Operations

View Docker logs:

```bash
docker logs -f ypbrief
```

Restart:

```bash
docker restart ypbrief
```

Check health locally:

```bash
curl http://127.0.0.1:48787/api/health
```

If a scheduled digest appears slow, check the run history in the Automation or Daily Digests pages. YPBrief reuses existing single-video summaries when available, but each digest run still asks the selected LLM to generate a fresh digest from the included video summaries. Reasoning models can take noticeably longer than faster chat models.

## Security Notes

Keep these private:

- `key.env`
- `data/`
- `exports/`
- `actions-exports/`
- `logs/`
- SQLite database files
- cookies
- certificates
- provider API keys
- Telegram and SMTP credentials
- private source lists and custom prompts

For GitHub Actions Lite, the intended exception is a private fork: digest Markdown and single-video `summary.md` under `actions-exports/` may be committed there if you accept that anyone with repository access can read them. Do not commit those outputs to a public repository unless you intentionally want them public.

Safe public templates:

- `key.env.example`
- `sources.example.yaml`
- `prompts.example.yaml`

For public deployments:

- Use a strong `YPBRIEF_ACCESS_PASSWORD`.
- Rotate the password from Settings when needed.
- Put the service behind your preferred access control, reverse proxy, firewall, or server management stack if exposing it to the internet.
- Keep Docker volumes and backups private.

## Notes On Cost

YPBrief can be run with very low infrastructure cost:

- YouTube Data API usage is usually covered by the free quota for personal/small-team metadata lookup.
- Proxy is optional and only needed in difficult network environments.
- Docker can run on a small VPS for typical personal use.
- The main variable cost is the LLM provider/model you choose.

For a personal deployment with a few dozen recurring sources, SQLite is sufficient. A future database upgrade is only worth considering if the project grows into a multi-user or high-volume service.
