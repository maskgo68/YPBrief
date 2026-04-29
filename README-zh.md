# YPBrief

YouTube Podcast Brief.

YPBrief 是一个自托管的 YouTube 播客定时简报工具，适合需要长期关注固定 YouTube 来源的人。

它会监听你配置的 YouTube 频道和播放列表，获取视频元数据和字幕，生成单视频总结，再把新更新合成为可读的每日或定时简报，并通过 Telegram 或 Email 推送。Web UI 更像一个实用的操作台，用于来源管理、提示词调整、手动运行、自动任务、阅读、导出和排错。

YPBrief 不是通用知识库、视频播放器或自动化画布。它的核心目标很明确：把重复出现的长视频 YouTube 来源，转成可追溯、可重复、可阅读的内容简报。

## 适合谁

如果你经常关注 YouTube 播客、访谈、研究频道、市场评论、产品访谈或专家讨论，并希望不用手动检查每个来源就能获得重点更新，YPBrief 会比较适合你。

典型用户包括：

- 关注市场评论的投资者和分析师
- 跟踪领域专家和长访谈的研究者
- 需要每日或每周来源更新的运营/管理者
- 跟踪特定频道或播放列表的内容团队
- 希望搭建私有自托管简报流程的个人用户

当你的来源是固定、重复、结构化的频道、播放列表或主题分组时，YPBrief 的效果最好。

## 功能概览

核心流程：

```text
YouTube 频道 / 播放列表 / 单视频
-> YouTube Data API 元数据
-> yt-dlp 字幕下载
-> 清洗后的 transcript
-> 单视频总结
-> 每日或定时综合简报
-> Telegram / Email / Web UI
```

主要能力：

- 管理 YouTube 频道、播放列表和单视频来源。
- 从粘贴文本或 `.txt` 文件批量导入来源，并自动识别重复。
- 按投资、科技、医疗、研究等主题组织来源分组。
- 在 Dashboard 中粘贴单个 YouTube URL，生成一次性总结。
- 手动生成简报，支持选择来源、分组、滚动窗口、自定义日期范围或全部历史。
- 创建定时任务，每个任务可配置来源范围、语言、时间窗口、运行时间和推送渠道。
- 同一天多次运行日报时，保留独立历史记录，不互相覆盖。
- 后续生成日报时可复用已处理过的 transcript 和单视频总结。
- 本地保存原始 VTT 字幕、清洗 transcript、单视频总结、日报总结、运行记录和推送日志。
- 在视频详情页复制或下载 summary 和 transcript。
- 按时间或按频道分组浏览视频。
- 编辑单视频总结和日报总结提示词。
- 从 Web UI 配置多个 LLM provider 并切换当前模型。
- 通过 Telegram 和 Email 推送简报。
- 可选启用 Telegram Bot Inbox，让授权用户发送单个 YouTube 链接并收到总结。
- 用单一访问密码保护 Web UI，并可在 Settings 中轮换密码。

## 产品边界

YPBrief 有意聚焦在“定时内容简报生成”上。

它不是 Notion、Airtable、Obsidian、Readwise、n8n 或完整知识库的替代品。这些工具更适合长期笔记管理、标签、数据库视图、灵活自动化和知识检索。YPBrief 保留数据库和本地归档，是为了让简报流水线可复现、可排错，但主要产物仍然是简报。

相比通用自动化工作流，YPBrief 把“重复监控 YouTube 来源并生成简报”这个场景做成了一套专用系统：来源、分组、提示词、字幕、总结、运行历史、定时任务、推送和维护视图都属于同一条工作流。

## 架构

YPBrief 是一个小型自托管 Web 应用：

- 后端：`FastAPI`
- 前端：`React + Vite`
- 数据库：`SQLite + FTS5`
- 调度器：`APScheduler`
- 字幕后端：`yt-dlp`
- LLM 层：多个模型服务的 provider adapter
- 推送：Telegram Bot API 和 SMTP Email
- 部署方式：本地 Python、Docker/VPS、GitHub Actions Lite

