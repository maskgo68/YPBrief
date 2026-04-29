# YPBrief

[English](README-en.md) | 简体中文

YouTube Podcast Brief.

YPBrief 是一个自托管的 YouTube 播客与长视频简报工具。它会定期检查你关注的 YouTube 频道或播放列表，获取新视频的字幕，生成单视频总结，再合成为每日或定时简报，并通过 Web UI、Telegram、飞书或 Email 查看和接收。

它适合长期关注固定信息源的人，例如投资播客、科技访谈、研究频道、市场评论、产品访谈和专家讨论。YPBrief 的目标不是做知识库或视频播放器，而是把重复出现的长视频来源变成可追溯、可重复、可阅读的简报。

## 主要特点

- 支持 YouTube channel、playlist 和单视频链接。
- 支持来源分组，例如投资、科技、研究、健康等。
- 自动获取视频字幕，生成单视频总结。
- 支持按来源、分组、时间窗口生成每日或定时简报。
- 支持 Telegram、飞书和 Email 推送。
- 定时任务支持成功日报、无更新和失败告警通知；失败告警会标明来源、频道、视频、发布时间和简短原因。
- Web UI 提供来源管理、手动运行、定时任务、视频总结、日报历史、提示词和模型配置。
- 支持 Docker/VPS 常驻部署，也支持 GitHub Actions Lite 无服务器定时运行。
- 本地保存处理记录，后续生成日报时可复用已处理过的视频总结。

## 适合谁

YPBrief 更适合固定来源、长期运行的场景：

- 投资者和分析师跟踪市场评论。
- 研究者跟踪专家访谈和领域讨论。
- 创业者、产品和技术人员跟踪行业播客。
- 内容团队跟踪指定频道或播放列表。
- 个人用户搭建私有的 YouTube 信息简报工作流。

如果你只是偶尔总结一个视频，也可以用 Dashboard 的单视频总结；如果你需要每天自动检查一批固定来源，YPBrief 的定时简报会更有价值。

## 工作流程

```text
YouTube 频道 / 播放列表 / 单视频
-> 获取视频元数据
-> 下载字幕
-> 清洗 transcript
-> 生成单视频总结
-> 生成每日或定时综合简报
-> Web UI / Telegram / 飞书 / Email
```

YPBrief 使用 YouTube Data API 获取元数据，使用 `yt-dlp` 获取字幕，使用你配置的 LLM provider 生成总结。

## 运行方式

YPBrief 有三种常见运行方式：

| 方式 | 适合场景 |
| --- | --- |
| 本地运行 | 开发、试用、在自己的电脑上长期使用 |
| Docker / VPS | 推荐的正式部署方式，有 Web UI 和完整历史 |
| GitHub Actions Lite | 不想租 VPS，只想每天定时收到固定来源简报 |

Docker/VPS 是完整版本，包含 Web UI、数据库历史、完整运行记录和维护视图。GitHub Actions Lite 是轻量版本，不运行 Web UI，也不保留完整数据库历史。

## 基础配置

YPBrief 至少需要：

- YouTube Data API key
- 一个 LLM provider 的 API key
- 一个模型名
- Web UI 访问密码

本地或 Docker 部署使用 `key.env` 保存配置。可以从模板复制：

```bash
copy key.env.example key.env
```

最小配置示例：

```env
YOUTUBE_DATA_API_KEY=

LLM_PROVIDER=openrouter
LLM_MODEL=
OPENROUTER_API_KEY=

YPBRIEF_ACCESS_PASSWORD=
```

你也可以使用 OpenAI、Gemini、Claude、xAI、DeepSeek、SiliconFlow、OpenRouter 或其他 OpenAI-compatible 服务。

### Telegram 推送

如果需要 Telegram 推送：

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Telegram Bot Token 通过 Telegram 的 BotFather 创建 bot 获取；`TELEGRAM_CHAT_ID` 是接收消息的个人、群组或频道 id。

### 飞书推送

如果需要飞书群机器人推送：

```env
FEISHU_ENABLED=true
FEISHU_WEBHOOK_URL=
FEISHU_SECRET=
```

