# YPBrief

English | [简体中文](README.md)

YouTube Podcast Brief.

YPBrief is a self-hosted briefing tool for YouTube podcasts and long-form videos. It regularly checks the YouTube channels or playlists you follow, fetches subtitles for new videos, generates single-video summaries, combines them into daily or scheduled briefs, and lets you read or receive them through the Web UI, Telegram, Feishu, or Email.

It is designed for people who follow recurring information sources over time, such as investing podcasts, technology interviews, research channels, market commentary, product interviews, and expert discussions. YPBrief is not trying to be a knowledge base or a video player. Its goal is to turn recurring long-form YouTube sources into traceable, repeatable, readable briefs.

## Key Features

- Supports YouTube channels, playlists, and single-video links.
- Supports source groups such as investing, technology, research, health, and more.
- Automatically fetches video subtitles and generates single-video summaries.
- Generates daily or scheduled briefs by source, group, and time window.
- Supports Telegram, Feishu, and Email delivery.
- Scheduled jobs can send success digests, no-update notices, and short failure alerts. Failure alerts include the source, channel, video, publish date, and a concise reason.
- The Web UI provides source management, manual runs, scheduled jobs, video summaries, digest history, prompts, and model configuration.
- Supports always-on Docker/VPS deployment and no-server GitHub Actions Lite.
- Keeps local processing records so later digest runs can reuse already processed video summaries.

## Who It Is For

YPBrief works best for fixed-source, long-running workflows:

- Investors and analysts tracking market commentary.
- Researchers following expert interviews and domain discussions.
- Founders, product people, and engineers tracking industry podcasts.
- Content teams monitoring specific channels or playlists.
- Individual users building a private YouTube briefing workflow.

If you only need to summarize an occasional video, the Dashboard single-video summary tool is enough. If you want to automatically check a fixed set of sources every day, scheduled briefs are more useful.

## Workflow

```text
YouTube channels / playlists / single videos
-> Fetch video metadata
-> Download subtitles
-> Clean transcript
-> Generate single-video summary
-> Generate daily or scheduled digest
-> Web UI / Telegram / Feishu / Email
```

YPBrief uses the YouTube Data API for metadata, `yt-dlp` for subtitles, and your configured LLM provider for summarization.

## Real Run Examples

The [`examples/`](examples/) folder shows a set of real run examples. You can review them first to see the output:

- [Chinese daily report example](examples/Daily%20Report-Invest%20Daily%20Report-260428-zh.md)
- [English daily report example](examples/Daily%20Report-Invest%20Daily%20Report-260428-en.md)
- [Chinese video summary example](examples/Video%20Summary-Invest%20Like%20The%20Best%20-%20Legendary%20Trader%20Paul%20Tudor%20Jones%20on%20AI%20Risk,%20Bubbles%20and%20Buffett%20-%20260428-zh.md)
- [English video summary example](examples/Video%20Summary-Invest%20Like%20The%20Best%20-%20Legendary%20Trader%20Paul%20Tudor%20Jones%20on%20AI%20Risk,%20Bubbles%20and%20Buffett%20-%20260428-en.md)

## Running Modes

YPBrief has three common running modes:

| Mode | Best For |
| --- | --- |
| Local run | Development, trial use, or long-term use on your own computer |
| Docker / VPS | Recommended production deployment with Web UI and full history |
| GitHub Actions Lite | No VPS; scheduled fixed-source briefs only |

Docker/VPS is the full version. It includes the Web UI, database history, complete run records, and maintenance views. GitHub Actions Lite is the lightweight version. It does not run the Web UI and does not keep full database history.

Note: a scheduled job's timezone controls when it triggers and sends; run records, database timestamps, and logs should be interpreted as UTC by default.

## Basic Configuration

YPBrief needs at least:

- YouTube Data API key
- An API key for one LLM provider
- A model name
- Web UI access password

Local and Docker deployments use `key.env` for configuration. You can copy it from the template:

```bash
copy key.env.example key.env
```

Minimal configuration example:

```env
YOUTUBE_DATA_API_KEY=

LLM_PROVIDER=openrouter
LLM_MODEL=
OPENROUTER_API_KEY=

YPBRIEF_ACCESS_PASSWORD=
```