运行行为：

- YouTube Data API 用于频道、播放列表、视频元数据和时长查询。
- `yt-dlp` 用于字幕发现和 VTT 下载。
- 字幕选择优先匹配视频主语言，再尝试常见英文/中文字幕轨道，最后回退到任意可用原始字幕轨道。
- 如果 YouTube 元数据能拿到时长，`duration <= 300` 秒的视频会被跳过，避免 Shorts、预告片和低信息量短视频污染日报。
- Markdown 是主要的人类可读导出格式。
- SQLite 存储结构化运行状态，包括来源、分组、视频、transcript、summary、日报运行、定时任务、设置和推送日志。

## 项目结构

```text
src/ypbrief/                         核心后端服务和领域逻辑
src/ypbrief_api/app.py               FastAPI 服务、API 路由、认证、调度器接线和 Web UI 静态托管
web/                                 React + Vite 前端源码
tests/                               后端、API、部署和 Actions Lite 自动化测试
.github/workflows/github-actions-daily.yml
                                     GitHub Actions Lite workflow
scripts/github_actions_daily.py      GitHub Actions Lite 一次性运行脚本
scripts/tee_run.py                   run.bat 使用的本地日志辅助脚本
Dockerfile                           生产 Docker 镜像定义
docker-entrypoint.sh                 容器首次启动配置初始化脚本
docker-compose.yml                   可选单服务 Compose 部署
run.bat                              Windows 本地启动脚本
pyproject.toml                       Python 包元数据和依赖
key.env.example                      公开配置模板，Docker 首次启动会复制它
prompts.example.yaml                 提示词结构示例
sources.example.yaml                 来源/分组导入示例
.gitignore                           公开仓库安全规则
.dockerignore                        Docker build context 安全规则
```

仅本地或私有仓库使用的目录：

```text
actions-exports/   GitHub Actions Lite Markdown 输出；只应在 private fork 或本地存在
data/              SQLite 数据库、运行状态和 Docker key.env；只应在本地/VPS 存在
exports/           VTT、transcript、视频总结和日报归档；只应在本地/VPS 存在
logs/              运行日志；只应在本地/VPS 存在
PRD doc/           内部规划文档；不属于公开发布或 Docker 镜像
Project Evaluation/
                   内部评估材料；不属于公开发布或 Docker 镜像
web/node_modules/  本地前端依赖，可重建
web/dist/          前端构建产物，可本地生成或在 Docker build 中生成
```

重要后端模块：

- `config.py`：读取 `key.env` 和环境变量，解析路径、代理、provider key、推送设置和运行默认值。
- `database.py`：负责 SQLite schema、迁移和持久化 helper，覆盖来源、视频、字幕、总结、运行、任务、设置、provider、prompt 和推送日志。
- `youtube.py`：封装 YouTube Data API 元数据发现，包括视频、频道、播放列表、发布时间和时长。
- `sources.py`：管理来源、来源分组、YAML 导入导出、批量新增、去重和 channel/playlist/video 标准化。
- `transcripts.py`：通过 `yt-dlp` 获取字幕元数据和 VTT 文件，支持语言回退、cookies 和代理。
- `cleaner.py`：把字幕片段清洗成可读 transcript。
- `video_processor.py`：编排单视频元数据、字幕抓取、transcript 清洗、summary 生成、状态更新和导出。
- `summarizer.py`：使用渲染后的提示词和当前 LLM provider 生成单视频总结。
- `daily.py`：从视频总结构建手动、定时和 Actions Lite 日报输入；处理日期窗口、复用、重试、日报生成和 Markdown 导出。
- `scheduler.py`：管理定时任务、立即运行、APScheduler 集成、运行历史和任务级推送行为。
- `delivery.py`：发送 Telegram 和 Email，拆分长 Telegram 消息，脱敏敏感值，并记录推送日志。
- `prompts.py`：管理默认提示词、数据库提示词、分组提示词、激活提示词、预览、导入导出和旧 YAML prompt 兼容。
- `provider_config.py`：优先从 SQLite，其次从 `key.env` 解析当前 provider/model 配置。
- `llm.py`：包含 OpenAI-compatible、Gemini、Claude、Grok/xAI、DeepSeek、SiliconFlow、OpenRouter 和自定义 provider adapter。
- `exporter.py`：写入 transcript、summary、metadata 和服务端导出文件。
- `archive.py`：写入日报归档文件，并避免同日多次运行互相覆盖。
- `text_normalization.py`：轻量输出清理 helper。
- `cli.py`：提供本地或脚本化使用的命令行入口。