飞书使用群聊里的“自定义机器人”Webhook，`FEISHU_SECRET` 只在群机器人开启签名校验时填写。

### Email 推送

如果需要 Email 推送：

```env
EMAIL_ENABLED=true
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
```

### 代理

代理默认关闭。只有当你的服务器访问 YouTube 字幕不稳定、被限流或被阻断时，才需要开启。如果采用 GitHub Actions Lite 部署，建议配置代理，因为 GitHub runner 的默认 IP 质量不稳定，抓取 YouTube 字幕时更容易遇到限流或风控。

如果代理服务商给你的是 `host`、`port`、`username`、`password`，把它们拼成下面这种 URL：

```text
http://username:password@host:port
```

在 Web UI 里通常只需要填写“通用代理地址”。如果手动写 `key.env`，可以把同一个代理地址填到下面三项：

```env
YOUTUBE_PROXY_ENABLED=true
YOUTUBE_PROXY_HTTP=http://username:password@host:port
YOUTUBE_PROXY_HTTPS=http://username:password@host:port
YT_DLP_PROXY=http://username:password@host:port
```

其中 `YT_DLP_PROXY` 用于字幕发现和下载，通常是最关键的一项；前两项用于其他 YouTube 相关网络请求。

不使用代理时保持关闭：

```env
YOUTUBE_PROXY_ENABLED=false
```

## 本地运行

创建并激活 Python 环境：

```bash
python -m venv .venv
.venv\Scripts\activate
```

安装依赖：

```bash
pip install -e ".[transcripts,llm,dev]"
```

初始化数据库：

```bash
ypbrief --env-file key.env init-db
```

Windows 一键启动：

```bash
run.bat
```

默认地址：

```text
API:    http://127.0.0.1:48787
Web UI: http://127.0.0.1:45173
```

## Docker 部署

推荐 VPS 部署：

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

首次启动时，容器会在挂载的 `data` 目录中创建 `key.env`，并生成一个初始访问密码。初始密码会显示在 Docker 日志中：

```bash
docker logs ypbrief
```

打开：

```text
http://YOUR_SERVER_IP:48787
```

建议在公网部署时放到你自己的反向代理、访问网关、防火墙或服务器安全策略之后。

## GitHub Actions Lite

GitHub Actions Lite 是 YPBrief 的无服务器模式。它适合不需要 Web UI、只想每天自动生成固定来源简报的用户。

它可以做到：

- 定时或手动运行 GitHub Actions。
- 从仓库里的 `sources.yaml` 读取频道和播放列表。
- 抓取新视频字幕并生成单视频总结。
- 生成每日综合简报。
- 推送到 Telegram、飞书或 Email。
- 任务失败时发送简短失败通知，便于定位具体来源和视频。
- 把生成的 Markdown 简报保存到仓库。

它不适合：

- 在网页里管理来源和任务。
- 保存完整 SQLite 历史。
- 保存完整 transcript 和 VTT 字幕归档。
- 在失败后通过维护视图逐条重试。
- 管理多个复杂定时任务。

如果你需要这些能力，请使用 Docker/VPS 版本。

### Actions 配置

建议把项目 fork 到自己的 private repository，再配置 GitHub Actions。真实 API key 和 token 放在 GitHub Secrets；来源列表放在 private repository 的 `sources.yaml`。由于 GitHub runner 默认 IP 质量不稳定，Actions 部署建议同时配置代理，避免字幕抓取失败或速度很慢。

Actions 主要需要三类配置：

1. `sources.yaml`：写关注哪些 YouTube 来源。
2. Secrets：写 API key、Telegram token、代理账号等敏感信息。
3. Variables：写默认运行参数，例如语言、时间窗口、分组。

#### 1. sources.yaml

`sources.yaml` 放在 private repository 根目录，用来定义分组和来源。示例：

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