You can also use OpenAI, Gemini, Claude, xAI, DeepSeek, SiliconFlow, OpenRouter, or another OpenAI-compatible service.

### Telegram Delivery

To enable Telegram delivery:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Create the Telegram bot through BotFather to get the bot token. `TELEGRAM_CHAT_ID` is the personal chat, group, or channel ID that should receive messages.

### Feishu Delivery

To enable Feishu group bot delivery:

```env
FEISHU_ENABLED=true
FEISHU_WEBHOOK_URL=
FEISHU_SECRET=
```

Feishu delivery uses a group chat custom bot webhook. `FEISHU_SECRET` is only needed if signature verification is enabled for the bot.

### Email Delivery

To enable Email delivery:

```env
EMAIL_ENABLED=true
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
```

### Proxy

Proxy is disabled by default. Enable it only when your server has unstable YouTube subtitle access, is rate-limited, or is blocked. If you deploy through GitHub Actions Lite, proxy configuration is recommended because GitHub runner IP quality can be inconsistent and may trigger YouTube subtitle throttling or risk checks.

If your proxy provider gives you `host`, `port`, `username`, and `password`, combine them into this URL format:

```text
http://username:password@host:port
```

In the Web UI, you usually only need to fill the generic proxy URL field. If you edit `key.env` manually, you can put the same proxy URL into all three fields:

```env
YOUTUBE_PROXY_ENABLED=true
YOUTUBE_PROXY_HTTP=http://username:password@host:port
YOUTUBE_PROXY_HTTPS=http://username:password@host:port
YT_DLP_PROXY=http://username:password@host:port
```

`YT_DLP_PROXY` is used for subtitle discovery and download, and is usually the most important field. The first two fields are used for other YouTube-related network requests.

Keep proxy disabled if you do not need it:

```env
YOUTUBE_PROXY_ENABLED=false
```

## Local Run

Create and activate a Python environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -e ".[transcripts,llm,dev]"
```

Initialize the database:

```bash
ypbrief --env-file key.env init-db
```

One-click Windows start:

```bash
run.bat
```

Default URLs:

```text
API:    http://127.0.0.1:48787
Web UI: http://127.0.0.1:45173
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

On first boot, the container creates `key.env` in the mounted `data` directory and generates an initial access password. The initial password is shown in Docker logs:

```bash
docker logs ypbrief
```

Open:

```text
http://YOUR_SERVER_IP:48787
```

If you expose YPBrief to the public internet, put it behind your own reverse proxy, access gateway, firewall, or server security policy.

## GitHub Actions Lite

GitHub Actions Lite is YPBrief's no-server mode. It is for users who do not need the Web UI and only want scheduled fixed-source briefs.

It can:

- Run GitHub Actions on a schedule or manually.
- Read channels and playlists from `sources.yaml` in the repository.
- Fetch subtitles for new videos and generate single-video summaries.
- Generate a daily digest.
- Deliver to Telegram, Feishu, or Email.
- Send a short failure notice when a task fails, making it easier to locate the exact source and video.
- Save generated Markdown briefs back to the repository.

It is not suitable for:

- Managing sources and jobs in a browser.
- Keeping complete SQLite history.
- Keeping full transcript and VTT subtitle archives.
- Retrying failed videos one by one through a maintenance view.
- Managing many complex scheduled jobs.

Use Docker/VPS if you need those capabilities.

### Actions Configuration

Fork the project into your own private repository before configuring GitHub Actions. Real API keys and tokens should go into GitHub Secrets. The source list should live in `sources.yaml` inside the private repository. Because GitHub runner IP quality is inconsistent, proxy configuration is recommended for Actions deployment to reduce subtitle fetch failures and slow runs.

Actions mainly needs three kinds of configuration:

1. `sources.yaml`: which YouTube sources to follow.
2. Secrets: API keys, Telegram token, proxy credentials, and other sensitive values.
3. Variables: default non-sensitive run parameters, such as language, time window, and group.

#### 1. sources.yaml

Place `sources.yaml` in the private repository root to define groups and sources. Example:

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

#### 2. Secrets

Configure Secrets in `Settings -> Secrets and variables -> Actions -> Secrets`.