API 与部署入口：

- `src/ypbrief_api/app.py`：创建 FastAPI app，注册 API 路由，托管构建后的 Web UI，执行认证，启动后台调度器，并把 Settings 修改同步回 `key.env`。
- `.github/workflows/github-actions-daily.yml`：GitHub Actions Lite 的定时/手动无服务器日报 workflow。
- `scripts/github_actions_daily.py`：Actions Lite 一次性 runner，创建临时 `key.env` 和 SQLite，导入 `sources.yaml`，调用共享核心服务，清理不保留的产物，打印推送结果，只留下允许提交的 Markdown 输出。
- `Dockerfile`：先用 Node 构建前端，再把 Python 后端、构建后的 Web UI 和 `key.env.example` 打进 slim 运行镜像。
- `docker-entrypoint.sh`：首次启动时创建 `/app/data/key.env`，填充 Docker 运行路径，生成初始访问密码，然后启动 Uvicorn。
- `run.bat`：Windows 本地后端和前端启动脚本。

前端入口：

- `web/src/App.tsx`：主 React 应用，包括 Dashboard、Sources、Videos、Daily Digests、Prompts、Automation、Settings、认证流程和 UI 状态。
- `web/src/api.ts`：API client helper，处理 bearer token，并把 JSON/HTML 代理错误压缩成可读错误信息。
- `web/src/types.ts`：与 API payload 对齐的前端类型定义。
- `web/src/main.tsx`：React 应用启动入口。
- `web/src/App.css`：应用样式。
- `web/public/`：favicon 和 icon 资源。

测试覆盖按子系统组织：

- `tests/test_api.py`：FastAPI 路由和 Web UI/API 集成行为。
- `tests/test_github_actions_daily.py`：Actions Lite 配置解析、allowlist、清理、dry-run 和推送日志。
- `tests/test_deployment_artifacts.py`：仓库和部署安全预期。
- `tests/test_daily.py` 以及 API 测试中的 scheduler 相关用例：日报和自动化行为。
- 其他 `tests/test_*.py` 覆盖 config、sources、transcripts、prompts、providers、delivery、exporter、CLI 和 YouTube helper。

## 运行数据

YPBrief 会把工作数据放在应用代码之外：

```text
data/             SQLite 数据库、运行状态和 Docker key.env
exports/          VTT 文件、清洗 transcript、视频总结和日报导出
actions-exports/  GitHub Actions Lite 保留的 Markdown 输出
logs/             运行日志
key.env           非 Docker 本地运行的密钥和配置
sources.yaml      本地/private 来源快照；公开仓库应使用 sources.example.yaml
prompts.yaml      本地/private 提示词快照；公开仓库应使用 prompts.example.yaml
```

最重要的文件是 SQLite 数据库：

```text
data/ypbrief.db
```

它保存来源、分组、视频、transcript、summary、日报运行、定时任务、推送日志、模型设置、提示词和其他运行状态。

不同运行方式下的事实来源不同：

- 本地和 Docker/VPS：SQLite 是事实来源。`sources.yaml` 和 `prompts.yaml` 是导入/导出快照，不是实时数据库。
- GitHub Actions Lite：private fork 中的 `sources.yaml` 是每次运行的来源配置。SQLite 是临时数据库，workflow 结束后丢弃。
- Docker 首次启动：镜像里只包含 `key.env.example`；真实 `key.env` 会生成到挂载的 `data/` 目录。