Secrets 在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions -> Secrets` 中配置。

(1) YOUTUBE_DATA_API_KEY

`YOUTUBE_DATA_API_KEY=your_youtube_api_key`

(2) `LLM_PROVIDER` 必须填写支持的 provider id，建议全部使用小写。当前支持：`openrouter`、`openai`、`gemini`、`claude`、`xai`、`deepseek`、`siliconflow`、`custom_openai`。

OpenRouter 示例：

```text
LLM_PROVIDER=openrouter
LLM_MODEL=openai/gpt-4.1-mini
OPENROUTER_API_KEY=your_openrouter_api_key
```

(3) 推送 Secrets：Telegram 使用 `TELEGRAM_ENABLED`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`；飞书使用 `FEISHU_ENABLED`、`FEISHU_WEBHOOK_URL`、`FEISHU_SECRET`。

```text
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

FEISHU_ENABLED=false
FEISHU_WEBHOOK_URL=your_feishu_bot_webhook
FEISHU_SECRET=optional_signing_secret
```

(4) 代理 Secrets：`YOUTUBE_PROXY_ENABLED`、`YOUTUBE_PROXY_HTTP`、`YOUTUBE_PROXY_HTTPS`、`YT_DLP_PROXY`。

Actions 代理格式与本地/Docker 相同，通常三个字段填同一个代理 URL：

```text
YOUTUBE_PROXY_ENABLED=true
YOUTUBE_PROXY_HTTP=http://username:password@host:port
YOUTUBE_PROXY_HTTPS=http://username:password@host:port
YT_DLP_PROXY=http://username:password@host:port
```

#### 3. Variables

Variables 在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions -> Variables` 中配置，用于非敏感默认参数，可配置：`YPBRIEF_ACTIONS_TIMEZONE`、`YPBRIEF_ACTIONS_WINDOW`、`YPBRIEF_ACTIONS_GROUP`、`YPBRIEF_ACTIONS_LANGUAGE`、`YPBRIEF_ACTIONS_MAX_VIDEOS_PER_SOURCE`。

Variables 示例：

```text
YPBRIEF_ACTIONS_TIMEZONE=Asia/Shanghai
YPBRIEF_ACTIONS_WINDOW=last_1
YPBRIEF_ACTIONS_GROUP=all
YPBRIEF_ACTIONS_LANGUAGE=zh
YPBRIEF_ACTIONS_MAX_VIDEOS_PER_SOURCE=10
```

配置完成后，在 GitHub 页面打开：

```text
Actions -> YPBrief Daily -> Run workflow
```

也可以等待定时任务自动运行。

## Web UI 页面

- Dashboard：查看最新简报、最近总结，并运行单视频总结。
- Sources：管理频道、播放列表、分组和批量导入。
- Videos：查看视频、总结、transcript，并进行复制或下载。
- Daily Digests：生成和查看日报历史。
- Prompts：编辑单视频总结和日报提示词。
- Automation：配置定时任务和推送。
- Settings：配置 YouTube API、代理、LLM、Telegram、飞书、Email 和访问密码。

## 常用命令

查看 Docker 日志：

```bash
docker logs -f ypbrief
```

重启 Docker 容器：

```bash
docker restart ypbrief
```

检查服务健康状态：

```bash
curl http://127.0.0.1:48787/api/health
```

处理单个视频：

```bash
ypbrief --env-file key.env video process "https://www.youtube.com/watch?v=VIDEO_ID"
```

生成单视频总结：

```bash
ypbrief --env-file key.env summarize video VIDEO_ID
```

## 未来方向

YPBrief 后续计划抽象成可被 Agent 调用的能力层，例如 Skills 或 MCP。目标是让 OpenCLAW、Claude Code、各类 Agent 和自动化工作流可以直接调用 YPBrief 的核心能力，包括来源查询、视频转录、单视频总结、日报生成、失败排查和内容推送。

完整 Web UI 和 Docker/VPS 部署仍会作为主线形态保留；Skills / MCP 更偏向把 YPBrief 变成可组合的工具能力，方便接入个人助理、研究 Agent、投资分析 Agent 或团队内部自动化系统。

## 安全提醒

如果把 YPBrief 部署到公网，请务必设置强访问密码，并妥善保护服务器，避免暴露`key.env`。

GitHub Actions Lite 如果使用真实来源和真实总结，建议放在 private repository 中运行。