(1) YOUTUBE_DATA_API_KEY

`YOUTUBE_DATA_API_KEY=your_youtube_api_key`

(2) `LLM_PROVIDER` must be a supported provider ID. Lowercase is recommended. Currently supported values: `openrouter`, `openai`, `gemini`, `claude`, `xai`, `deepseek`, `siliconflow`, `custom_openai`.

OpenRouter example:

```text
LLM_PROVIDER=openrouter
LLM_MODEL=openai/gpt-4.1-mini
OPENROUTER_API_KEY=your_openrouter_api_key
```

(3) Delivery Secrets: Telegram uses `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`; Feishu uses `FEISHU_ENABLED`, `FEISHU_WEBHOOK_URL`, and `FEISHU_SECRET`.

```text
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

FEISHU_ENABLED=false
FEISHU_WEBHOOK_URL=your_feishu_bot_webhook
FEISHU_SECRET=optional_signing_secret
```

(4) Proxy Secrets: `YOUTUBE_PROXY_ENABLED`, `YOUTUBE_PROXY_HTTP`, `YOUTUBE_PROXY_HTTPS`, and `YT_DLP_PROXY`.

Actions proxy format is the same as local/Docker. Usually the same proxy URL can be used for all three fields:

```text
YOUTUBE_PROXY_ENABLED=true
YOUTUBE_PROXY_HTTP=http://username:password@host:port
YOUTUBE_PROXY_HTTPS=http://username:password@host:port
YT_DLP_PROXY=http://username:password@host:port
```

#### 3. Variables

Configure Variables in `Settings -> Secrets and variables -> Actions -> Variables`. They are for non-sensitive defaults: `YPBRIEF_ACTIONS_TIMEZONE`, `YPBRIEF_ACTIONS_WINDOW`, `YPBRIEF_ACTIONS_GROUP`, `YPBRIEF_ACTIONS_LANGUAGE`, and `YPBRIEF_ACTIONS_MAX_VIDEOS_PER_SOURCE`.

Variables example:

```text
YPBRIEF_ACTIONS_TIMEZONE=Asia/Shanghai
YPBRIEF_ACTIONS_WINDOW=last_1
YPBRIEF_ACTIONS_GROUP=all
YPBRIEF_ACTIONS_LANGUAGE=zh
YPBRIEF_ACTIONS_MAX_VIDEOS_PER_SOURCE=10
```

After configuration, open:

```text
Actions -> YPBrief Daily -> Run workflow
```

You can also wait for the scheduled run.

## Web UI Pages

- Dashboard: view the latest brief, recent summaries, and run single-video summaries.
- Sources: manage channels, playlists, groups, and bulk imports.
- Videos: view videos, summaries, transcripts, and copy or download content.
- Daily Digests: generate and view digest history.
- Prompts: edit single-video and daily digest prompts.
- Automation: configure scheduled jobs and delivery.
- Settings: configure YouTube API, proxy, LLM, Telegram, Feishu, Email, and access password.

## Common Commands

View Docker logs:

```bash
docker logs -f ypbrief
```

Restart the Docker container:

```bash
docker restart ypbrief
```

Check service health:

```bash
curl http://127.0.0.1:48787/api/health
```

Process a single video:

```bash
ypbrief --env-file key.env video process "https://www.youtube.com/watch?v=VIDEO_ID"
```

Generate a single-video summary:

```bash
ypbrief --env-file key.env summarize video VIDEO_ID
```

## Future Direction

YPBrief is planned to evolve into a capability layer that Agents can call, such as Skills or an MCP Server. The goal is to let OpenCLAW, Claude Code, other Agents, and automation workflows directly use YPBrief capabilities including source lookup, video transcription, single-video summaries, daily digest generation, failure diagnosis, and content delivery.

The full Web UI and Docker/VPS deployment will remain the main product form. Skills / MCP will make YPBrief more composable, so it can be plugged into personal assistants, research Agents, investing analysis Agents, or internal team automation systems.

## Security Notes

If you deploy YPBrief on the public internet, use a strong access password and protect the server carefully. Do not expose `key.env`.

If GitHub Actions Lite uses real sources and real summaries, run it in a private repository.