## 发布规则

YPBrief 支持三种运行方式，但它们的上传规则不同。

| 文件或目录 | 公开 GitHub 源码仓库 | Docker 镜像/build context | GitHub Actions private fork | 本地 / VPS 运行 |
| --- | --- | --- | --- | --- |
| `src/`、`web/`、`Dockerfile`、`docker-entrypoint.sh`、`pyproject.toml` | 是 | 是 | 是 | 是 |
| `.github/workflows/`、`scripts/github_actions_daily.py`、tests | 是 | 否 | 是 | 可选 |
| `key.env.example` | 是 | 是 | 是 | 模板 |
| `sources.example.yaml`、`prompts.example.yaml` | 是 | 否 | 是 | 参考/导入 |
| `sources.yaml`、`prompts.yaml` | 否 | 否 | private fork 可提交 | 本地快照 |
| `actions-exports/` | 否 | 否 | private fork 可提交 | Actions 输出 |
| `data/`、`exports/`、`logs/`、`key.env` | 否 | 否 | 否 | 是 |
| 数据库、cookies、API key、代理凭证、Telegram/SMTP 凭证 | 否 | 否 | 只放 Secrets | 是 |
| `PRD doc/`、`Project Evaluation/` | 否 | 否 | 否 | 内部文档 |
| `web/node_modules/`、`web/dist/`、缓存 | 否 | 否 | 否 | 可重建本地文件 |

公开仓库应该是干净的产品源码包：代码、示例、测试、Docker 文件、GitHub Actions workflow 和文档。不要包含私有来源列表、生成的总结、本地数据库、运行导出或凭证。

Docker 镜像比公开仓库更严格。它只需要后端包、构建后的前端、`key.env.example` 和容器入口脚本。GitHub Actions 文件、测试、辅助脚本、来源示例、提示词示例、README、内部文档和运行输出都会被 `.dockerignore` 排除。

GitHub Actions Lite 是例外：在你自己的 private fork 里，如果你接受仓库成员能看到这些内容，可以提交 `sources.yaml` 和 `actions-exports/` 下的 Markdown 输出。不要把 `key.env`、SQLite 数据库、VTT 字幕、完整 transcript、日志和凭证提交到 fork。

## 运行要求

- Python `>= 3.10`
- 如果要本地前端开发，需要 Node.js `>= 20`
- 如果使用容器部署，需要 Docker
- 一个 YouTube Data API key
- 至少一个 LLM provider API key
- 如果服务器访问 YouTube 字幕不稳定，可选配置代理或 cookies

YouTube Data API 对元数据查询有较高免费额度。个人或小团队使用通常不需要为 YouTube API 单独付费。代理默认关闭，只有当服务器 IP 质量较差、经常遇到字幕限流、阻断或反爬错误时才需要配置。如果你的 VPS 或本地网络能稳定访问 YouTube 字幕，就不需要配置代理。

## 配置

YPBrief 在本地和 Docker 部署中使用同一套配置模型：

- SQLite 是 sources、groups、prompts、models、summaries、runs 和 scheduled jobs 的运行时事实来源。
- `key.env` 保存密钥和启动 fallback。
- Web UI 中保存的设置会在适用时写回运行配置，并立即生效。

最小配置：

```env
YOUTUBE_DATA_API_KEY=

LLM_PROVIDER=gemini
GEMINI_API_KEY=

YPBRIEF_ACCESS_PASSWORD=
```

默认 env 模板会刻意省略模型名称。你可以手动添加 `LLM_MODEL` 或 provider 对应的 `*_MODEL` 字段，也可以在 Web UI 中配置模型。

### YouTube Data API

获取 YouTube Data API key：

1. 打开 Google Cloud Console。
2. 创建或选择一个项目。
3. 启用 `YouTube Data API v3`。
4. 在 `APIs & Services -> Credentials` 创建 API key。
5. 把 key 写入 `YOUTUBE_DATA_API_KEY`。

YPBrief 使用这个 key 查询元数据、频道、播放列表和视频时长。它不使用 YouTube API 播放视频。

### 代理

代理默认关闭。只有当你的环境访问字幕不稳定，通常是服务器 IP 被限流、阻断或 YouTube 访问质量较差时，才需要启用。

代理配置不绑定某个服务商。任何标准 HTTP/HTTPS 代理都可以通过通用代理 URL 配置：

```env
YOUTUBE_PROXY_ENABLED=true
YOUTUBE_PROXY_HTTP=http://username:password@host:port
YOUTUBE_PROXY_HTTPS=http://username:password@host:port
YT_DLP_PROXY=http://username:password@host:port
```

`YOUTUBE_PROXY_HTTP` / `YOUTUBE_PROXY_HTTPS` 用于 Python 元数据和字幕辅助请求。`YT_DLP_PROXY` 会直接传给 `yt-dlp`，用于字幕发现和下载。大多数部署中，三个字段使用同一个 HTTP 代理 URL 即可。

YPBrief 也支持 IPRoyal 风格的拆分配置：

```env
YOUTUBE_PROXY_ENABLED=true
IPROYAL_PROXY_HOST=geo.iproyal.com
IPROYAL_PROXY_PORT=12345
IPROYAL_PROXY_USERNAME=your_username
IPROYAL_PROXY_PASSWORD=your_password
```

这些 `IPROYAL_PROXY_*` 字段只是内部拼接成同样的代理 URL。如果其他代理服务商也给 host、port、username、password，建议优先使用通用的 `YOUTUBE_PROXY_HTTP`、`YOUTUBE_PROXY_HTTPS` 和 `YT_DLP_PROXY` 字段。为了最大兼容性，推荐使用 HTTP/HTTPS 代理 URL；SOCKS 支持取决于底层 Python 和 `yt-dlp` 环境。

如果不需要代理：

```env
YOUTUBE_PROXY_ENABLED=false
```

### LLM Providers

YPBrief 支持 OpenAI、Gemini、Claude、SiliconFlow、OpenRouter、Grok/xAI、DeepSeek 和自定义 OpenAI-compatible provider。

常见配置方式：

1. 添加 provider API key。
2. 设置默认 provider 和 model。
3. 启动应用。
4. 后续在 Web UI 中调整当前 provider/model。

Provider endpoint URL 会尽量提供稳定默认值。模型名称不会作为产品默认值写死，因为各家模型更新很快；运行总结前请配置 `LLM_MODEL` 或对应 provider 的 `*_MODEL` 字段。

### 推送

Telegram 和 Email 推送都是可选项。

Telegram 需要：

- bot token
- chat ID
- 可选的 Telegram Bot Inbox 入站 allowlist/webhook 设置

Email 需要：

- SMTP host 和 port
- SMTP username 和 password
- 发件地址
- 收件地址

测试总结流程时可以先关闭推送。

## 本地安装

创建并激活 Python 环境：

```bash
python -m venv .venv
.venv\Scripts\activate
```

安装依赖：

```bash
pip install -e ".[transcripts,llm,dev]"
```

创建本地配置：

```bash
copy key.env.example key.env
```

初始化数据库：

```bash
ypbrief --env-file key.env init-db
```

Windows 启动：

```bash
run.bat
```

默认本地地址：

```text
API:    http://127.0.0.1:48787
Web UI: http://127.0.0.1:45173
```

手动启动后端：

```bash
python -m uvicorn ypbrief_api.app:app --host 127.0.0.1 --port 48787
```

手动启动前端开发服务器：

```bash
cd web
npm install
npm run dev -- --host 127.0.0.1 --port 45173 --strictPort
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

首次启动时，容器会从内置模板创建 `/root/ypbrief/data/key.env`，并生成一个随机初始 `YPBRIEF_ACCESS_PASSWORD`。

查看初始密码：

```bash
docker logs ypbrief
```

或只过滤密码行：

```bash
docker logs ypbrief 2>&1 | grep YPBRIEF_ACCESS_PASSWORD
```

然后打开：

```text
http://YOUR_SERVER_IP:48787
```

你也可以把 YPBrief 放在自己的反向代理或访问网关后面。

### Docker Compose

项目包含一个可选 Compose 文件：

```bash
docker compose up -d
```

它会把本地 `./data`、`./exports` 和 `./logs` 映射到容器。

## GitHub Actions Lite

GitHub Actions Lite 是 YPBrief 的无服务器运行模式，适合只想要定时简报、不需要 Web UI 的用户。

这是主要部署方式之一：

- 不需要 VPS
- 不需要常驻后端
- 不需要 Web UI
- 支持定时或手动触发 GitHub Actions
- Markdown 输出提交回 private fork
- 每次运行后可推送 Telegram 或 Email

它不是 Docker/VPS 版的替代品，而是面向固定来源定时简报的轻量模式。每次运行都会从仓库配置开始，创建临时数据库，生成简报，发送推送，只保留选定 Markdown 输出，然后退出：

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

这个模式适合：

- 不想租 VPS，也想每天收到 YouTube 播客简报
- 私有地监控一组固定来源
- 低维护的“每天运行一次并把日报发给我”工作流
- 在迁移到完整 Docker/VPS 部署前先试用 YPBrief

已经验证过的能力：

- 手动 workflow 可以处理 `sources.yaml` 中的固定来源
- `all_time` 加 `max_videos_per_source` 可用于最近历史视频 smoke test
- 每日日报 Markdown 会保存到 `actions-exports/daily/`
- 单视频总结会保存到 `actions-exports/videos/**/summary.md`
- 当 `TELEGRAM_CHAT_ID` 指向 bot 可访问的 chat 时，Telegram 推送可用
- GitHub-hosted runner 的 IP 可能被 YouTube 字幕访问限流或挑战，因此代理配置经常有用

如果你需要以下能力，请使用 Docker/VPS：

- Web UI 来源管理
- 长期 SQLite 历史
- 完整 transcript 和 VTT 归档
- 维护视图和手动重试工具
- 从浏览器管理多个定时任务
- 未来 Skill/MCP 服务化模式

推荐隐私模型：

- 上游项目可以保持公开。
- 真实使用时 fork 到自己的 private repository。
- API key 和 token 放到 GitHub Secrets。
- 普通默认值放到 GitHub Variables。
- 来源配置放到 private fork 的 `sources.yaml`。
- 只提交日报 Markdown 和单视频 `summary.md` 输出。

默认 ignore 规则对 Docker/VPS 使用是保守的：真实运行文件如 `sources.yaml`、`prompts.yaml`、`exports/`、`actions-exports/`、数据库、日志和密钥都会被保护，避免误提交到公开仓库。Actions workflow 会用明确 allowlist 和 `git add -f` 只提交预期文件：`sources.yaml`、可选 `prompts.yaml`、日报 Markdown 和单视频 `summary.md`。

### GitHub Actions 设置

1. 把项目 fork 到 private repository。
2. 把 `sources.example.yaml` 复制成 private fork 里的 `sources.yaml`，并编辑真实频道/播放列表。
3. 在 `Settings -> Secrets and variables -> Actions` 添加必需 Secrets。

必需 Secrets：

```text
YOUTUBE_DATA_API_KEY
LLM_PROVIDER
LLM_MODEL
GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY / ...
```

使用与你选择的 `LLM_PROVIDER` 对应的 API key。例如 `LLM_PROVIDER=grok` 应搭配 `XAI_API_KEY`；`LLM_PROVIDER=gemini` 应搭配 `GEMINI_API_KEY`。

Telegram 推送需要：

```text
TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

当 GitHub-hosted runner 抓取字幕不稳定时，推荐准备：

```text
YOUTUBE_PROXY_ENABLED
YOUTUBE_PROXY_HTTP
YOUTUBE_PROXY_HTTPS
YT_DLP_PROXY
```

Email 推送可选：

```text
EMAIL_ENABLED
SMTP_HOST
SMTP_USERNAME
SMTP_PASSWORD
EMAIL_FROM
EMAIL_TO
```

代理 secrets 原则上是可选的，但如果 GitHub Actions 抓字幕失败或不稳定，强烈建议配置。可以使用上面的通用代理 URL secrets，也可以使用拆分字段：

```text
IPROYAL_PROXY_HOST
IPROYAL_PROXY_PORT
IPROYAL_PROXY_USERNAME
IPROYAL_PROXY_PASSWORD
```

这些字段命名为 IPRoyal，是因为它是第一个测试过的服务商；本质上只是拼成普通 HTTP 代理 URL。其他代理服务商也可以通过 `YOUTUBE_PROXY_HTTP`、`YOUTUBE_PROXY_HTTPS` 和 `YT_DLP_PROXY` 配置。

最小 private `sources.yaml` 示例：

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

4. 添加可选 Variables，作为非敏感默认值：

```text
YPBRIEF_ACTIONS_TIMEZONE=Asia/Shanghai
YPBRIEF_ACTIONS_WINDOW=last_1
YPBRIEF_ACTIONS_GROUP=all
YPBRIEF_ACTIONS_LANGUAGE=zh
YPBRIEF_ACTIONS_MAX_VIDEOS_PER_SOURCE=10
```

5. 打开 `Actions -> YPBrief Daily -> Run workflow` 手动测试。
6. 如果 `sources.yaml` 或生成的总结需要保密，请保持仓库私有。

常用手动测试参数：

```text
window=last_3
group=all
language=zh
max_videos_per_source=1
dry_run=false
```

更完整的历史 smoke test：

```text
window=all_time
group=all
language=zh
max_videos_per_source=2
dry_run=false
```

workflow 文件是 `.github/workflows/github-actions-daily.yml`，运行脚本是 `scripts/github_actions_daily.py`。

如果想在推送到 GitHub 前做本地 smoke test，可以用本地 env 文件运行：

```bash
python scripts/github_actions_daily.py --env-file key.env --dry-run --window last_7 --max-videos-per-source 3
```

`--env-file key.env` 只是本地测试便利入口。在线 GitHub Actions 中，凭证仍来自 Secrets，workflow 会在运行时生成临时 `key.env`。`--dry-run` 会跳过 Telegram/Email 推送和 git commit，但仍会调用 YouTube 和配置的 LLM。

GitHub Actions Lite 会把保留的 Markdown 输出写到 `actions-exports/`，而不是 Docker/VPS 使用的 `exports/`。这样本地 smoke test、private fork Actions 输出和完整 Web UI 归档不会混在一起。

推送排错：

- 如果日志显示 `delivery telegram success`，表示 Telegram Bot API 已接受消息。
- 如果 Telegram 返回 `Bad Request: chat not found`，常见原因是 `TELEGRAM_CHAT_ID` 错误、用户没有给 bot 发送 `/start`、bot 不在目标群，或 bot 不是目标频道管理员。
- 如果 `included=0` 且没有日报内容，先检查选择的 `window` 是否真的包含新视频。测试时可以用 `last_3`、`last_7` 或 `all_time` 加较小的 `max_videos_per_source`。
- GitHub schedule 使用 UTC，且不保证精确到分钟；手动 `Run workflow` 是测试配置的最好方式。

GitHub Actions Lite 不应提交：

- `key.env`
- SQLite 数据库
- VTT 字幕文件
- 完整 transcript
- metadata 文件
- logs
- cookies
- provider key 或推送凭证

这个模式最适合固定来源日报。如果你需要 Web UI、长期 SQLite 历史、维护视图、完整 transcript 归档或未来 Skill/MCP 服务模式，请使用 Docker/VPS。

## Docker 备份和迁移

Docker 镜像不包含你的历史数据。你的持久状态保存在宿主机挂载目录：

```text
/root/ypbrief/data/      SQLite 数据库和 key.env
/root/ypbrief/exports/   VTT、transcript、summary 和日报导出
/root/ypbrief/logs/      日志
```

迁移到另一台服务器：

```bash
docker stop ypbrief
cd /root
tar -czf ypbrief-backup.tar.gz ypbrief
```

把 `ypbrief-backup.tar.gz` 复制到新服务器，然后：

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

最需要保留的文件是：

- `/root/ypbrief/data/ypbrief.db`
- `/root/ypbrief/data/key.env`
- `/root/ypbrief/exports/`

## 更新 Docker

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

重大升级前请备份 `/root/ypbrief`。

## Web UI 页面

- Dashboard：最新日报预览、最近总结和一次性 YouTube URL 总结。
- Daily Digests：手动日报生成、日报历史、详情页、复制/导出/下载、重跑和推送。
- Videos：视频列表、按频道分组浏览、阅读视图、维护视图、transcript、summary、复制/下载和手动处理。
- Sources：来源和分组管理、批量导入、导出和面向备份的来源维护。
- Prompts：单视频总结和日报总结提示词编辑。
- Automation：定时任务、来源范围、时间窗口、语言、推送设置和运行历史。
- Settings：YouTube API、代理、LLM providers/models、Telegram、Email 和访问密码轮换。

## 常用 CLI 命令

显示解析后的配置：

```bash
ypbrief --env-file key.env config
```

添加来源：

```bash
ypbrief --env-file key.env source add "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

处理单个视频：

```bash
ypbrief --env-file key.env video process "https://www.youtube.com/watch?v=VIDEO_ID"
```

总结已有视频：

```bash
ypbrief --env-file key.env summarize video VIDEO_ID
```

导出 transcript：

```bash
ypbrief --env-file key.env export transcript --video-id VIDEO_ID --format md
```

导出 summary：

```bash
ypbrief --env-file key.env export summary --video-id VIDEO_ID
```

## 运维

查看 Docker 日志：

```bash
docker logs -f ypbrief
```

重启：

```bash
docker restart ypbrief
```

本地健康检查：

```bash
curl http://127.0.0.1:48787/api/health
```

如果定时日报看起来比较慢，可以在 Automation 或 Daily Digests 页面查看运行历史。YPBrief 会在可用时复用已有单视频总结，但每次日报运行仍会让所选 LLM 基于视频总结生成新的综合日报。推理模型可能明显慢于普通聊天模型。

## 安全说明

以下内容应保持私有：

- `key.env`
- `data/`
- `exports/`
- `actions-exports/`
- `logs/`
- SQLite 数据库文件
- cookies
- 证书
- provider API key
- Telegram 和 SMTP 凭证
- 私有来源列表和自定义提示词

对于 GitHub Actions Lite，例外是 private fork：如果你接受仓库访问者能读取这些内容，可以在 `actions-exports/` 下提交日报 Markdown 和单视频 `summary.md`。不要把这些输出提交到公开仓库，除非你明确希望公开。

可以安全公开的模板：

- `key.env.example`
- `sources.example.yaml`
- `prompts.example.yaml`

公网部署建议：

- 使用强 `YPBRIEF_ACCESS_PASSWORD`。
- 需要时在 Settings 中轮换密码。
- 如果暴露到互联网，请放在你偏好的访问控制、反向代理、防火墙或服务器管理栈之后。
- 保护好 Docker volumes 和备份。

## 成本说明

YPBrief 可以以很低的基础设施成本运行：

- 对个人/小团队的元数据查询，YouTube Data API 通常在免费 quota 内。
- 代理是可选项，只在网络环境困难时需要。
- Docker 部署对典型个人使用来说可以跑在小型 VPS 上。
- 主要可变成本取决于你选择的 LLM provider/model。

对于只有几十个固定来源的个人部署，SQLite 已经足够。只有当项目演进成多用户或高吞吐服务时，才值得考虑数据库升级。
