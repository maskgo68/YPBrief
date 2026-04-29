import { type FormEvent, useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api, setAuthToken } from './api'
import type {
  AuthStatus,
  Dashboard,
  DeliveryLog,
  DeliveryResult,
  DeliverySettings,
  Digest,
  DigestRun,
  DigestTab,
  DigestVideo,
  Health,
  Language,
  LLMProvider,
  ModelProfile,
  Page,
  Prompt,
  ProxySettings,
  QuickVideoProcessResult,
  ScheduledJob,
  Source,
  SourceGroup,
  Video,
  VideoDetail,
  VideoMode,
  VideoTab,
  YoutubeSettings,
} from './types'
import './App.css'

const copy = {
  zh: {
    dashboard: '仪表盘',
    sources: '来源',
    videos: '视频',
    digests: '日报',
    prompts: '提示词',
    automation: '自动任务',
    settings: '设置',
    groups: '分组',
    group: '分组',
    ungrouped: '未分组',
    subtitle: 'YouTube 播客转录与日报控制台',
    loginTitle: '访问控制',
    loginSubtitle: '请输入 key.env 中配置的访问密码。',
    password: '访问密码',
    accessPassword: '访问密码',
    changePassword: '修改密码',
    currentPassword: '当前密码',
    newPassword: '新密码',
    confirmPassword: '确认新密码',
    passwordUpdated: '访问密码已更新，请使用新密码继续访问。',
    passwordMismatch: '两次输入的新密码不一致',
    passwordTooShort: '新密码至少需要 8 个字符',
    login: '登录',
    logout: '退出',
    loggingIn: '登录中...',
    authFailed: '密码不正确或会话已过期',
    latestDigest: '最近日报',
    digestPreview: '日报预览',
    noDigest: '还没有生成日报',
    viewDigest: '查看完整日报',
    latestRun: '最近任务',
    runWindow: '任务窗口',
    startedAt: '开始时间',
    completedAt: '完成时间',
    duration: '耗时',
    runningDuration: '已运行',
    operationalItems: '异常与跳过',
    noOperationalItems: '暂无失败或跳过条目',
    regenerateDaily: '重新生成',
    regenerating: '生成中...',
    enabledSources: '启用来源',
    totalSources: '总来源',
    totalVideos: '视频',
    summarizedVideos: '已总结视频',
    pendingVideos: '待处理视频',
    failed: '失败',
    recentVideos: '最近总结',
    sourceName: '来源名称',
    type: '类型',
    status: '状态',
    actions: '操作',
    enabled: '启用',
    disabled: '禁用',
    disable: '禁用',
    enable: '启用',
    active: '当前启用',
    health: '健康状态',
    configured: '已配置',
    missing: '缺失',
    digestHistory: '日报历史',
    videoLibrary: '视频总结库',
    listView: '列表视图',
    channelView: '频道视图',
    showAllVideos: '展开全部',
    showLessVideos: '收起',
    readingView: '阅读视图',
    maintenanceView: '维护视图',
    needsAttention: '需要处理',
    noSummaries: '还没有已总结视频',
    quickVideoSummary: '临时视频总结',
    quickVideoHint: '粘贴一个 YouTube 视频链接，立即抓字幕并生成单篇总结，不会加入来源列表。',
    quickVideoInput: 'YouTube 视频链接',
    quickVideoPlaceholder: 'https://www.youtube.com/watch?v=...',
    quickVideoLanguage: '总结语言',
    quickVideoLanguageAuto: '跟随视频',
    summarizeVideo: '开始总结',
    processingVideo: '处理中...',
    deliverAfterSummary: '完成后推送',
    pushTelegram: 'Telegram',
    pushEmail: 'Email',
    deliver: '推送',
    delivering: '推送中...',
    deliveryComplete: '推送完成',
    selectDeliveryChannel: '请选择至少一个推送渠道',
    openVideoDetail: '打开视频详情',
    reusedSummary: '已复用现有总结',
    summarizedNow: '已生成新总结',
    noSummary: '暂无总结',
    showMaintenanceHint: '维护视图会显示未处理、失败、原始字幕和技术字段。',
    add: '添加',
    delete: '删除',
    edit: '编辑',
    save: '保存',
    cancel: '取消',
    modelProfiles: '模型配置',
    currentModel: '当前总结模型',
    providerKeys: 'API Key 状态',
    providers: '供应商配置',
    addProvider: '添加供应商',
    test: '测试',
    providerType: '供应商类型',
    baseUrl: 'Base URL',
    apiKey: 'API Key',
    defaultModel: '默认模型',
    configSource: '配置来源',
    testYoutube: '测试 YouTube API',
    testLlm: '测试 LLM API',
    testProxy: '测试代理',
    testDatabase: '测试数据库',
    proxySettings: '代理配置',
    youtubeSettings: 'YouTube API 配置',
    schedulerSettings: '自动日报',
    automationJobs: '自动任务',
    addJob: '添加任务',
    jobName: '任务名称',
    windowMode: '时间范围',
    deliveryChannels: '推送渠道',
    runHistory: '运行记录',
    runSubmitted: '任务已提交，正在后台运行；完成后会出现在运行记录中。',
    deliverySettings: '消息渠道',
    telegramDelivery: 'Telegram 推送',
    emailDelivery: 'Email 推送',
    runNow: '立即运行',
    runTime: '运行时间',
    timezone: '时区',
    digestLanguage: '日报语言',
    sourceScope: '来源范围',
    selectedSources: '指定来源',
    selectedGroups: '指定分组',
    maxVideosPerSource: '每个来源最多视频',
    limitVideos: '限制每源视频数',
    unlimitedVideos: '不限额',
    copied: '已复制',
    downloaded: '已下载',
    noMarkdown: '没有可复制的 Markdown 内容',
    sendEmptyDigest: '无更新也推送',
    processMissingVideos: '自动处理缺失总结',
    retryFailedOnce: '失败重试一次',
    testTelegram: '测试 Telegram',
    testEmail: '测试 Email',
    deliveryLogs: '推送记录',
    showLogs: '展开记录',
    hideLogs: '收起记录',
    botToken: 'Bot Token',
    chatId: 'Chat ID',
    smtpHost: 'SMTP Host',
    smtpPort: 'SMTP Port',
    smtpUsername: 'SMTP 用户名',
    smtpPassword: 'SMTP 密码',
    emailFrom: '发件人',
    emailTo: '收件人',
    subjectTemplate: '邮件标题模板',
    youtubeApiKey: 'YouTube API Key',
    apiKeyHint: '当前 Key',
    proxyEnabled: '启用代理',
    proxyStatus: '代理状态',
    proxyEffective: '有效代理',
    proxyYtDlp: 'yt-dlp 代理',
    videoPrompt: '单视频总结提示词',
    dailyPrompt: '每日总结提示词',
    generateDigest: '生成日报',
    scopeAll: '全部启用来源',
    windowDays: '时间窗口',
    last1: '最近 1 天',
    last3: '最近 3 天',
    last7: '最近 7 天',
    customRange: '自定义日期',
    allTime: '全部历史',
    runResult: '任务结果',
    detail: '详情',
    process: '完整处理',
    summarize: '重新总结',
    copySummary: '复制总结',
    downloadSummary: '下载总结',
    copyTranscript: '复制转录',
    downloadTranscript: '下载转录',
    operationRunning: '处理中...',
    processComplete: '处理完成，已生成总结',
    summarizeComplete: '重新总结完成，已生成总结',
    operationComplete: '操作完成',
    openYoutube: '打开 YouTube',
    summary: '总结',
    transcript: '转录',
    sourceVtt: '原始 VTT',
    metadata: '元数据',
    included: '包含视频',
    copyMarkdown: '复制 Markdown',
    exportMarkdown: '导出 Markdown',
    promptPreview: '预览渲染',
    resetDefault: '恢复默认',
    activate: '启用版本',
    variables: '可用变量',
    sourceType: '来源类型',
    displayName: '显示名称',
    bulkAddSources: '批量添加来源',
    bulkSourceText: '每行一个 YouTube 频道或播放列表 URL；空行和 # 注释会被忽略。',
    bulkDefaultGroup: '默认分组',
    bulkUploadTxt: '上传 TXT',
    bulkImport: '批量导入',
    bulkResult: '导入结果',
    bulkCreated: '新增',
    bulkDuplicate: '重复',
    bulkFailed: '失败',
    bulkIgnored: '忽略',
    sourceGroupFilter: '查看分组',
    visibleSources: '当前显示',
    bulkMoveToGroup: '批量移动到',
    assignGroup: '移动到分组',
    removeGroup: '移出分组',
    importYaml: '导入 YAML',
    saveYaml: '保存 YAML',
    exportYaml: '导出 YAML',
    globalScope: '全局',
    promptScope: '提示词范围',
    filters: '筛选',
    all: '全部',
    hasSummary: '有总结',
    transcriptFilter: '转录',
    hasTranscript: '有转录',
    noTranscript: '无转录',
    dateFrom: '开始日期',
    dateTo: '结束日期',
    retry: '重试',
    summaryMeta: '总结信息',
    pipelineMeta: '处理信息',
    sourceMeta: '来源信息',
    keyword: '关键词',
    statusNew: '未处理',
    statusCleaned: '已清洗转录',
    statusSummarized: '已总结',
    statusFailed: '失败',
    statusSkipped: '已跳过',
    statusHelp: 'new=只发现视频；cleaned=已抓字幕并清洗；summarized=已生成总结。',
  },
  en: {
    dashboard: 'Dashboard',
    sources: 'Sources',
    videos: 'Videos',
    digests: 'Digests',
    prompts: 'Prompts',
    automation: 'Automation',
    settings: 'Settings',
    groups: 'Groups',
    group: 'Group',
    ungrouped: 'Ungrouped',
    subtitle: 'YouTube podcast transcript and digest console',
    loginTitle: 'Access Control',
    loginSubtitle: 'Enter the access password configured in key.env.',
    password: 'Access password',
    accessPassword: 'Access Password',
    changePassword: 'Change Password',
    currentPassword: 'Current password',
    newPassword: 'New password',
    confirmPassword: 'Confirm new password',
    passwordUpdated: 'Access password updated. Use the new password from now on.',
    passwordMismatch: 'The new passwords do not match',
    passwordTooShort: 'New password must be at least 8 characters',
    login: 'Log in',
    logout: 'Log out',
    loggingIn: 'Logging in...',
    authFailed: 'Invalid password or expired session',
    latestDigest: 'Latest Digest',
    digestPreview: 'Digest Preview',
    noDigest: 'No digest generated yet',
    viewDigest: 'View full digest',
    latestRun: 'Latest Run',
    runWindow: 'Run Window',
    startedAt: 'Started',
    completedAt: 'Completed',
    duration: 'Duration',
    runningDuration: 'Running for',
    operationalItems: 'Failures and Skips',
    noOperationalItems: 'No failed or skipped items',
    regenerateDaily: 'Regenerate',
    regenerating: 'Regenerating...',
    enabledSources: 'Enabled Sources',
    totalSources: 'Sources',
    totalVideos: 'Videos',
    summarizedVideos: 'Summarized',
    pendingVideos: 'Pending',
    failed: 'Failed',
    recentVideos: 'Recent Summaries',
    sourceName: 'Source Name',
    type: 'Type',
    status: 'Status',
    actions: 'Actions',
    enabled: 'Enabled',
    disabled: 'Disabled',
    disable: 'Disable',
    enable: 'Enable',
    active: 'Active',
    health: 'Health',
    configured: 'Configured',
    missing: 'Missing',
    digestHistory: 'Digest History',
    videoLibrary: 'Video Summary Library',
    listView: 'List View',
    channelView: 'Channel View',
    showAllVideos: 'Show all',
    showLessVideos: 'Show less',
    readingView: 'Reading View',
    maintenanceView: 'Maintenance View',
    needsAttention: 'Needs Attention',
    noSummaries: 'No summarized videos yet',
    quickVideoSummary: 'Quick Video Summary',
    quickVideoHint: 'Paste one YouTube URL to fetch the transcript and summarize it once. It will not be added to Sources.',
    quickVideoInput: 'YouTube video URL',
    quickVideoPlaceholder: 'https://www.youtube.com/watch?v=...',
    quickVideoLanguage: 'Summary language',
    quickVideoLanguageAuto: 'Match video',
    summarizeVideo: 'Summarize',
    processingVideo: 'Processing...',
    deliverAfterSummary: 'Deliver after summary',
    pushTelegram: 'Telegram',
    pushEmail: 'Email',
    deliver: 'Deliver',
    delivering: 'Delivering...',
    deliveryComplete: 'Delivery complete',
    selectDeliveryChannel: 'Select at least one delivery channel',
    openVideoDetail: 'Open video detail',
    reusedSummary: 'Reused existing summary',
    summarizedNow: 'Created new summary',
    noSummary: 'No summary yet',
    showMaintenanceHint: 'Maintenance view shows unprocessed, failed, raw transcript, and technical fields.',
    add: 'Add',
    delete: 'Delete',
    edit: 'Edit',
    save: 'Save',
    cancel: 'Cancel',
    modelProfiles: 'Model Profiles',
    currentModel: 'Current Summary Model',
    providerKeys: 'API Key Status',
    providers: 'Providers',
    addProvider: 'Add Provider',
    test: 'Test',
    providerType: 'Provider Type',
    baseUrl: 'Base URL',
    apiKey: 'API Key',
    defaultModel: 'Default Model',
    configSource: 'Config Source',
    testYoutube: 'Test YouTube API',
    testLlm: 'Test LLM API',
    testProxy: 'Test Proxy',
    testDatabase: 'Test Database',
    proxySettings: 'Proxy Settings',
    youtubeSettings: 'YouTube API Settings',
    schedulerSettings: 'Automatic Digest',
    automationJobs: 'Automation Jobs',
    addJob: 'Add Job',
    jobName: 'Job name',
    windowMode: 'Window',
    deliveryChannels: 'Delivery channels',
    runHistory: 'Run history',
    runSubmitted: 'Job submitted and running in the background. The result will appear in run history.',
    deliverySettings: 'Message Channels',
    telegramDelivery: 'Telegram Delivery',
    emailDelivery: 'Email Delivery',
    runNow: 'Run Now',
    runTime: 'Run time',
    timezone: 'Timezone',
    digestLanguage: 'Digest language',
    sourceScope: 'Source scope',
    selectedSources: 'Selected sources',
    selectedGroups: 'Selected groups',
    maxVideosPerSource: 'Max videos per source',
    limitVideos: 'Limit videos per source',
    unlimitedVideos: 'Unlimited',
    copied: 'Copied',
    downloaded: 'Downloaded',
    noMarkdown: 'No Markdown content to copy',
    sendEmptyDigest: 'Send no-update notice',
    processMissingVideos: 'Process missing summaries',
    retryFailedOnce: 'Retry failed once',
    testTelegram: 'Test Telegram',
    testEmail: 'Test Email',
    deliveryLogs: 'Delivery Logs',
    showLogs: 'Show logs',
    hideLogs: 'Hide logs',
    botToken: 'Bot Token',
    chatId: 'Chat ID',
    smtpHost: 'SMTP Host',
    smtpPort: 'SMTP Port',
    smtpUsername: 'SMTP username',
    smtpPassword: 'SMTP password',
    emailFrom: 'From',
    emailTo: 'Recipients',
    subjectTemplate: 'Subject template',
    youtubeApiKey: 'YouTube API Key',
    apiKeyHint: 'Current key',
    proxyEnabled: 'Enable proxy',
    proxyStatus: 'Proxy status',
    proxyEffective: 'Effective proxy',
    proxyYtDlp: 'yt-dlp proxy',
    videoPrompt: 'Video Summary Prompt',
    dailyPrompt: 'Daily Digest Prompt',
    generateDigest: 'Generate Digest',
    scopeAll: 'All enabled sources',
    windowDays: 'Window',
    last1: 'Last 1 day',
    last3: 'Last 3 days',
    last7: 'Last 7 days',
    customRange: 'Custom range',
    allTime: 'All history',
    runResult: 'Run Result',
    detail: 'Detail',
    process: 'Full process',
    summarize: 'Re-summarize',
    copySummary: 'Copy summary',
    downloadSummary: 'Download summary',
    copyTranscript: 'Copy transcript',
    downloadTranscript: 'Download transcript',
    operationRunning: 'Processing...',
    processComplete: 'Processing complete, summary generated',
    summarizeComplete: 'Re-summary complete, summary generated',
    operationComplete: 'Operation complete',
    openYoutube: 'Open YouTube',
    summary: 'Summary',
    transcript: 'Transcript',
    sourceVtt: 'Source VTT',
    metadata: 'Metadata',
    included: 'Included',
    copyMarkdown: 'Copy Markdown',
    exportMarkdown: 'Export Markdown',
    promptPreview: 'Preview Render',
    resetDefault: 'Reset Defaults',
    activate: 'Activate',
    variables: 'Variables',
    sourceType: 'Source type',
    displayName: 'Display name',
    bulkAddSources: 'Bulk Add Sources',
    bulkSourceText: 'One YouTube channel or playlist URL per line. Blank lines and # comments are ignored.',
    bulkDefaultGroup: 'Default group',
    bulkUploadTxt: 'Upload TXT',
    bulkImport: 'Bulk Import',
    bulkResult: 'Import result',
    bulkCreated: 'Created',
    bulkDuplicate: 'Duplicates',
    bulkFailed: 'Failed',
    bulkIgnored: 'Ignored',
    sourceGroupFilter: 'View group',
    visibleSources: 'Visible',
    bulkMoveToGroup: 'Move selected to',
    assignGroup: 'Assign group',
    removeGroup: 'Remove group',
    importYaml: 'Import YAML',
    saveYaml: 'Save YAML',
    exportYaml: 'Export YAML',
    globalScope: 'Global',
    promptScope: 'Prompt Scope',
    filters: 'Filters',
    all: 'All',
    hasSummary: 'Has summary',
    transcriptFilter: 'Transcript',
    hasTranscript: 'Has transcript',
    noTranscript: 'No transcript',
    dateFrom: 'Start date',
    dateTo: 'End date',
    retry: 'Retry',
    summaryMeta: 'Summary info',
    pipelineMeta: 'Pipeline info',
    sourceMeta: 'Source info',
    keyword: 'Keyword',
    statusNew: 'New',
    statusCleaned: 'Transcript cleaned',
    statusSummarized: 'Summarized',
    statusFailed: 'Failed',
    statusSkipped: 'Skipped',
    statusHelp: 'new=metadata only; cleaned=transcript fetched and cleaned; summarized=summary generated.',
  },
}

async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Fall through to the textarea fallback for non-HTTPS or restricted browsers.
    }
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

type DeliveryChannels = {
  telegram: boolean
  email: boolean
}

async function deliverSummary(summaryId: number, channels: DeliveryChannels): Promise<DeliveryResult[]> {
  const result = await api<{ deliveries: DeliveryResult[] }>(`/summaries/${summaryId}/deliver`, {
    method: 'POST',
    body: JSON.stringify({
      telegram_enabled: channels.telegram,
      email_enabled: channels.email,
    }),
  })
  return result.deliveries || []
}

function deliveryStatusText(deliveries: DeliveryResult[], t: typeof copy.zh) {
  if (!deliveries.length) return t.noOperationalItems
  return `${t.deliveryComplete}: ${deliveries.map((item) => `${item.channel} ${item.status}`).join(', ')}`
}

function videoOperationStatusText(path: string, result: Record<string, string | number>, t: typeof copy.zh) {
  const summaryId = result.summary_id ? ` #${result.summary_id}` : ''
  if (path.endsWith('/process')) return `${t.processComplete}${summaryId}`
  if (path.endsWith('/summarize')) return `${t.summarizeComplete}${summaryId}`
  return t.operationComplete
}

function safeFilenamePart(value?: string | null) {
  return (value || 'untitled')
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120)
}

function transcriptMarkdownFilename(video: VideoDetail) {
  return `${safeFilenamePart(video.channel_name)} - ${safeFilenamePart(video.video_title)} - ${safeFilenamePart(video.video_date || 'unknown-date')} - ${safeFilenamePart(video.video_id)} - transcript.md`
}

function summaryMarkdownFilename(video: VideoDetail) {
  return `${safeFilenamePart(video.channel_name)} - ${safeFilenamePart(video.video_title)} - ${safeFilenamePart(video.video_date || 'unknown-date')} - ${safeFilenamePart(video.video_id)} - summary.md`
}

function cleanLabel(value?: string | null) {
  return (value || '').trim()
}

function groupLabel(group: SourceGroup) {
  return cleanLabel(group.display_name) || cleanLabel(group.group_name)
}

function sourceGroupLabel(source: Source, fallback: string) {
  return cleanLabel(source.group_display_name) || cleanLabel(source.group_name) || fallback
}

type SourceBulkAddResult = {
  created: Source[]
  duplicates: Array<{ line: number; input: string; reason: string; source?: Source }>
  failed: Array<{ line: number; input: string; error: string }>
  ignored: number
}

function formatRunWindow(run: DigestRun | null | undefined, t: typeof copy.zh) {
  if (!run) return '-'
  if (!run.window_start) {
    return run.window_end ? `${t.allTime} -> ${run.window_end}` : t.allTime
  }
  return `${run.window_start} -> ${run.window_end || '-'}`
}

function compactDateTime(value?: string | null) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 16)
}

function parseDateTime(value?: string | null) {
  if (!value) return null
  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const parsed = new Date(normalized.endsWith('Z') || /[+-]\d\d:\d\d$/.test(normalized) ? normalized : `${normalized}Z`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function formatDurationMs(ms: number, t: typeof copy.zh) {
  const totalSeconds = Math.max(0, Math.round(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (t === copy.zh) {
    if (hours) return `${hours}小时${minutes}分${seconds}秒`
    if (minutes) return `${minutes}分${seconds}秒`
    return `${seconds}秒`
  }
  if (hours) return `${hours}h ${minutes}m ${seconds}s`
  if (minutes) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

function runDuration(run: DigestRun | null | undefined, t: typeof copy.zh) {
  const started = parseDateTime(run?.created_at)
  if (!started) return '-'
  const ended = parseDateTime(run?.completed_at) || new Date()
  return formatDurationMs(ended.getTime() - started.getTime(), t)
}

function digestDisplayTitle(digest: Digest, t: typeof copy.zh) {
  const jobName = cleanLabel(digest.scheduled_job_name)
  const date = digest.range_start || digest.latest_run_window_end || `#${digest.summary_id}`
  if (jobName) return `${jobName} · ${date}`
  if (digest.latest_run_type === 'scheduled' || digest.latest_run_type === 'scheduled_manual') return `${t.automationJobs} · ${date}`
  return `${t.generateDigest} · ${date}`
}

function digestDisplayMeta(digest: Digest) {
  const included = digest.latest_run_included_count ?? digest.included_count ?? 0
  const failed = digest.latest_run_failed_count ?? digest.failed_count ?? 0
  const skipped = digest.latest_run_skipped_count ?? digest.skipped_count ?? 0
  const created = compactDateTime(digest.latest_run_completed_at || digest.latest_run_created_at || digest.created_at)
  return `${included} videos · failed ${failed} · skipped ${skipped} · ${created}`
}

function runDisplayTitle(run: DigestRun, fallbackJobName?: string) {
  const name = cleanLabel(run.scheduled_job_name) || cleanLabel(fallbackJobName) || 'Scheduled Job'
  return `${name} · ${run.window_end || run.run_id}`
}

function runDisplayMeta(run: DigestRun, t: typeof copy.zh) {
  const durationLabel = run.completed_at ? t.duration : t.runningDuration
  return `${run.status} · ${formatRunWindow(run, t)} · ${t.startedAt}: ${compactDateTime(run.created_at)} · ${t.completedAt}: ${compactDateTime(run.completed_at)} · ${durationLabel}: ${runDuration(run, t)} · included ${run.included_count} · failed ${run.failed_count} · skipped ${run.skipped_count}`
}

type DateInputProps = {
  value: string
  onChange: (value: string) => void
  ariaLabel?: string
  title?: string
}

function DateInput({ value, onChange, ariaLabel, title }: DateInputProps) {
  return (
    <input
      type="date"
      lang="en-CA"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={ariaLabel}
      title={title}
    />
  )
}

function App() {
  const [language, setLanguage] = useState<Language>(() => (localStorage.getItem('ypbrief-lang') as Language) || 'zh')
  const [page, setPage] = useState<Page>('dashboard')
  const [auth, setAuth] = useState<AuthStatus>({ auth_required: false, authenticated: false })
  const [authChecked, setAuthChecked] = useState(false)
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [groups, setGroups] = useState<SourceGroup[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [digests, setDigests] = useState<Digest[]>([])
  const [prompts, setPrompts] = useState<Prompt[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [models, setModels] = useState<ModelProfile[]>([])
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [proxySettings, setProxySettings] = useState<ProxySettings | null>(null)
  const [youtubeSettings, setYoutubeSettings] = useState<YoutubeSettings | null>(null)
  const [scheduledJobs, setScheduledJobs] = useState<ScheduledJob[]>([])
  const [deliverySettings, setDeliverySettings] = useState<DeliverySettings | null>(null)
  const [deliveryLogs, setDeliveryLogs] = useState<DeliveryLog[]>([])
  const [selectedDigest, setSelectedDigest] = useState<Digest | null>(null)
  const [selectedVideoId, setSelectedVideoId] = useState('')
  const [selectedVideoMode, setSelectedVideoMode] = useState<VideoMode | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const [error, setError] = useState('')
  const t = copy[language]

  const checkAuth = async () => {
    try {
      const status = await api<AuthStatus>('/auth/status')
      setAuth(status)
      setAuthChecked(true)
      if (!status.auth_required || status.authenticated) await load()
    } catch (exc) {
      setAuth({ auth_required: true, authenticated: false })
      setAuthChecked(true)
      setError(exc instanceof Error ? exc.message : String(exc))
    }
  }

  const load = async () => {
    setError('')
    try {
      const [dashboardData, sourceData, groupData, videoData, digestData, promptData, healthData, modelData, providerData, proxyData, youtubeData, jobData, deliveryData, deliveryLogData] = await Promise.all([
        api<Dashboard>('/dashboard'),
        api<Source[]>('/sources'),
        api<SourceGroup[]>('/source-groups'),
        api<Video[]>('/videos'),
        api<Digest[]>('/digests'),
        api<Prompt[]>('/prompts'),
        api<Health>('/health'),
        api<ModelProfile[]>('/model-profiles'),
        api<LLMProvider[]>('/llm-providers'),
        api<ProxySettings>('/proxy-settings'),
        api<YoutubeSettings>('/youtube-settings'),
        api<ScheduledJob[]>('/scheduled-jobs'),
        api<DeliverySettings>('/delivery-settings'),
        api<DeliveryLog[]>('/delivery-logs'),
      ])
      setDashboard(dashboardData)
      setSources(sourceData)
      setGroups(groupData)
      setVideos(videoData)
      setDigests(digestData)
      setPrompts(promptData)
      setHealth(healthData)
      setModels(modelData)
      setProviders(providerData)
      setProxySettings(proxyData)
      setYoutubeSettings(youtubeData)
      setScheduledJobs(jobData)
      setDeliverySettings(deliveryData)
      setDeliveryLogs(deliveryLogData)
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc)
      setError(message)
      if (message.includes('Authentication required')) {
        setAuth((current) => ({ ...current, auth_required: true, authenticated: false }))
      }
    }
  }

  useEffect(() => {
    localStorage.setItem('ypbrief-lang', language)
  }, [language])

  useEffect(() => {
    checkAuth()
    const onAuthRequired = () => setAuth((current) => ({ ...current, auth_required: true, authenticated: false }))
    window.addEventListener('ypbrief-auth-required', onAuthRequired)
    return () => window.removeEventListener('ypbrief-auth-required', onAuthRequired)
  }, [])

  const handleLogin = async (password: string) => {
    const result = await api<{ token: string; auth_required: boolean }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
    setAuthToken(result.token || '')
    const next = { auth_required: result.auth_required, authenticated: true }
    setAuth(next)
    await load()
  }

  const handleLogout = () => {
    setAuthToken('')
    setAuth((current) => ({ ...current, authenticated: false }))
  }

  const nav = useMemo(
    () => [
      ['dashboard', t.dashboard],
      ['digests', t.digests],
      ['videos', t.videos],
      ['sources', t.sources],
      ['prompts', t.prompts],
      ['automation', t.automation],
      ['settings', t.settings],
    ] as Array<[Page, string]>,
    [t],
  )

  const toggleSource = async (source: Source) => {
    setError('')
    await api(`/sources/${source.source_id}/${source.enabled ? 'disable' : 'enable'}`, { method: 'POST' })
    await load()
  }

  const handleRefresh = async () => {
    setError('')
    await load()
    setRefreshTick((current) => current + 1)
  }

  if (!authChecked) {
    return <div className="login-screen"><div className="login-card"><strong>YPBrief</strong><span>Loading...</span></div></div>
  }

  if (auth.auth_required && !auth.authenticated) {
    return <LoginView t={t} language={language} onLanguage={setLanguage} onLogin={handleLogin} />
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">Y</div>
          <div>
            <strong>YPBrief</strong>
            <span>{t.subtitle}</span>
          </div>
        </div>
        <nav>
          {nav.map(([key, label]) => (
            <button key={key} className={page === key ? 'nav active' : 'nav'} onClick={() => setPage(key)}>
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{nav.find(([key]) => key === page)?.[1]}</h1>
            <p>{health ? `${health.llm_provider || 'LLM'} / ${health.llm_model || 'default model'}` : 'Loading'}</p>
          </div>
          <div className="toolbar">
            <button className="ghost" onClick={handleRefresh}>Refresh</button>
            {auth.auth_required ? <button className="ghost" onClick={handleLogout}>{t.logout}</button> : null}
            <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </div>
        </header>

        {error ? <div className="notice">{error}</div> : null}
        {page === 'dashboard' && <DashboardView data={dashboard} t={t} onViewDigest={(digest) => { setSelectedDigest(digest); setPage('digests') }} onOpenVideo={(videoId) => { setSelectedVideoId(videoId); setSelectedVideoMode(null); setPage('videos') }} onChanged={load} />}
        {page === 'sources' && <SourcesView sources={sources} groups={groups} refreshTick={refreshTick} t={t} onToggle={toggleSource} onChanged={load} />}
        {page === 'videos' && <VideosView videos={videos} sources={sources} selectedVideoId={selectedVideoId} selectedVideoMode={selectedVideoMode} refreshTick={refreshTick} t={t} onChanged={load} />}
        {page === 'digests' && <DigestsView digests={digests} sources={sources} groups={groups} selected={selectedDigest} refreshTick={refreshTick} t={t} onSelect={setSelectedDigest} onOpenVideo={(videoId, mode) => { setSelectedVideoId(videoId); setSelectedVideoMode(mode || null); setPage('videos') }} onChanged={load} />}
        {page === 'prompts' && <PromptsView prompts={prompts} groups={groups} refreshTick={refreshTick} t={t} onChanged={load} />}
        {page === 'automation' && <AutomationView jobs={scheduledJobs} sources={sources} groups={groups} deliveryLogs={deliveryLogs} refreshTick={refreshTick} t={t} onChanged={load} />}
        {page === 'settings' && <SettingsView health={health} models={models} providers={providers} proxySettings={proxySettings} youtubeSettings={youtubeSettings} deliverySettings={deliverySettings} refreshTick={refreshTick} t={t} onChanged={load} />}
      </main>
    </div>
  )
}

function LoginView({
  t,
  language,
  onLanguage,
  onLogin,
}: {
  t: typeof copy.zh
  language: Language
  onLanguage: (language: Language) => void
  onLogin: (password: string) => Promise<void>
}) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onLogin(password)
    } catch {
      setError(t.authFailed)
    } finally {
      setLoading(false)
    }
  }
  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="brand login-brand">
          <div className="mark">Y</div>
          <div>
            <strong>YPBrief</strong>
            <span>{t.subtitle}</span>
          </div>
        </div>
        <div>
          <h1>{t.loginTitle}</h1>
          <p>{t.loginSubtitle}</p>
        </div>
        <label className="form-field wide">
          <span>{t.password}</span>
          <input
            autoFocus
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? <div className="notice compact">{error}</div> : null}
        <div className="login-actions">
          <button disabled={!password.trim() || loading}>{loading ? t.loggingIn : t.login}</button>
          <select className="login-language" value={language} onChange={(event) => onLanguage(event.target.value as Language)}>
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </div>
      </form>
    </div>
  )
}

function DashboardView({
  data,
  t,
  onViewDigest,
  onOpenVideo,
  onChanged,
}: {
  data: Dashboard | null
  t: typeof copy.zh
  onViewDigest: (digest: Digest) => void
  onOpenVideo: (videoId: string) => void
  onChanged: () => void
}) {
  const digest = data?.latest_digest
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState('')
  const [retrying, setRetrying] = useState('')
  const [quickUrl, setQuickUrl] = useState('')
  const [quickBusy, setQuickBusy] = useState(false)
  const [quickResult, setQuickResult] = useState<QuickVideoProcessResult | null>(null)
  const [quickMessage, setQuickMessage] = useState('')
  const [quickDelivery, setQuickDelivery] = useState<DeliveryChannels>({ telegram: false, email: false })
  const [quickLanguage, setQuickLanguage] = useState<'auto' | 'zh' | 'en'>('auto')
  const regenerate = async () => {
    if (!digest) return
    setRunning(true)
    setMessage('')
    try {
      const result = await api<DigestRun>(`/digests/${digest.summary_id}/regenerate`, { method: 'POST' })
      setMessage(`#${result.run_id} · ${result.status} · included ${result.included_count}`)
      await onChanged()
    } finally {
      setRunning(false)
    }
  }
  const retryRunVideo = async (row: DigestVideo) => {
    if (!row.run_id) return
    setRetrying(`${row.run_id}-${row.video_id}-${row.source_id || ''}`)
    setMessage('')
    try {
      const query = row.source_id ? `?source_id=${row.source_id}` : ''
      const result = await api<DigestVideo & { run: DigestRun }>(`/digest-runs/${row.run_id}/videos/${row.video_id}/retry${query}`, { method: 'POST' })
      setMessage(`${result.video_title || result.video_id} · ${result.status}`)
      await onChanged()
    } catch (exc) {
      setMessage(errorMessage(exc))
    } finally {
      setRetrying('')
    }
  }
  const processQuickVideo = async (event: FormEvent) => {
    event.preventDefault()
    const videoUrl = quickUrl.trim()
    if (!videoUrl) return
    setQuickBusy(true)
    setQuickMessage('')
    setQuickResult(null)
    try {
      const result = await api<QuickVideoProcessResult>('/videos/process-url', {
        method: 'POST',
        body: JSON.stringify({ video_url: videoUrl, output_language: quickLanguage }),
      })
      setQuickResult(result)
      let nextMessage = result.reused ? t.reusedSummary : t.summarizedNow
      if (result.summary_id && (quickDelivery.telegram || quickDelivery.email)) {
        const deliveries = await deliverSummary(result.summary_id, quickDelivery)
        nextMessage = `${nextMessage} · ${deliveryStatusText(deliveries, t)}`
      }
      setQuickMessage(nextMessage)
      await onChanged()
    } catch (exc) {
      setQuickMessage(errorMessage(exc))
    } finally {
      setQuickBusy(false)
    }
  }
  return (
    <section className="grid dashboard-grid">
      <div className="metric"><span>{t.totalSources}</span><strong>{data?.stats.sources ?? '-'}</strong></div>
      <div className="metric"><span>{t.enabledSources}</span><strong>{data?.stats.enabled_sources ?? '-'}</strong></div>
      <div className="metric"><span>{t.summarizedVideos}</span><strong>{data?.stats.summarized_videos ?? '-'}</strong></div>
      <div className="metric"><span>{t.pendingVideos}</span><strong>{data?.stats.pending_videos ?? '-'}</strong></div>
      <article className="panel digest-panel">
        <div className="panel-title">
          <h2>{t.latestDigest}</h2>
          <div className="actions">
            {digest ? <button className="ghost" disabled={running} onClick={regenerate}>{running ? t.regenerating : t.regenerateDaily}</button> : null}
            {digest ? <button onClick={() => onViewDigest(digest)}>{t.viewDigest}</button> : null}
          </div>
        </div>
        {message ? <div className="notice compact neutral">{message}</div> : null}
        {digest ? (
          <>
            <div className="digest-meta">{digest.range_start} · {digest.model_provider} · {digest.model_name}</div>
            <div className="section-label">{t.digestPreview}</div>
            <div className="markdown-preview"><ReactMarkdown>{digest.preview || ''}</ReactMarkdown></div>
          </>
        ) : <p>{t.noDigest}</p>}
      </article>
      <div className="dashboard-side">
        <article className="panel quick-video-panel">
          <div className="panel-title compact-title">
            <h2>{t.quickVideoSummary}</h2>
          </div>
          <p className="digest-meta">{t.quickVideoHint}</p>
          <form className="quick-video-form" onSubmit={processQuickVideo}>
            <label className="form-field wide">
              <span>{t.quickVideoInput}</span>
              <input
                value={quickUrl}
                placeholder={t.quickVideoPlaceholder}
                onChange={(event) => setQuickUrl(event.target.value)}
              />
            </label>
            <DeliveryChannelPicker
              label={t.deliverAfterSummary}
              channels={quickDelivery}
              onChange={setQuickDelivery}
              t={t}
            />
            <label className="form-field quick-language-field">
              <span>{t.quickVideoLanguage}</span>
              <select value={quickLanguage} onChange={(event) => setQuickLanguage(event.target.value as 'auto' | 'zh' | 'en')}>
                <option value="auto">{t.quickVideoLanguageAuto}</option>
                <option value="zh">中文</option>
                <option value="en">English</option>
              </select>
            </label>
            <div className="actions quick-video-actions">
              <button disabled={quickBusy || !quickUrl.trim()}>{quickBusy ? t.processingVideo : t.summarizeVideo}</button>
              {quickResult ? (
                <button className="ghost" type="button" onClick={() => onOpenVideo(quickResult.video_id)}>
                  {t.openVideoDetail}
                </button>
              ) : null}
            </div>
          </form>
          {quickMessage ? <div className={`notice compact ${quickResult ? 'neutral' : ''}`}>{quickMessage}</div> : null}
        </article>
        <article className="panel recent-panel">
          <h2>{t.recentVideos}</h2>
          {(data?.recent_videos || []).length ? <CompactVideoList videos={data?.recent_videos || []} t={t} onOpen={onOpenVideo} /> : <p>{t.noSummaries}</p>}
        </article>
      </div>
      <article className="panel ops-panel">
        <h2>{t.latestRun}</h2>
        {data?.latest_run ? (
          <div className="ops-stack">
            <span className={data.latest_run.status === 'completed' ? 'pill ok' : 'pill'}>{data.latest_run.status}</span>
            <div className="run-counters">
              <strong>{data.latest_run.included_count}</strong><span>included</span>
              <strong>{data.latest_run.failed_count}</strong><span>failed</span>
              <strong>{data.latest_run.skipped_count}</strong><span>skipped</span>
            </div>
            <p className="digest-meta">{t.runWindow}: {formatRunWindow(data.latest_run, t)}</p>
            <p className="digest-meta">{t.startedAt}: {compactDateTime(data.latest_run.created_at)}</p>
            <p className="digest-meta">{t.completedAt}: {compactDateTime(data.latest_run.completed_at)}</p>
            <p className="digest-meta">{data.latest_run.completed_at ? t.duration : t.runningDuration}: {runDuration(data.latest_run, t)}</p>
            {data.latest_run.error_message ? <div className="notice compact">{data.latest_run.error_message}</div> : null}
          </div>
        ) : <p>{t.noDigest}</p>}
      </article>
      <article className="panel ops-panel">
        <h2>{t.needsAttention}</h2>
        {(data?.recent_run_videos || []).length ? (
          <details className="ops-details">
            <summary>{data?.recent_run_videos.length} {t.needsAttention}</summary>
            <RunVideoList rows={data?.recent_run_videos || []} onRetry={retryRunVideo} retryingKey={retrying} retryLabel={t.retry} />
          </details>
        ) : <p>{t.noOperationalItems}</p>}
      </article>
    </section>
  )
}

function SourcesView({
  sources,
  groups,
  refreshTick,
  t,
  onToggle,
  onChanged,
}: {
  sources: Source[]
  groups: SourceGroup[]
  refreshTick: number
  t: typeof copy.zh
  onToggle: (source: Source) => Promise<void>
  onChanged: () => void
}) {
  const [sourceInput, setSourceInput] = useState('')
  const [sourceType, setSourceType] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [groupId, setGroupId] = useState('')
  const [editing, setEditing] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editGroupId, setEditGroupId] = useState('')
  const [message, setMessage] = useState('')
  const [busySourceId, setBusySourceId] = useState<number | null>(null)
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([])
  const [sourceGroupFilterId, setSourceGroupFilterId] = useState('all')
  const [bulkGroupId, setBulkGroupId] = useState('')
  const [bulkText, setBulkText] = useState('')
  const [bulkDefaultGroupId, setBulkDefaultGroupId] = useState('')
  const [bulkType, setBulkType] = useState('')
  const [bulkResult, setBulkResult] = useState<SourceBulkAddResult | null>(null)
  const [groupForm, setGroupForm] = useState({
    group_name: '',
    display_name: '',
    description: '',
  })
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null)
  const [editGroupForm, setEditGroupForm] = useState(groupForm)

  useEffect(() => {
    setMessage('')
    setEditing(null)
    setEditingGroupId(null)
    setBusySourceId(null)
    setSelectedSourceIds([])
    setSourceGroupFilterId('all')
    setBulkGroupId('')
    setBulkText('')
    setBulkDefaultGroupId('')
    setBulkType('')
    setBulkResult(null)
    setGroupForm({ group_name: '', display_name: '', description: '' })
  }, [refreshTick])

  const runSourceAction = async (action: () => Promise<void>, successMessage?: string, sourceId?: number) => {
    setMessage('')
    if (sourceId) setBusySourceId(sourceId)
    try {
      await action()
      if (successMessage) setMessage(successMessage)
    } catch (exc) {
      setMessage(`Error: ${errorMessage(exc)}`)
    } finally {
      setBusySourceId(null)
    }
  }

  const addSource = async () => {
    if (!sourceInput.trim()) return
    await runSourceAction(async () => {
      await api('/sources', {
        method: 'POST',
        body: JSON.stringify({
          source_input: sourceInput.trim(),
          source_type: sourceType || null,
          display_name: displayName || null,
          group_id: groupId ? Number(groupId) : null,
          enabled: true,
        }),
      })
      setSourceInput('')
      setDisplayName('')
      setGroupId('')
      await onChanged()
    }, 'Source added')
  }
  const deleteSource = async (source: Source) => {
    await runSourceAction(async () => {
      await api(`/sources/${source.source_id}`, { method: 'DELETE' })
      await onChanged()
    }, `Deleted: ${source.display_name || source.source_name}`, source.source_id)
  }
  const saveEdit = async (source: Source) => {
    await runSourceAction(async () => {
      await api(`/sources/${source.source_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ display_name: editName, group_id: editGroupId ? Number(editGroupId) : null }),
      })
      setEditing(null)
      await onChanged()
    }, `Saved: ${source.display_name || source.source_name}`, source.source_id)
  }
  const filteredSources = sources.filter((source) => {
    if (sourceGroupFilterId === 'all') return true
    if (sourceGroupFilterId === 'ungrouped') return !source.group_id
    return source.group_id === Number(sourceGroupFilterId)
  })
  const filteredSourceIds = filteredSources.map((source) => source.source_id)
  const selectedVisibleSourceIds = selectedSourceIds.filter((sourceId) => filteredSourceIds.includes(sourceId))

  useEffect(() => {
    setSelectedSourceIds([])
  }, [sourceGroupFilterId])

  const toggleSelected = (sourceId: number) => {
    setSelectedSourceIds((current) => current.includes(sourceId) ? current.filter((id) => id !== sourceId) : [...current, sourceId])
  }
  const toggleAllSelected = () => {
    if (filteredSources.length > 0 && selectedVisibleSourceIds.length === filteredSources.length) {
      setSelectedSourceIds((current) => current.filter((sourceId) => !filteredSourceIds.includes(sourceId)))
      return
    }
    setSelectedSourceIds((current) => Array.from(new Set([...current, ...filteredSourceIds])))
  }
  const importYaml = async () => {
    await runSourceAction(async () => {
      const result = await api<{ imported: number }>('/sources/import', { method: 'POST' })
      setMessage(`imported: ${result.imported}`)
      await onChanged()
    })
  }
  const exportYaml = async () => {
    await runSourceAction(async () => {
      const result = await api<{ path: string; filename: string; content: string }>('/sources/export')
      downloadMarkdown(result.filename, result.content)
      setMessage(result.path)
    })
  }
  const saveYaml = async () => {
    await runSourceAction(async () => {
      const result = await api<{ path: string }>('/sources/save', { method: 'POST' })
      setMessage(result.path)
    })
  }
  const loadBulkTxt = async (file: File | null) => {
    if (!file) return
    const text = await file.text()
    setBulkText(text)
  }
  const bulkAddSources = async () => {
    if (!bulkText.trim()) return
    await runSourceAction(async () => {
      const result = await api<SourceBulkAddResult>('/sources/bulk-add', {
        method: 'POST',
        body: JSON.stringify({
          text: bulkText,
          source_type: bulkType || null,
          group_id: bulkDefaultGroupId ? Number(bulkDefaultGroupId) : null,
        }),
      })
      setBulkResult(result)
      setMessage(`${t.bulkCreated}: ${result.created.length} · ${t.bulkDuplicate}: ${result.duplicates.length} · ${t.bulkFailed}: ${result.failed.length}`)
      if (!result.failed.length) setBulkText('')
      await onChanged()
    })
  }
  const toggle = async (source: Source) => {
    await runSourceAction(async () => {
      await onToggle(source)
    }, `${source.enabled ? t.disabled : t.enabled}: ${source.display_name || source.source_name}`, source.source_id)
  }
  const createGroup = async () => {
    if (!groupForm.group_name.trim()) return
    await runSourceAction(async () => {
      await api('/source-groups', {
        method: 'POST',
        body: JSON.stringify(groupForm),
      })
      setGroupForm({ group_name: '', display_name: '', description: '' })
      await onChanged()
    }, 'Group added')
  }
  const saveGroup = async (groupIdValue: number) => {
    await runSourceAction(async () => {
      await api(`/source-groups/${groupIdValue}`, {
        method: 'PATCH',
        body: JSON.stringify(editGroupForm),
      })
      setEditingGroupId(null)
      await onChanged()
    }, 'Group saved')
  }
  const deleteGroup = async (group: SourceGroup) => {
    await runSourceAction(async () => {
      await api(`/source-groups/${group.group_id}`, { method: 'DELETE' })
      await onChanged()
    }, `Deleted: ${groupLabel(group)}`)
  }
  const applyBulkGroup = async (nextGroupId: number | null) => {
    if (!selectedSourceIds.length) return
    await runSourceAction(async () => {
      await Promise.all(
        selectedSourceIds.map((sourceId) => api(`/sources/${sourceId}`, {
          method: 'PATCH',
          body: JSON.stringify({ group_id: nextGroupId }),
        })),
      )
      setSelectedSourceIds([])
      setBulkGroupId('')
      await onChanged()
    }, nextGroupId ? 'Group assigned' : 'Group removed')
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{t.sources}</h2>
        <div className="toolbar">
          <button className="ghost" onClick={importYaml}>{t.importYaml}</button>
          <button className="ghost" onClick={saveYaml}>{t.saveYaml}</button>
          <button className="ghost" onClick={exportYaml}>{t.exportYaml}</button>
        </div>
      </div>
      {message ? <div className="notice compact neutral">{message}</div> : null}
      <div className="groups-block compact">
        <div className="groups-headline">
          <h3>{t.groups}</h3>
          <span>{groups.length} groups</span>
        </div>
        <div className="inline-form source-group-form">
          <input value={groupForm.group_name} onChange={(event) => setGroupForm({ ...groupForm, group_name: event.target.value })} placeholder="group_name" />
          <input value={groupForm.display_name} onChange={(event) => setGroupForm({ ...groupForm, display_name: event.target.value })} placeholder={t.displayName} />
          <input value={groupForm.description} onChange={(event) => setGroupForm({ ...groupForm, description: event.target.value })} placeholder="Description" />
          <button onClick={createGroup}>{t.add}</button>
        </div>
        <div className="group-row-list">
          <div className="group-row muted">
            <div className="group-row-main">
              <strong>{t.ungrouped}</strong>
              <span>No assigned sources</span>
            </div>
          </div>
          {groups.map((group) => (
            <div className="group-row" key={group.group_id}>
              {editingGroupId === group.group_id ? (
                <div className="group-row-edit">
                  <input value={editGroupForm.group_name} onChange={(event) => setEditGroupForm({ ...editGroupForm, group_name: event.target.value })} />
                  <input value={editGroupForm.display_name} onChange={(event) => setEditGroupForm({ ...editGroupForm, display_name: event.target.value })} />
                  <div className="toolbar">
                    <button onClick={() => saveGroup(group.group_id)}>{t.save}</button>
                    <button className="ghost" onClick={() => setEditingGroupId(null)}>{t.cancel}</button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="group-row-main">
                    <strong>{groupLabel(group)}</strong>
                    <span>{group.group_name} · {group.source_count || 0}</span>
                  </div>
                  <div className="row-actions compact">
                    <button className="ghost compact" onClick={() => { setEditingGroupId(group.group_id); setEditGroupForm({ group_name: group.group_name, display_name: group.display_name || '', description: group.description || '' }) }}>{t.edit}</button>
                    <button className="danger compact" onClick={() => deleteGroup(group)}>{t.delete}</button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
      <details className="bulk-import-block">
        <summary>
          <span>{t.bulkAddSources}</span>
          <small>{t.bulkSourceText}</small>
        </summary>
        <div className="bulk-import-grid">
          <textarea
            value={bulkText}
            onChange={(event) => setBulkText(event.target.value)}
            placeholder={'https://www.youtube.com/@channel\nhttps://www.youtube.com/playlist?list=PL...'}
          />
          <div className="bulk-import-controls">
            <label className="form-field">
              <span>{t.sourceType}</span>
              <select value={bulkType} onChange={(event) => setBulkType(event.target.value)}>
                <option value="">auto</option>
                <option value="channel">channel</option>
                <option value="playlist">playlist</option>
              </select>
            </label>
            <label className="form-field">
              <span>{t.bulkDefaultGroup}</span>
              <select value={bulkDefaultGroupId} onChange={(event) => setBulkDefaultGroupId(event.target.value)}>
                <option value="">{t.ungrouped}</option>
                {groups.map((group) => <option key={group.group_id} value={group.group_id}>{groupLabel(group)}</option>)}
              </select>
            </label>
            <label className="file-button ghost">
              {t.bulkUploadTxt}
              <input type="file" accept=".txt,text/plain" onChange={(event) => loadBulkTxt(event.target.files?.[0] || null)} />
            </label>
            <button disabled={!bulkText.trim()} onClick={bulkAddSources}>{t.bulkImport}</button>
          </div>
        </div>
        {bulkResult ? (
          <div className="bulk-result">
            <strong>{t.bulkResult}</strong>
            <span>{t.bulkCreated}: {bulkResult.created.length}</span>
            <span>{t.bulkDuplicate}: {bulkResult.duplicates.length}</span>
            <span>{t.bulkFailed}: {bulkResult.failed.length}</span>
            <span>{t.bulkIgnored}: {bulkResult.ignored}</span>
            {bulkResult.failed.length ? (
              <details>
                <summary>{t.bulkFailed}</summary>
                <ul>
                  {bulkResult.failed.map((item) => <li key={`${item.line}-${item.input}`}>#{item.line} {item.input}: {item.error}</li>)}
                </ul>
              </details>
            ) : null}
            {bulkResult.duplicates.length ? (
              <details>
                <summary>{t.bulkDuplicate}</summary>
                <ul>
                  {bulkResult.duplicates.map((item) => <li key={`${item.line}-${item.input}`}>#{item.line} {item.input}: {item.reason}</li>)}
                </ul>
              </details>
            ) : null}
          </div>
        ) : null}
      </details>
      <div className="inline-form source-form">
        <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
          <option value="">{t.sourceType}: auto</option>
          <option value="channel">channel</option>
          <option value="playlist">playlist</option>
          <option value="video">video</option>
        </select>
        <input value={sourceInput} onChange={(event) => setSourceInput(event.target.value)} placeholder="YouTube channel / playlist / video URL" />
        <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder={t.displayName} />
        <select value={groupId} onChange={(event) => setGroupId(event.target.value)}>
          <option value="">{t.ungrouped}</option>
          {groups.map((group) => <option key={group.group_id} value={group.group_id}>{groupLabel(group)}</option>)}
        </select>
        <button onClick={addSource}>{t.add}</button>
      </div>
      <div className="bulk-toolbar compact">
        <label className="source-filter-control">
          <span>{t.sourceGroupFilter}</span>
          <select value={sourceGroupFilterId} onChange={(event) => setSourceGroupFilterId(event.target.value)}>
            <option value="all">{t.all}</option>
            <option value="ungrouped">{t.ungrouped}</option>
            {groups.map((group) => <option key={group.group_id} value={group.group_id}>{groupLabel(group)}</option>)}
          </select>
        </label>
        <span className="source-filter-count">{t.visibleSources}: {filteredSources.length}/{sources.length}</span>
        <label className="check-row">
          <input type="checkbox" checked={filteredSources.length > 0 && selectedVisibleSourceIds.length === filteredSources.length} onChange={toggleAllSelected} />
          {selectedSourceIds.length ? `${selectedSourceIds.length} selected` : 'Select all'}
        </label>
        <label className="source-filter-control">
          <span>{t.bulkMoveToGroup}</span>
          <select value={bulkGroupId} onChange={(event) => setBulkGroupId(event.target.value)}>
            <option value="">{t.group}</option>
            {groups.map((group) => <option key={group.group_id} value={group.group_id}>{groupLabel(group)}</option>)}
          </select>
        </label>
        <button className="ghost" disabled={!selectedSourceIds.length || !bulkGroupId} onClick={() => applyBulkGroup(Number(bulkGroupId))}>{t.assignGroup}</button>
        <button className="ghost" disabled={!selectedSourceIds.length} onClick={() => applyBulkGroup(null)}>{t.removeGroup}</button>
      </div>
      <table>
        <thead><tr><th></th><th>{t.status}</th><th>{t.type}</th><th>{t.sourceName}</th><th>{t.group}</th><th>YouTube ID</th><th>Playlist</th><th>Last Error</th><th>{t.actions}</th></tr></thead>
        <tbody>
          {filteredSources.map((source) => (
            <tr key={source.source_id}>
              <td><input type="checkbox" checked={selectedSourceIds.includes(source.source_id)} onChange={() => toggleSelected(source.source_id)} /></td>
              <td><span className={source.enabled ? 'pill ok' : 'pill'}>{source.enabled ? t.enabled : t.disabled}</span></td>
              <td>{source.source_type}</td>
              <td>
                {editing === source.source_id ? (
                  <input value={editName} onChange={(event) => setEditName(event.target.value)} />
                ) : (
                  <>
                    {source.display_name || source.source_name}
                    <small>{source.channel_name}</small>
                  </>
                )}
              </td>
              <td>
                {editing === source.source_id ? (
                  <select value={editGroupId} onChange={(event) => setEditGroupId(event.target.value)}>
                    <option value="">{t.ungrouped}</option>
                    {groups.map((group) => <option key={group.group_id} value={group.group_id}>{groupLabel(group)}</option>)}
                  </select>
                ) : (
                  <span className={sourceGroupLabel(source, '') ? 'group-inline' : 'group-inline muted'}>
                    {sourceGroupLabel(source, t.ungrouped)}
                  </span>
                )}
              </td>
              <td><code>{source.youtube_id}</code></td>
              <td><code>{source.playlist_id || '-'}</code></td>
              <td>{source.last_error || '-'}</td>
              <td className="actions">
                <button disabled={busySourceId === source.source_id} onClick={() => toggle(source)}>{source.enabled ? t.disable : t.enable}</button>
                {editing === source.source_id ? (
                  <>
                    <button disabled={busySourceId === source.source_id} onClick={() => saveEdit(source)}>{t.save}</button>
                    <button className="ghost" onClick={() => setEditing(null)}>{t.cancel}</button>
                  </>
                ) : (
                  <button className="ghost" onClick={() => { setEditing(source.source_id); setEditName(source.display_name || ''); setEditGroupId(source.group_id ? String(source.group_id) : '') }}>{t.edit}</button>
                )}
                <button className="danger" disabled={busySourceId === source.source_id} onClick={() => deleteSource(source)}>{t.delete}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function VideoListRow({
  video,
  selected,
  mode,
  t,
  onSelect,
}: {
  video: Video
  selected: boolean
  mode: VideoMode
  t: typeof copy.zh
  onSelect: () => void
}) {
  return (
    <button className={selected ? 'list-row selected' : 'list-row'} onClick={onSelect}>
      <strong>{video.video_title}</strong>
      <span>{video.channel_name} · {video.video_date || '-'}{mode === 'maintenance' ? ` · ${statusLabel(video.status, t)} (${video.status})` : ''}</span>
    </button>
  )
}

function groupVideosByChannel(videos: Video[]) {
  const groups = new Map<string, { key: string; name: string; latestDate: string; videos: Video[] }>()
  for (const video of videos) {
    const name = video.channel_name || 'Unknown channel'
    const key = name.toLowerCase()
    const group = groups.get(key) || { key, name, latestDate: '', videos: [] }
    group.videos.push(video)
    if ((video.video_date || '') > group.latestDate) group.latestDate = video.video_date || ''
    groups.set(key, group)
  }
  return [...groups.values()].sort((left, right) => {
    if (right.latestDate !== left.latestDate) return right.latestDate.localeCompare(left.latestDate)
    return left.name.localeCompare(right.name)
  })
}

function VideosView({
  videos,
  sources,
  selectedVideoId,
  selectedVideoMode,
  refreshTick,
  t,
  onChanged,
}: {
  videos: Video[]
  sources: Source[]
  selectedVideoId: string
  selectedVideoMode: VideoMode | null
  refreshTick: number
  t: typeof copy.zh
  onChanged: () => void
}) {
  const [selectedId, setSelectedId] = useState(selectedVideoId || videos[0]?.video_id || '')
  const [detail, setDetail] = useState<VideoDetail | null>(null)
  const [tab, setTab] = useState<VideoTab>('summary')
  const [status, setStatus] = useState('')
  const [mode, setMode] = useState<VideoMode>('reading')
  const [listView, setListView] = useState<'list' | 'channel'>('list')
  const [expandedChannels, setExpandedChannels] = useState<string[]>([])
  const [deliveryChannels, setDeliveryChannels] = useState<DeliveryChannels>({ telegram: true, email: false })
  const [delivering, setDelivering] = useState(false)
  const [appliedSelectedVideoId, setAppliedSelectedVideoId] = useState('')
  const [filters, setFilters] = useState({
    source: '',
    status: 'summarized',
    summary: 'yes',
    transcript: '',
    dateFrom: '',
    dateTo: '',
    keyword: '',
  })

  const readableVideos = videos.filter((video) => video.status === 'summarized' && video.summary_latest_id)
  const listSource = mode === 'reading' ? readableVideos : videos

  useEffect(() => {
    if (!selectedVideoId || selectedVideoId === appliedSelectedVideoId) return
    const target = videos.find((video) => video.video_id === selectedVideoId)
    const nextMode = selectedVideoMode || ((!target || target.status !== 'summarized' || !target.summary_latest_id) ? 'maintenance' : null)
    if (nextMode) {
      setMode(nextMode)
      if (nextMode === 'maintenance') {
        setFilters({ source: '', status: '', summary: '', transcript: '', dateFrom: '', dateTo: '', keyword: '' })
      } else {
        setFilters({ source: '', status: 'summarized', summary: 'yes', transcript: '', dateFrom: '', dateTo: '', keyword: '' })
      }
    }
    setSelectedId(selectedVideoId)
    setAppliedSelectedVideoId(selectedVideoId)
    setTab('summary')
  }, [selectedVideoId, selectedVideoMode, appliedSelectedVideoId, videos])

  useEffect(() => {
    if (selectedVideoId && selectedId === selectedVideoId) return
    if (!selectedId && listSource[0]?.video_id) setSelectedId(listSource[0].video_id)
    if (selectedId && !listSource.some((video) => video.video_id === selectedId) && listSource[0]?.video_id) {
      setSelectedId(listSource[0].video_id)
      setTab('summary')
    }
  }, [listSource, selectedId, selectedVideoId])

  useEffect(() => {
    if (!selectedId) return
    api<VideoDetail>(`/videos/${selectedId}`).then(setDetail).catch((exc) => setStatus(String(exc)))
  }, [selectedId])

  useEffect(() => {
    setStatus('')
  }, [refreshTick])

  const switchMode = (nextMode: VideoMode) => {
    setMode(nextMode)
    setTab('summary')
    if (nextMode === 'reading') {
      setFilters({ source: '', status: 'summarized', summary: 'yes', transcript: '', dateFrom: '', dateTo: '', keyword: '' })
    } else {
      setFilters({ source: '', status: '', summary: '', transcript: '', dateFrom: '', dateTo: '', keyword: '' })
    }
    setSelectedId('')
    setDetail(null)
  }

  const filtered = listSource.filter((video) => {
    const source = sources.find((item) => item.source_id === Number(filters.source))
    const text = `${video.video_title} ${video.channel_name} ${video.video_id}`.toLowerCase()
    if (mode === 'maintenance' && filters.status && video.status !== filters.status) return false
    if (mode === 'maintenance' && filters.summary === 'yes' && !video.summary_latest_id) return false
    if (mode === 'maintenance' && filters.summary === 'no' && video.summary_latest_id) return false
    if (filters.transcript === 'yes' && !video.has_transcript) return false
    if (filters.transcript === 'no' && video.has_transcript) return false
    if (filters.dateFrom && (!video.video_date || video.video_date < filters.dateFrom)) return false
    if (filters.dateTo && (!video.video_date || video.video_date > filters.dateTo)) return false
    if (filters.keyword && !text.includes(filters.keyword.toLowerCase())) return false
    if (source && source.channel_name && video.channel_name !== source.channel_name) return false
    return true
  })
  const channelGroups = useMemo(() => groupVideosByChannel(filtered), [filtered])

  const toggleChannel = (channelKey: string) => {
    setExpandedChannels((current) => (
      current.includes(channelKey)
        ? current.filter((item) => item !== channelKey)
        : [...current, channelKey]
    ))
  }

  const operate = async (path: string) => {
    const videoId = detail?.video_id || selectedId
    if (!videoId) return
    setStatus(t.operationRunning)
    try {
      const result = await api<Record<string, string | number>>(path, { method: 'POST' })
      const refreshed = await api<VideoDetail>(`/videos/${videoId}`)
      setDetail(refreshed)
      setStatus(videoOperationStatusText(path, result, t))
      await onChanged()
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : String(exc))
    }
  }

  const summaryMarkdown = detail?.summary?.content_markdown?.trim() || ''
  const transcriptMarkdown = detail?.transcript_clean?.trim() || ''

  const copySummary = async () => {
    if (!summaryMarkdown) {
      setStatus(t.noSummary)
      return
    }
    await copyText(`${summaryMarkdown}\n`)
    setStatus(t.copied)
  }

  const downloadSummary = () => {
    if (!detail || !summaryMarkdown) {
      setStatus(t.noSummary)
      return
    }
    downloadMarkdown(summaryMarkdownFilename(detail), `${summaryMarkdown}\n`)
    setStatus(t.downloaded)
  }

  const copyTranscript = async () => {
    if (!transcriptMarkdown) {
      setStatus(t.noTranscript)
      return
    }
    await copyText(`${transcriptMarkdown}\n`)
    setStatus(t.copied)
  }

  const downloadTranscript = () => {
    if (!detail || !transcriptMarkdown) {
      setStatus(t.noTranscript)
      return
    }
    downloadMarkdown(transcriptMarkdownFilename(detail), `${transcriptMarkdown}\n`)
    setStatus(t.downloaded)
  }
  const deliverCurrentVideo = async () => {
    if (!detail?.summary?.summary_id) return
    if (!deliveryChannels.telegram && !deliveryChannels.email) {
      setStatus(t.selectDeliveryChannel)
      return
    }
    setDelivering(true)
    setStatus('')
    try {
      const deliveries = await deliverSummary(detail.summary.summary_id, deliveryChannels)
      setStatus(deliveryStatusText(deliveries, t))
      await onChanged()
    } catch (exc) {
      setStatus(errorMessage(exc))
    } finally {
      setDelivering(false)
    }
  }

  return (
    <section className="split wide">
      <div className="panel list-panel">
        <div className="segmented">
          <button className={mode === 'reading' ? 'active' : ''} onClick={() => switchMode('reading')}>{t.readingView}</button>
          <button className={mode === 'maintenance' ? 'active' : ''} onClick={() => switchMode('maintenance')}>{t.maintenanceView}</button>
        </div>
        <h2>{t.filters}</h2>
        <select value={filters.source} onChange={(event) => setFilters({ ...filters, source: event.target.value })}>
          <option value="">{t.all} sources</option>
          {sources.map((source) => <option key={source.source_id} value={source.source_id}>{source.display_name || source.source_name}</option>)}
        </select>
        {mode === 'maintenance' ? (
          <>
            <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
              <option value="">{t.all} status</option>
              {[...new Set(videos.map((video) => video.status))].map((item) => <option key={item} value={item}>{statusLabel(item, t)} ({item})</option>)}
            </select>
            <select value={filters.summary} onChange={(event) => setFilters({ ...filters, summary: event.target.value })}>
              <option value="">{t.all}</option>
              <option value="yes">{t.hasSummary}</option>
              <option value="no">No summary</option>
            </select>
          </>
        ) : null}
        <div className="filter-row">
          <DateInput value={filters.dateFrom} onChange={(value) => setFilters({ ...filters, dateFrom: value })} ariaLabel={t.dateFrom} title={t.dateFrom} />
          <DateInput value={filters.dateTo} onChange={(value) => setFilters({ ...filters, dateTo: value })} ariaLabel={t.dateTo} title={t.dateTo} />
        </div>
        <select value={filters.transcript} onChange={(event) => setFilters({ ...filters, transcript: event.target.value })}>
          <option value="">{t.all} {t.transcriptFilter}</option>
          <option value="yes">{t.hasTranscript}</option>
          <option value="no">{t.noTranscript}</option>
        </select>
        <input value={filters.keyword} onChange={(event) => setFilters({ ...filters, keyword: event.target.value })} placeholder={t.keyword} />
        {mode === 'maintenance' ? <div className="status-help">{t.statusHelp}</div> : <div className="status-help">{t.showMaintenanceHint}</div>}
        <h2 className="section-gap">{t.videoLibrary}</h2>
        <div className="segmented compact-segmented">
          <button className={listView === 'list' ? 'active' : ''} onClick={() => setListView('list')}>{t.listView}</button>
          <button className={listView === 'channel' ? 'active' : ''} onClick={() => setListView('channel')}>{t.channelView}</button>
        </div>
        {filtered.length ? (
          listView === 'list' ? filtered.map((video) => (
            <VideoListRow key={video.video_id} video={video} selected={selectedId === video.video_id} mode={mode} t={t} onSelect={() => { setSelectedId(video.video_id); setTab('summary') }} />
          )) : (
            <div className="channel-list">
              {channelGroups.map((group) => {
                const expanded = expandedChannels.includes(group.key)
                const visible = expanded ? group.videos : group.videos.slice(0, 3)
                return (
                  <div className="channel-group" key={group.key}>
                    <div className="channel-group-title">
                      <div>
                        <strong>{group.name}</strong>
                        <span>{group.videos.length} videos · {group.latestDate || '-'}</span>
                      </div>
                      {group.videos.length > 3 ? (
                        <button className="ghost small-button" onClick={() => toggleChannel(group.key)}>
                          {expanded ? t.showLessVideos : t.showAllVideos}
                        </button>
                      ) : null}
                    </div>
                    {visible.map((video) => (
                      <VideoListRow key={video.video_id} video={video} selected={selectedId === video.video_id} mode={mode} t={t} onSelect={() => { setSelectedId(video.video_id); setTab('summary') }} />
                    ))}
                  </div>
                )
              })}
            </div>
          )
        ) : <p>{mode === 'reading' ? t.noSummaries : t.noOperationalItems}</p>}
      </div>
      <article className="panel detail-panel">
        {!detail ? <p>Loading</p> : (
          <>
            <div className="panel-title">
              <div>
                <h2>{detail.video_title}</h2>
                <p className="digest-meta">{detail.channel_name} · {detail.video_date || '-'} · {statusLabel(detail.status, t)} · <code>{detail.video_id}</code></p>
              </div>
              <div className="actions">
                {mode === 'maintenance' ? (
                  <div className="video-maintenance-actions">
                    <button onClick={() => operate(`/videos/${detail.video_id}/process`)}>{t.process}</button>
                    <button onClick={() => operate(`/videos/${detail.video_id}/summarize`)}>{t.summarize}</button>
                  </div>
                ) : null}
                <DeliveryControls
                  summaryId={detail.summary?.summary_id}
                  channels={deliveryChannels}
                  onChannelsChange={setDeliveryChannels}
                  onDeliver={deliverCurrentVideo}
                  delivering={delivering}
                  t={t}
                />
                <div className="video-document-actions">
                  <button className="ghost" disabled={!summaryMarkdown} onClick={copySummary}>{t.copySummary}</button>
                  <button className="ghost" disabled={!summaryMarkdown} onClick={downloadSummary}>{t.downloadSummary}</button>
                  <button className="ghost" disabled={!transcriptMarkdown} onClick={copyTranscript}>{t.copyTranscript}</button>
                  <button className="ghost" disabled={!transcriptMarkdown} onClick={downloadTranscript}>{t.downloadTranscript}</button>
                </div>
                {detail.video_url ? <a className="button-link video-open-link" href={detail.video_url} target="_blank" rel="noreferrer">{t.openYoutube}</a> : null}
              </div>
            </div>
            <div className="detail-meta-grid">
              <div>
                <span>{t.summaryMeta}</span>
                <strong>{detail.summary?.summary_id ? `#${detail.summary.summary_id}` : '-'}</strong>
                <small>{detail.summary ? `${detail.summary.model_provider} / ${detail.summary.model_name}` : t.noSummary}</small>
                <small>{detail.summary?.prompt_version || '-'}</small>
              </div>
              <div>
                <span>{t.pipelineMeta}</span>
                <strong>{detail.has_transcript ? t.hasTranscript : t.noTranscript}</strong>
                <small>fetched: {detail.fetched_at || '-'}</small>
                <small>cleaned: {detail.cleaned_at || '-'}</small>
                <small>summarized: {detail.summarized_at || '-'}</small>
              </div>
              <div>
                <span>{t.sourceMeta}</span>
                <strong>{detail.sources?.[0]?.display_name || detail.sources?.[0]?.source_name || detail.channel_name}</strong>
                <small>{detail.sources?.map((source) => source.display_name || source.source_name).filter(Boolean).join(', ') || '-'}</small>
                <small>duration: {detail.duration ? `${Math.round(Number(detail.duration) / 60)} min` : '-'}</small>
              </div>
            </div>
            {status ? <div className="notice compact neutral">{status}</div> : null}
            <div className="tabs">
              {(mode === 'reading'
                ? (['summary', 'transcript'] as VideoTab[])
                : (['summary', 'transcript', 'vtt', 'metadata'] as VideoTab[])
              ).map((item) => (
                <button key={item} className={tab === item ? 'tab active' : 'tab'} onClick={() => setTab(item)}>
                  {item === 'summary' ? t.summary : item === 'transcript' ? t.transcript : item === 'vtt' ? t.sourceVtt : t.metadata}
                </button>
              ))}
            </div>
            {tab === 'summary' ? (
              <div className="markdown-preview">
                <ReactMarkdown>{detail.summary?.content_markdown || t.noSummary}</ReactMarkdown>
              </div>
            ) : null}
            {tab === 'transcript' ? <pre className="text-block">{detail.transcript_clean || 'No transcript'}</pre> : null}
            {tab === 'vtt' ? <pre className="text-block">{detail.transcript_raw_vtt || 'No source VTT'}</pre> : null}
            {tab === 'metadata' ? <MetadataTable data={detail} /> : null}
          </>
        )}
      </article>
    </section>
  )
}

function DigestsView({
  digests,
  sources,
  groups,
  selected,
  refreshTick,
  t,
  onSelect,
  onOpenVideo,
  onChanged,
}: {
  digests: Digest[]
  sources: Source[]
  groups: SourceGroup[]
  selected: Digest | null
  refreshTick: number
  t: typeof copy.zh
  onSelect: (digest: Digest) => void
  onOpenVideo: (videoId: string, mode?: VideoMode) => void
  onChanged: () => void
}) {
  const digest = selected || digests[0]
  const [digestDetail, setDigestDetail] = useState<Digest | null>(null)
  const [scopeMode, setScopeMode] = useState<'all' | 'groups' | 'sources'>('all')
  const [timeMode, setTimeMode] = useState<'1' | '3' | '7' | 'custom' | 'all'>('1')
  const [digestLanguage, setDigestLanguage] = useState<'zh' | 'en'>('zh')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [limitVideos, setLimitVideos] = useState(true)
  const [maxVideosPerSource, setMaxVideosPerSource] = useState(10)
  const [selectedSources, setSelectedSources] = useState<number[]>([])
  const [selectedGroups, setSelectedGroups] = useState<number[]>([])
  const [run, setRun] = useState<DigestRun | null>(null)
  const [running, setRunning] = useState(false)
  const [tab, setTab] = useState<DigestTab>('summary')
  const [message, setMessage] = useState('')
  const [retrying, setRetrying] = useState('')
  const [deliveryChannels, setDeliveryChannels] = useState<DeliveryChannels>({ telegram: true, email: false })
  const [delivering, setDelivering] = useState(false)

  useEffect(() => {
    if (!digest?.summary_id) {
      setDigestDetail(null)
      return
    }
    api<Digest>(`/digests/${digest.summary_id}`).then(setDigestDetail).catch(() => setDigestDetail(null))
  }, [digest?.summary_id])

  useEffect(() => {
    setMessage('')
    setRunning(false)
    setRetrying('')
  }, [refreshTick])

  const toggleSelectedSource = (sourceId: number) => {
    setSelectedSources((current) => (
      current.includes(sourceId) ? current.filter((id) => id !== sourceId) : [...current, sourceId]
    ))
  }
  const toggleSelectedGroup = (groupId: number) => {
    setSelectedGroups((current) => (
      current.includes(groupId) ? current.filter((id) => id !== groupId) : [...current, groupId]
    ))
  }
  const isCustomRange = timeMode === 'custom'
  const isAllTime = timeMode === 'all'
  const generate = async () => {
    setRunning(true)
    setMessage('')
    try {
      const result = await api<DigestRun>('/digest-runs', {
        method: 'POST',
        body: JSON.stringify({
          use_all_enabled_sources: scopeMode === 'all',
          source_ids: scopeMode === 'sources' ? selectedSources : [],
          group_ids: scopeMode === 'groups' ? selectedGroups : [],
          window_days: isCustomRange || isAllTime ? null : Number(timeMode),
          date_from: isCustomRange ? dateFrom : null,
          date_to: isCustomRange ? dateTo : null,
          all_time: isAllTime,
          max_videos_per_source: limitVideos ? Math.max(1, maxVideosPerSource) : null,
          reuse_existing_summaries: true,
          process_missing_videos: true,
          retry_failed_once: true,
          digest_language: digestLanguage,
        }),
      })
      setRun(result)
      await onChanged()
    } finally {
      setRunning(false)
    }
  }
  const exportDigest = async () => {
    if (!digest) return
    const result = await api<{ summary: string; filename: string; content_markdown: string }>(`/digests/${digest.summary_id}/export`, { method: 'POST' })
    downloadMarkdown(result.filename || 'daily-summary.md', result.content_markdown || '')
    setMessage(`${t.downloaded}: ${result.summary}`)
  }
  const regenerateDigest = async () => {
    if (!digest) return
    setRunning(true)
    setMessage('')
    try {
      const result = await api<DigestRun>(`/digests/${digest.summary_id}/regenerate`, { method: 'POST' })
      setRun(result)
      setMessage(`#${result.run_id} · ${result.status}`)
      await onChanged()
    } finally {
      setRunning(false)
    }
  }
  const copyDigest = async () => {
    const markdown = visibleDigest?.content_markdown || digest?.content_markdown || ''
    if (!markdown.trim()) {
      setMessage(t.noMarkdown)
      return
    }
    await copyText(markdown)
    setMessage(t.copied)
  }
  const deliverCurrentDigest = async () => {
    if (!visibleDigest?.summary_id) return
    if (!deliveryChannels.telegram && !deliveryChannels.email) {
      setMessage(t.selectDeliveryChannel)
      return
    }
    setDelivering(true)
    setMessage('')
    try {
      const deliveries = await deliverSummary(visibleDigest.summary_id, deliveryChannels)
      setMessage(deliveryStatusText(deliveries, t))
      await onChanged()
    } catch (exc) {
      setMessage(errorMessage(exc))
    } finally {
      setDelivering(false)
    }
  }
  const retryRunVideo = async (row: DigestVideo) => {
    if (!row.run_id) return
    setRetrying(`${row.run_id}-${row.video_id}-${row.source_id || ''}`)
    setMessage('')
    try {
      const query = row.source_id ? `?source_id=${row.source_id}` : ''
      const result = await api<DigestVideo & { run: DigestRun }>(`/digest-runs/${row.run_id}/videos/${row.video_id}/retry${query}`, { method: 'POST' })
      setMessage(`${result.video_title || result.video_id} · ${result.status}`)
      await onChanged()
      if (digest?.summary_id) {
        setDigestDetail(await api<Digest>(`/digests/${digest.summary_id}`))
      }
    } catch (exc) {
      setMessage(errorMessage(exc))
    } finally {
      setRetrying('')
    }
  }

  const visibleDigest = digestDetail || digest
  const runVideos = (run?.videos || []) as DigestVideo[]
  const included = visibleDigest?.included_videos?.length ? visibleDigest.included_videos : runVideos.filter((video) => video.status === 'included')
  const failed = visibleDigest?.failed_videos?.length ? visibleDigest.failed_videos : runVideos.filter((video) => video.status === 'failed' || video.status === 'skipped')
  const groupedSources = groups.filter((group) => Number(group.source_count || 0) > 0)
  const generateDisabled =
    running
    || (scopeMode === 'sources' && selectedSources.length === 0)
    || (scopeMode === 'groups' && selectedGroups.length === 0)
    || (isCustomRange && (!dateFrom || !dateTo))

  return (
    <section className="split">
      <div className="panel list-panel">
        <h2>{t.generateDigest}</h2>
        <label className="field-label">{t.sourceScope}</label>
        <select value={scopeMode} onChange={(event) => setScopeMode(event.target.value as 'all' | 'groups' | 'sources')}>
          <option value="all">{t.scopeAll}</option>
          <option value="groups">{t.selectedGroups}</option>
          <option value="sources">{t.selectedSources}</option>
        </select>
        {scopeMode === 'groups' ? (
          <div className="source-checks">
            {groupedSources.map((group) => (
              <label className="check-row" key={group.group_id}>
                <input
                  type="checkbox"
                  checked={selectedGroups.includes(group.group_id)}
                  onChange={() => toggleSelectedGroup(group.group_id)}
                />
                {groupLabel(group)} ({group.source_count || 0})
              </label>
            ))}
          </div>
        ) : null}
        {scopeMode === 'sources' ? (
          <div className="source-checks">
            {sources.map((source) => (
              <label className="check-row" key={source.source_id}>
                <input
                  type="checkbox"
                  checked={selectedSources.includes(source.source_id)}
                  onChange={() => toggleSelectedSource(source.source_id)}
                />
                {source.display_name || source.source_name}
              </label>
            ))}
          </div>
        ) : null}
        <label className="field-label">{t.windowDays}</label>
        <select value={timeMode} onChange={(event) => setTimeMode(event.target.value as '1' | '3' | '7' | 'custom' | 'all')}>
          <option value="1">{t.last1}</option>
          <option value="3">{t.last3}</option>
          <option value="7">{t.last7}</option>
          <option value="custom">{t.customRange}</option>
          <option value="all">{t.allTime}</option>
        </select>
        <label className="field-label">{t.digestLanguage}</label>
        <select value={digestLanguage} onChange={(event) => setDigestLanguage(event.target.value as 'zh' | 'en')}>
          <option value="zh">中文</option>
          <option value="en">English</option>
        </select>
        {isCustomRange ? (
          <div className="inline-form two">
            <DateInput value={dateFrom} onChange={setDateFrom} ariaLabel={t.dateFrom} title={t.dateFrom} />
            <DateInput value={dateTo} onChange={setDateTo} ariaLabel={t.dateTo} title={t.dateTo} />
          </div>
        ) : null}
        <label className="check-row">
          <input type="checkbox" checked={limitVideos} onChange={(event) => setLimitVideos(event.target.checked)} />
          {t.limitVideos}
        </label>
        {limitVideos ? (
          <>
            <label className="field-label">{t.maxVideosPerSource}</label>
            <input
              type="number"
              min="1"
              value={maxVideosPerSource}
              onChange={(event) => setMaxVideosPerSource(Number(event.target.value) || 1)}
            />
          </>
        ) : (
          <p className="field-label">{t.unlimitedVideos}</p>
        )}
        <button disabled={generateDisabled} onClick={generate}>
          {running ? 'Running...' : t.generateDigest}
        </button>
        {run ? (
          <div className="run-result">
            <h2>{t.runResult}</h2>
            <span className={run.status === 'completed' ? 'pill ok' : 'pill'}>{run.status}</span>
            <p>included: {run.included_count}</p>
            <p>failed: {run.failed_count}</p>
            <p>skipped: {run.skipped_count}</p>
            {run.summary_id ? <p>summary: #{run.summary_id}</p> : null}
          </div>
        ) : null}
        <h2>{t.digestHistory}</h2>
        {digests.map((item) => (
          <button className={digest?.summary_id === item.summary_id ? 'list-row selected' : 'list-row'} key={item.summary_id} onClick={() => { onSelect(item); setTab('summary') }}>
            <strong>{digestDisplayTitle(item, t)}</strong>
            <span>{digestDisplayMeta(item)}</span>
          </button>
        ))}
      </div>
      <article className="panel markdown">
        <div className="panel-title digest-detail-title">
          <div>
            <h2>{visibleDigest ? digestDisplayTitle(visibleDigest, t) : t.noDigest}</h2>
            <p className="digest-meta">
              {visibleDigest ? `${visibleDigest.model_provider} / ${visibleDigest.model_name} · ${digestDisplayMeta(visibleDigest)}` : ''}
            </p>
          </div>
          <div className="actions digest-detail-actions">
            <div className="digest-delivery-actions">
              <DeliveryControls
                summaryId={visibleDigest?.summary_id}
                channels={deliveryChannels}
                onChannelsChange={setDeliveryChannels}
                onDeliver={deliverCurrentDigest}
                delivering={delivering}
                t={t}
              />
            </div>
            <div className="digest-file-actions">
              <button className="ghost" disabled={!digest || running} onClick={regenerateDigest}>{running ? t.regenerating : t.regenerateDaily}</button>
              <button className="ghost" disabled={!digest} onClick={copyDigest}>{t.copyMarkdown}</button>
              <button className="ghost" disabled={!digest} onClick={exportDigest}>{t.exportMarkdown}</button>
            </div>
          </div>
        </div>
        {message ? <div className="notice compact neutral">{message}</div> : null}
        <div className="tabs">
          {(['summary', 'included', 'failed', 'metadata'] as DigestTab[]).map((item) => (
            <button key={item} className={tab === item ? 'tab active' : 'tab'} onClick={() => setTab(item)}>
              {item === 'summary' ? t.summary : item === 'included' ? t.included : item === 'failed' ? t.failed : t.metadata}
            </button>
          ))}
        </div>
        {tab === 'summary' ? <div className="markdown-preview"><ReactMarkdown>{visibleDigest?.content_markdown || visibleDigest?.preview || ''}</ReactMarkdown></div> : null}
        {tab === 'included' ? <RunVideoList rows={included} onOpenVideo={(videoId) => onOpenVideo(videoId, 'reading')} /> : null}
        {tab === 'failed' ? <RunVideoList rows={failed} onOpenVideo={(videoId) => onOpenVideo(videoId, 'maintenance')} onRetry={retryRunVideo} retryingKey={retrying} retryLabel={t.retry} /> : null}
        {tab === 'metadata' ? <MetadataTable data={{ ...(visibleDigest || {}), latest_run: run || null }} /> : null}
      </article>
    </section>
  )
}

function PromptsView({ prompts, groups, refreshTick, t, onChanged }: { prompts: Prompt[]; groups: SourceGroup[]; refreshTick: number; t: typeof copy.zh; onChanged: () => void }) {
  const [scope, setScope] = useState('global')
  const selectedGroupId = scope === 'global' ? null : Number(scope)
  const scopedPrompts = prompts.filter((prompt) => (selectedGroupId === null ? !prompt.group_id : prompt.group_id === selectedGroupId))
  const activeVideo = scopedPrompts.find((prompt) => prompt.prompt_type === 'video_summary' && prompt.is_active) || scopedPrompts.find((prompt) => prompt.prompt_type === 'video_summary')
  const activeDaily = scopedPrompts.find((prompt) => prompt.prompt_type === 'daily_digest' && prompt.is_active) || scopedPrompts.find((prompt) => prompt.prompt_type === 'daily_digest')
  const [videoSystem, setVideoSystem] = useState(activeVideo?.system_prompt || 'You are a professional content research editor.')
  const [videoTemplate, setVideoTemplate] = useState(activeVideo?.user_template || 'Summarize this episode using the same language as the original video: {{ transcript }}')
  const [dailySystem, setDailySystem] = useState(activeDaily?.system_prompt || 'You are a professional industry content editor preparing a daily podcast brief for clients.')
  const [dailyTemplate, setDailyTemplate] = useState(activeDaily?.user_template || 'Create a daily digest for {{ run_date }} in {{ digest_language }} based on these summaries:\n\n{{ summaries }}')
  const [preview, setPreview] = useState('')

  useEffect(() => {
    if (activeVideo?.user_template) {
      setVideoSystem(activeVideo.system_prompt || '')
      setVideoTemplate(activeVideo.user_template)
    }
    if (activeDaily?.user_template) {
      setDailySystem(activeDaily.system_prompt || '')
      setDailyTemplate(activeDaily.user_template)
    }
  }, [activeVideo?.prompt_id, activeDaily?.prompt_id])

  useEffect(() => {
    setPreview('')
  }, [refreshTick])

  const savePrompt = async (promptType: string, promptName: string, systemPrompt: string, template: string) => {
    await api('/prompts', {
      method: 'POST',
      body: JSON.stringify({
        prompt_type: promptType,
        prompt_name: promptName,
        language: 'auto',
        group_id: selectedGroupId,
        system_prompt: systemPrompt,
        user_template: template,
        activate: true,
      }),
    })
    onChanged()
  }
  const activatePrompt = async (prompt: Prompt) => {
    await api(`/prompts/${prompt.prompt_id}/activate`, { method: 'POST' })
    onChanged()
  }
  const previewPrompt = async (prompt: Prompt) => {
    const values = prompt.prompt_type === 'daily_digest'
      ? { summaries: 'Summary of video A\n\nSummary of video B', run_date: '2026-04-25', digest_language: 'zh' }
      : { transcript: 'This is a sample transcript excerpt.', video_title: 'Sample video', channel_name: 'Sample podcast', video_date: '2026-04-25', video_url: 'https://www.youtube.com/watch?v=sample123' }
    const result = await api<{ system_prompt: string; user_prompt: string }>(`/prompts/${prompt.prompt_id}/preview`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    setPreview(`SYSTEM:\n${result.system_prompt}\n\nUSER:\n${result.user_prompt}`)
  }
  const resetDefaults = async () => {
    await api('/prompts/reset-defaults', { method: 'POST' })
    onChanged()
  }
  const importYaml = async () => {
    await api('/prompts/import', { method: 'POST' })
    await onChanged()
  }
  const saveYaml = async () => {
    await api('/prompts/save', { method: 'POST' })
    await onChanged()
  }
  const exportYaml = async () => {
    const result = await api<{ filename: string; content: string }>('/prompts/export')
    downloadMarkdown(result.filename, result.content)
  }

  return (
    <section className="split wide prompt-layout">
      <div className="panel">
        <div className="panel-title">
          <h2>{t.videoPrompt}</h2>
          <div className="toolbar">
            <button className="ghost" onClick={importYaml}>{t.importYaml}</button>
            <button className="ghost" onClick={saveYaml}>{t.saveYaml}</button>
            <button className="ghost" onClick={exportYaml}>{t.exportYaml}</button>
            <button className="ghost" onClick={resetDefaults}>{t.resetDefault}</button>
          </div>
        </div>
        <label className="field-label">{t.promptScope}</label>
        <select value={scope} onChange={(event) => setScope(event.target.value)}>
          <option value="global">{t.globalScope}</option>
          {groups.map((group) => <option key={group.group_id} value={group.group_id}>{group.display_name || group.group_name}</option>)}
        </select>
        <label className="field-label">System Prompt</label>
        <textarea className="short" value={videoSystem} onChange={(event) => setVideoSystem(event.target.value)} />
        <label className="field-label">User Template</label>
        <textarea value={videoTemplate} onChange={(event) => setVideoTemplate(event.target.value)} />
        <button onClick={() => savePrompt('video_summary', 'Video Summary Prompt', videoSystem, videoTemplate)}>{t.save}</button>
        <h2 className="section-gap">{t.dailyPrompt}</h2>
        <label className="field-label">System Prompt</label>
        <textarea className="short" value={dailySystem} onChange={(event) => setDailySystem(event.target.value)} />
        <label className="field-label">User Template</label>
        <textarea value={dailyTemplate} onChange={(event) => setDailyTemplate(event.target.value)} />
        <button onClick={() => savePrompt('daily_digest', 'Daily Digest Prompt', dailySystem, dailyTemplate)}>{t.save}</button>
      </div>
      <div className="panel">
        <h2>{t.prompts}</h2>
        <div className="variable-help">
          <strong>{t.variables}</strong>
          <code>{'{{ transcript }}'}</code>
          <code>{'{{ summaries }}'}</code>
          <code>{'{{ run_date }}'}</code>
          <code>{'{{ digest_language }}'}</code>
          <code>{'{{ video_title }}'}</code>
          <code>{'{{ channel_name }}'}</code>
          <code>{'{{ video_date }}'}</code>
          <code>{'{{ video_url }}'}</code>
        </div>
        {preview ? <pre className="text-block preview">{preview}</pre> : null}
        {scopedPrompts.map((prompt) => (
          <div className="prompt-card" key={prompt.prompt_id}>
            <strong>{prompt.prompt_name}</strong>
            <span>{prompt.prompt_type} · {prompt.version} · {prompt.language}{prompt.group_display_name ? ` · ${prompt.group_display_name}` : ''}</span>
            <span className="actions">
              {prompt.is_active ? <span className="pill ok">{t.active}</span> : <button onClick={() => activatePrompt(prompt)}>{t.activate}</button>}
              <button className="ghost" onClick={() => previewPrompt(prompt)}>{t.promptPreview}</button>
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

function AutomationView({
  jobs,
  sources,
  groups,
  deliveryLogs,
  refreshTick,
  t,
  onChanged,
}: {
  jobs: ScheduledJob[]
  sources: Source[]
  groups: SourceGroup[]
  deliveryLogs: DeliveryLog[]
  refreshTick: number
  t: typeof copy.zh
  onChanged: () => void
}) {
  const blankJob: ScheduledJob = {
    job_id: 0,
    job_name: 'Default Daily Job',
    enabled: true,
    timezone: 'Asia/Shanghai',
    run_time: '07:00',
    digest_language: 'zh',
    scope_type: 'all_enabled',
    group_ids: [],
    source_ids: [],
    window_mode: 'last_1',
    max_videos_per_source: 10,
    process_missing_videos: true,
    retry_failed_once: true,
    send_empty_digest: true,
    telegram_enabled: true,
    email_enabled: false,
  }
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)
  const [form, setForm] = useState<ScheduledJob>(blankJob)
  const [message, setMessage] = useState('')
  const [showDeliveryLogs, setShowDeliveryLogs] = useState(false)
  const [expandedRunJobIds, setExpandedRunJobIds] = useState<number[]>([])
  const [runningJobId, setRunningJobId] = useState<number | null>(null)

  useEffect(() => {
    setMessage('')
  }, [refreshTick])

  const startNew = () => {
    setEditingId('new')
    setForm(blankJob)
  }
  const startEdit = (job: ScheduledJob) => {
    setEditingId(job.job_id)
    setForm({ ...job, group_ids: [...job.group_ids], source_ids: [...job.source_ids] })
  }
  const saveJob = async () => {
    const payload = { ...form, job_id: undefined }
    const path = editingId === 'new' ? '/scheduled-jobs' : `/scheduled-jobs/${form.job_id}`
    const method = editingId === 'new' ? 'POST' : 'PATCH'
    await api(path, { method, body: JSON.stringify(payload) })
    setEditingId(null)
    setMessage(t.save)
    await onChanged()
  }
  const deleteJob = async (job: ScheduledJob) => {
    try {
      await api(`/scheduled-jobs/${job.job_id}`, { method: 'DELETE' })
      setMessage(`Deleted: ${job.job_name}`)
      await onChanged()
    } catch (exc) {
      setMessage(errorMessage(exc))
    }
  }
  const runJob = async (job: ScheduledJob) => {
    setRunningJobId(job.job_id)
    setMessage(`${job.job_name} · ${t.regenerating}`)
    try {
      await api<{ status: string; job_id: number; message: string }>(`/scheduled-jobs/${job.job_id}/run-now`, {
        method: 'POST',
        body: JSON.stringify({ background: true }),
      })
      setMessage(`${job.job_name} · ${t.runSubmitted}`)
      await onChanged()
      window.setTimeout(() => {
        onChanged()
      }, 5000)
    } catch (exc) {
      setMessage(`Error: ${errorMessage(exc)}`)
    } finally {
      setRunningJobId(null)
    }
  }
  const toggleNumberLimit = (limited: boolean) => setForm({ ...form, max_videos_per_source: limited ? (form.max_videos_per_source || 10) : null })
  const setIds = (field: 'group_ids' | 'source_ids', id: number, checked: boolean) => {
    const current = new Set(form[field])
    if (checked) current.add(id)
    else current.delete(id)
    setForm({ ...form, [field]: [...current] })
  }
  const toggleJobRuns = (jobId: number) => {
    setExpandedRunJobIds((current) => (
      current.includes(jobId) ? current.filter((id) => id !== jobId) : [...current, jobId]
    ))
  }

  return (
    <section className="settings-grid">
      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.automationJobs}</h2>
            <p className="digest-meta">{jobs.length} jobs · Telegram / Email shared credentials</p>
          </div>
          <button onClick={startNew}>{t.addJob}</button>
        </div>
        {message ? <div className="notice compact neutral">{message}</div> : null}
        <div className="provider-config-list">
          {jobs.map((job) => (
            <div className={editingId === job.job_id ? 'settings-row expanded' : 'settings-row'} key={job.job_id}>
              <div className="settings-row-summary">
            <div className="settings-identity">
              <strong>{job.job_name}</strong>
              <span>{job.timezone} · {job.run_time} · {windowModeLabel(job.window_mode, t)} · {t.digestLanguage}: {job.digest_language === 'en' ? 'English' : '中文'}</span>
            </div>
                <div className="settings-meta-grid">
                  <span>{t.sourceScope}: {scopeLabel(job.scope_type, t)}</span>
                  <span>{t.deliveryChannels}: {[job.telegram_enabled ? 'Telegram' : '', job.email_enabled ? 'Email' : ''].filter(Boolean).join(' / ') || '-'}</span>
                </div>
                <span className={job.enabled ? 'pill ok' : 'pill'}>{job.enabled ? t.enabled : t.disabled}</span>
                <div className="row-actions">
                  <button className="ghost" onClick={() => toggleJobRuns(job.job_id)}>{expandedRunJobIds.includes(job.job_id) ? t.hideLogs : t.runHistory}</button>
                  <button disabled={runningJobId === job.job_id} onClick={() => runJob(job)}>{runningJobId === job.job_id ? t.regenerating : t.runNow}</button>
                  <button className="ghost" onClick={() => startEdit(job)}>{t.edit}</button>
                  <button className="danger" onClick={() => deleteJob(job)}>{t.delete}</button>
                </div>
              </div>
              {expandedRunJobIds.includes(job.job_id) ? (
                <div className="job-run-list">
                  {(job.recent_runs || []).slice(0, 5).map((run) => (
                    <div className="compact-list-item" key={run.run_id}>
                      <strong>{runDisplayTitle(run, job.job_name)}</strong>
                      <span>{runDisplayMeta(run, t)}</span>
                    </div>
                  ))}
                  {!(job.recent_runs || []).length ? <div className="compact-list-item"><strong>-</strong><span>{t.noOperationalItems}</span></div> : null}
                </div>
              ) : null}
              {editingId === job.job_id ? <JobForm form={form} setForm={setForm} groups={groups} sources={sources} t={t} setIds={setIds} toggleNumberLimit={toggleNumberLimit} saveJob={saveJob} cancel={() => setEditingId(null)} /> : null}
            </div>
          ))}
        </div>
        {editingId === 'new' ? (
          <div className="settings-row expanded">
            <JobForm form={form} setForm={setForm} groups={groups} sources={sources} t={t} setIds={setIds} toggleNumberLimit={toggleNumberLimit} saveJob={saveJob} cancel={() => setEditingId(null)} />
          </div>
        ) : null}
      </div>

      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.deliveryLogs}</h2>
            <p className="digest-meta">Telegram · Email · latest 5</p>
          </div>
          <button className="ghost" onClick={() => setShowDeliveryLogs(!showDeliveryLogs)}>{showDeliveryLogs ? t.hideLogs : t.showLogs}</button>
        </div>
        {showDeliveryLogs ? (
          <div className="compact-list delivery-log-list">
            {deliveryLogs.slice(0, 5).map((log) => (
              <div className="compact-list-item" key={log.delivery_id}>
                <strong>{log.scheduled_job_name || `run #${log.run_id || '-'}`} · {log.channel} · {log.status}</strong>
                <span>{compactDateTime(log.created_at)} · {log.target || '-'} {log.error_message ? `· ${log.error_message}` : ''}</span>
              </div>
            ))}
            {!deliveryLogs.length ? <div className="compact-list-item"><strong>-</strong><span>No delivery records</span></div> : null}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function JobForm({
  form,
  setForm,
  groups,
  sources,
  t,
  setIds,
  toggleNumberLimit,
  saveJob,
  cancel,
}: {
  form: ScheduledJob
  setForm: (form: ScheduledJob) => void
  groups: SourceGroup[]
  sources: Source[]
  t: typeof copy.zh
  setIds: (field: 'group_ids' | 'source_ids', id: number, checked: boolean) => void
  toggleNumberLimit: (limited: boolean) => void
  saveJob: () => void
  cancel: () => void
}) {
  const selectedGroupNames = groups
    .filter((group) => form.group_ids.includes(group.group_id))
    .map(groupLabel)
  const selectedSourceNames = sources
    .filter((source) => form.source_ids.includes(source.source_id))
    .map((source) => source.display_name || source.source_name)
  const selectedSummary = (items: string[], emptyLabel: string) => {
    if (!items.length) return emptyLabel
    const preview = items.slice(0, 3).join(', ')
    return items.length > 3 ? `${preview} +${items.length - 3}` : preview
  }

  return (
    <div className="settings-form">
      <label className="form-field wide"><span>{t.jobName}</span><input value={form.job_name} onChange={(event) => setForm({ ...form, job_name: event.target.value })} /></label>
      <label className="check-row"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />{t.enabled}</label>
      <label className="form-field"><span>{t.runTime}</span><input type="time" value={form.run_time} onChange={(event) => setForm({ ...form, run_time: event.target.value })} /></label>
      <label className="form-field"><span>{t.timezone}</span><input value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })} /></label>
      <label className="form-field"><span>{t.digestLanguage}</span><select value={form.digest_language} onChange={(event) => setForm({ ...form, digest_language: event.target.value as 'zh' | 'en' })}><option value="zh">中文</option><option value="en">English</option></select></label>
      <label className="form-field"><span>{t.windowMode}</span><select value={form.window_mode} onChange={(event) => setForm({ ...form, window_mode: event.target.value as ScheduledJob['window_mode'] })}><option value="last_1">{t.last1}</option><option value="last_3">{t.last3}</option><option value="last_7">{t.last7}</option><option value="all_time">{t.allTime}</option></select></label>
      <label className="form-field"><span>{t.sourceScope}</span><select value={form.scope_type} onChange={(event) => setForm({ ...form, scope_type: event.target.value as ScheduledJob['scope_type'] })}><option value="all_enabled">{t.scopeAll}</option><option value="groups">{t.selectedGroups}</option><option value="sources">{t.selectedSources}</option></select></label>
      <label className="check-row"><input type="checkbox" checked={form.max_videos_per_source !== null && form.max_videos_per_source !== undefined} onChange={(event) => toggleNumberLimit(event.target.checked)} />{t.limitVideos}</label>
      {form.max_videos_per_source !== null && form.max_videos_per_source !== undefined ? <label className="form-field"><span>{t.maxVideosPerSource}</span><input type="number" min="1" value={form.max_videos_per_source} onChange={(event) => setForm({ ...form, max_videos_per_source: Number(event.target.value) })} /></label> : null}
      {form.scope_type === 'groups' ? (
        <details className="scope-picker wide">
          <summary>
            <span>{t.selectedGroups}</span>
            <small>{selectedSummary(selectedGroupNames, t.ungrouped)}</small>
          </summary>
          <div className="scope-picker-list">
            {groups.map((group) => (
              <label className="check-row" key={group.group_id}>
                <input type="checkbox" checked={form.group_ids.includes(group.group_id)} onChange={(event) => setIds('group_ids', group.group_id, event.target.checked)} />
                {groupLabel(group)}
              </label>
            ))}
          </div>
        </details>
      ) : null}
      {form.scope_type === 'sources' ? (
        <details className="scope-picker wide">
          <summary>
            <span>{t.selectedSources}</span>
            <small>{selectedSummary(selectedSourceNames, t.ungrouped)}</small>
          </summary>
          <div className="scope-picker-list">
            {sources.map((source) => (
              <label className="check-row" key={source.source_id}>
                <input type="checkbox" checked={form.source_ids.includes(source.source_id)} onChange={(event) => setIds('source_ids', source.source_id, event.target.checked)} />
                {source.display_name || source.source_name}
              </label>
            ))}
          </div>
        </details>
      ) : null}
      <label className="check-row"><input type="checkbox" checked={form.process_missing_videos} onChange={(event) => setForm({ ...form, process_missing_videos: event.target.checked })} />{t.processMissingVideos}</label>
      <label className="check-row"><input type="checkbox" checked={form.retry_failed_once} onChange={(event) => setForm({ ...form, retry_failed_once: event.target.checked })} />{t.retryFailedOnce}</label>
      <label className="check-row"><input type="checkbox" checked={form.send_empty_digest} onChange={(event) => setForm({ ...form, send_empty_digest: event.target.checked })} />{t.sendEmptyDigest}</label>
      <label className="check-row"><input type="checkbox" checked={form.telegram_enabled} onChange={(event) => setForm({ ...form, telegram_enabled: event.target.checked })} />Telegram</label>
      <label className="check-row"><input type="checkbox" checked={form.email_enabled} onChange={(event) => setForm({ ...form, email_enabled: event.target.checked })} />Email</label>
      <div className="form-actions wide"><button onClick={saveJob}>{t.save}</button><button className="ghost" onClick={cancel}>{t.cancel}</button></div>
    </div>
  )
}

function scopeLabel(scope: ScheduledJob['scope_type'], t: typeof copy.zh) {
  if (scope === 'groups') return t.selectedGroups
  if (scope === 'sources') return t.selectedSources
  return t.scopeAll
}

function windowModeLabel(mode: ScheduledJob['window_mode'], t: typeof copy.zh) {
  const labels: Record<ScheduledJob['window_mode'], string> = {
    last_1: t.last1,
    last_3: t.last3,
    last_7: t.last7,
    all_time: t.allTime,
  }
  return labels[mode]
}

function SettingsView({
  health,
  models,
  providers,
  proxySettings,
  youtubeSettings,
  deliverySettings,
  refreshTick,
  t,
  onChanged,
}: {
  health: Health | null
  models: ModelProfile[]
  providers: LLMProvider[]
  proxySettings: ProxySettings | null
  youtubeSettings: YoutubeSettings | null
  deliverySettings: DeliverySettings | null
  refreshTick: number
  t: typeof copy.zh
  onChanged: () => void
}) {
  const [provider, setProvider] = useState(health?.llm_provider || providers[0]?.provider || 'gemini')
  const [modelName, setModelName] = useState('')
  const [showProviderForm, setShowProviderForm] = useState(false)
  const [showModelForm, setShowModelForm] = useState(false)
  const [editingModelId, setEditingModelId] = useState<number | null>(null)
  const [editProvider, setEditProvider] = useState(health?.llm_provider || providers[0]?.provider || 'gemini')
  const [editModelName, setEditModelName] = useState('')
  const [providerForm, setProviderForm] = useState({
    provider: '',
    provider_type: 'openai_compatible',
    display_name: '',
    base_url: '',
    api_key: '',
    default_model: '',
    enabled: true,
  })
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [editProviderForm, setEditProviderForm] = useState(providerForm)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [showYoutubeForm, setShowYoutubeForm] = useState(false)
  const [youtubeApiKey, setYoutubeApiKey] = useState('')
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [showProxyForm, setShowProxyForm] = useState(false)
  const [proxyForm, setProxyForm] = useState({
    enabled: false,
    youtube_proxy_http: '',
    youtube_proxy_https: '',
    iproyal_host: '',
    iproyal_port: '',
    iproyal_username: '',
    iproyal_password: '',
    yt_dlp_proxy: '',
  })
  const [proxyPasswordTouched, setProxyPasswordTouched] = useState(false)
  const [showTelegramForm, setShowTelegramForm] = useState(false)
  const [showEmailForm, setShowEmailForm] = useState(false)
  const [telegramForm, setTelegramForm] = useState({
    telegram_enabled: false,
    telegram_bot_token: '',
    telegram_chat_id: '',
    telegram_parse_mode: 'Markdown',
    telegram_send_as_file_if_too_long: true,
  })
  const [telegramTokenTouched, setTelegramTokenTouched] = useState(false)
  const [emailForm, setEmailForm] = useState({
    email_enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    smtp_use_tls: true,
    smtp_use_ssl: false,
    email_from: '',
    email_to: '',
    email_subject_template: 'YPBrief 每日播客日报 - {{ run_date }}',
    email_attach_markdown: true,
  })
  const [smtpPasswordTouched, setSmtpPasswordTouched] = useState(false)

  useEffect(() => {
    if (!providers.find((item) => item.provider === provider) && providers[0]?.provider) {
      setProvider(health?.llm_provider || providers[0].provider)
    }
  }, [providers, provider, health?.llm_provider])

  useEffect(() => {
    if (!proxySettings) return
    setProxyForm({
      enabled: proxySettings.enabled,
      youtube_proxy_http: proxySettings.youtube_proxy_http || '',
      youtube_proxy_https: proxySettings.youtube_proxy_https || '',
      iproyal_host: proxySettings.iproyal_host || '',
      iproyal_port: proxySettings.iproyal_port || '',
      iproyal_username: proxySettings.iproyal_username || '',
      iproyal_password: '',
      yt_dlp_proxy: proxySettings.yt_dlp_proxy || '',
    })
    setProxyPasswordTouched(false)
  }, [proxySettings])

  useEffect(() => {
    if (!deliverySettings) return
    setTelegramForm({
      telegram_enabled: deliverySettings.telegram_enabled,
      telegram_bot_token: '',
      telegram_chat_id: deliverySettings.telegram_chat_id || '',
      telegram_parse_mode: deliverySettings.telegram_parse_mode || 'Markdown',
      telegram_send_as_file_if_too_long: deliverySettings.telegram_send_as_file_if_too_long,
    })
    setEmailForm({
      email_enabled: deliverySettings.email_enabled,
      smtp_host: deliverySettings.smtp_host || '',
      smtp_port: deliverySettings.smtp_port || 587,
      smtp_username: deliverySettings.smtp_username || '',
      smtp_password: '',
      smtp_use_tls: deliverySettings.smtp_use_tls,
      smtp_use_ssl: deliverySettings.smtp_use_ssl,
      email_from: deliverySettings.email_from || '',
      email_to: (deliverySettings.email_to || []).join('\n'),
      email_subject_template: deliverySettings.email_subject_template || 'YPBrief 每日播客日报 - {{ run_date }}',
      email_attach_markdown: deliverySettings.email_attach_markdown,
    })
    setTelegramTokenTouched(false)
    setSmtpPasswordTouched(false)
  }, [deliverySettings])

  useEffect(() => {
    setTestResult(null)
  }, [refreshTick])

  const testEndpoint = async (path: string) => {
    const result = await api<Record<string, string | boolean>>(path, { method: 'POST' })
    setTestResult(formatTestResult(result))
  }
  const addProvider = async () => {
    if (!providerForm.provider.trim()) return
    await api('/llm-providers', {
      method: 'POST',
      body: JSON.stringify(providerForm),
    })
    setProviderForm({ provider: '', provider_type: 'openai_compatible', display_name: '', base_url: '', api_key: '', default_model: '', enabled: true })
    setShowProviderForm(false)
    onChanged()
  }
  const startEditProvider = (item: LLMProvider) => {
    setEditingProvider(editingProvider === item.provider ? null : item.provider)
    setEditProviderForm({
      provider: item.provider,
      provider_type: item.provider_type,
      display_name: item.display_name || '',
      base_url: item.base_url || '',
      api_key: '',
      default_model: item.default_model || '',
      enabled: Boolean(item.enabled),
    })
  }
  const saveProvider = async (item: LLMProvider) => {
    await api(`/llm-providers/${item.provider}`, {
      method: 'PATCH',
      body: JSON.stringify({
        provider_type: editProviderForm.provider_type,
        display_name: editProviderForm.display_name || null,
        base_url: editProviderForm.base_url || null,
        api_key: editProviderForm.api_key || null,
        default_model: editProviderForm.default_model || null,
        enabled: editProviderForm.enabled,
      }),
    })
    setEditingProvider(null)
    onChanged()
  }
  const deleteProvider = async (item: LLMProvider) => {
    await api(`/llm-providers/${item.provider}`, { method: 'DELETE' })
    onChanged()
  }
  const saveProxy = async () => {
    await api('/proxy-settings', {
      method: 'PATCH',
      body: JSON.stringify({
        enabled: proxyForm.enabled,
        youtube_proxy_http: proxyForm.youtube_proxy_http,
        youtube_proxy_https: proxyForm.youtube_proxy_https,
        iproyal_host: proxyForm.iproyal_host,
        iproyal_port: proxyForm.iproyal_port,
        iproyal_username: proxyForm.iproyal_username,
        iproyal_password: proxyPasswordTouched ? proxyForm.iproyal_password : undefined,
        yt_dlp_proxy: proxyForm.yt_dlp_proxy,
      }),
    })
    setProxyPasswordTouched(false)
    onChanged()
  }
  const saveYoutube = async () => {
    await api('/youtube-settings', {
      method: 'PATCH',
      body: JSON.stringify({ api_key: youtubeApiKey }),
    })
    setYoutubeApiKey('')
    setShowYoutubeForm(false)
    onChanged()
  }
  const savePassword = async () => {
    if (passwordForm.new_password.length < 8) {
      setTestResult({ ok: false, message: t.passwordTooShort })
      return
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setTestResult({ ok: false, message: t.passwordMismatch })
      return
    }
    const result = await api<{ token: string }>('/auth/password', {
      method: 'PATCH',
      body: JSON.stringify({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      }),
    })
    setAuthToken(result.token)
    setPasswordForm({ current_password: '', new_password: '', confirm_password: '' })
    setShowPasswordForm(false)
    setTestResult({ ok: true, message: t.passwordUpdated })
    onChanged()
  }
  const addModel = async () => {
    if (!modelName.trim()) return
    await api('/model-profiles', {
      method: 'POST',
      body: JSON.stringify({ provider, model_name: modelName.trim(), activate: true }),
    })
    setModelName('')
    setShowModelForm(false)
    onChanged()
  }
  const deleteModel = async (model: ModelProfile) => {
    await api(`/model-profiles/${model.model_id}`, { method: 'DELETE' })
    onChanged()
  }
  const activateModel = async (model: ModelProfile) => {
    if (model.model_id === 0) {
      await api('/model-profiles', {
        method: 'POST',
        body: JSON.stringify({
          provider: model.provider,
          model_name: model.model_name,
          activate: true,
        }),
      })
    } else {
      await api(`/model-profiles/${model.model_id}/activate`, { method: 'POST' })
    }
    onChanged()
  }
  const startEditModel = (model: ModelProfile) => {
    setEditingModelId(model.model_id)
    setEditProvider(model.provider)
    setEditModelName(model.model_name)
  }
  const saveModel = async (model: ModelProfile) => {
    await api(`/model-profiles/${model.model_id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        provider: editProvider,
        model_name: editModelName,
        is_active: model.is_active ? true : null,
      }),
    })
    setEditingModelId(null)
    onChanged()
  }
  const testModel = async (model: ModelProfile) => {
    const result = await api<Record<string, string | boolean>>('/model-profiles/test', {
      method: 'POST',
      body: JSON.stringify({ provider: model.provider, model_name: model.model_name }),
    })
    setTestResult(formatTestResult(result))
  }
  const saveTelegram = async () => {
    await api('/delivery-settings', {
      method: 'PATCH',
      body: JSON.stringify({
        ...telegramForm,
        telegram_bot_token: telegramTokenTouched ? telegramForm.telegram_bot_token : undefined,
      }),
    })
    setTelegramTokenTouched(false)
    setShowTelegramForm(false)
    onChanged()
  }
  const saveEmail = async () => {
    await api('/delivery-settings', {
      method: 'PATCH',
      body: JSON.stringify({
        ...emailForm,
        smtp_password: smtpPasswordTouched ? emailForm.smtp_password : undefined,
        email_to: emailForm.email_to,
      }),
    })
    setSmtpPasswordTouched(false)
    setShowEmailForm(false)
    onChanged()
  }
  const testDelivery = async (path: string) => {
    const result = await api<Record<string, string | boolean>>(path, { method: 'POST' })
    setTestResult({ ok: result.status === 'success', message: `${result.channel || 'delivery'} · ${result.status || 'skipped'} · ${result.error_message || ''}` })
    onChanged()
  }
  const rows = health ? [
    ['YouTube API', health.youtube_api_key],
    ['Proxy', health.proxy],
  ] : []
  return (
    <section className="settings-grid">
      <div className="panel current-panel">
        <h2>{t.currentModel}</h2>
        <div className="current-model">
          <strong>{health?.llm_provider || '-'}</strong>
          <span>{health?.llm_model || '-'}</span>
          {health?.active_model ? <span className="pill ok">{t.active}</span> : <span className="pill">key.env</span>}
        </div>
      </div>

      <div className="panel health-panel">
        <h2>{t.health}</h2>
        <div className="toolbar settings-actions">
          <button onClick={() => testEndpoint('/health/test-youtube')}>{t.testYoutube}</button>
          <button onClick={() => testEndpoint('/health/test-llm')}>{t.testLlm}</button>
          <button onClick={() => testEndpoint('/health/test-proxy')}>{t.testProxy}</button>
          <button onClick={() => testEndpoint('/health/test-database')}>{t.testDatabase}</button>
        </div>
        {rows.map(([label, ok]) => (
          <div className="health-row" key={String(label)}>
            <span>{label}</span>
            <span className={ok ? 'pill ok' : 'pill'}>{ok ? t.configured : t.missing}</span>
          </div>
        ))}
        <p className="path">{health?.database_path}</p>
        <p className="path">{health?.export_dir}</p>
      </div>

      {testResult ? <div className={testResult.ok ? 'notice compact neutral settings-span' : 'notice compact settings-span'}>{testResult.message}</div> : null}

      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.accessPassword}</h2>
            <p className="digest-meta">YPBRIEF_ACCESS_PASSWORD · key.env</p>
          </div>
          <button className="ghost" onClick={() => setShowPasswordForm(!showPasswordForm)}>{showPasswordForm ? t.cancel : t.changePassword}</button>
        </div>
        <div className="settings-row-summary proxy-summary">
          <div className="settings-identity">
            <strong>{t.accessPassword}</strong>
            <span>{t.loginSubtitle}</span>
          </div>
          <div className="settings-meta-grid">
            <span>key.env: YPBRIEF_ACCESS_PASSWORD</span>
            <span>{t.configSource}: key.env / database / runtime</span>
          </div>
          <span className="pill ok">{t.configured}</span>
        </div>
        {showPasswordForm ? (
          <div className="settings-form">
            <label className="form-field">
              <span>{t.currentPassword}</span>
              <input
                type="password"
                value={passwordForm.current_password}
                onChange={(event) => setPasswordForm({ ...passwordForm, current_password: event.target.value })}
              />
            </label>
            <label className="form-field">
              <span>{t.newPassword}</span>
              <input
                type="password"
                value={passwordForm.new_password}
                onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })}
              />
            </label>
            <label className="form-field">
              <span>{t.confirmPassword}</span>
              <input
                type="password"
                value={passwordForm.confirm_password}
                onChange={(event) => setPasswordForm({ ...passwordForm, confirm_password: event.target.value })}
              />
            </label>
            <div className="form-actions wide">
              <button
                disabled={!passwordForm.current_password || !passwordForm.new_password || !passwordForm.confirm_password}
                onClick={savePassword}
              >
                {t.save}
              </button>
              <button
                className="ghost"
                onClick={() => {
                  setShowPasswordForm(false)
                  setPasswordForm({ current_password: '', new_password: '', confirm_password: '' })
                }}
              >
                {t.cancel}
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.deliverySettings}</h2>
            <p className="digest-meta">Telegram · Email</p>
          </div>
        </div>
        <div className="settings-row">
          <div className="settings-row-summary">
            <div className="settings-identity">
              <strong>{t.telegramDelivery}</strong>
              <span>{deliverySettings?.telegram_chat_id || '-'}</span>
            </div>
            <div className="settings-meta-grid">
              <span>{t.botToken}: {deliverySettings?.telegram_bot_token_hint || '-'}</span>
              <span>Parse: {deliverySettings?.telegram_parse_mode || 'Markdown'}</span>
            </div>
            <span className={deliverySettings?.telegram_enabled ? 'pill ok' : 'pill'}>{deliverySettings?.telegram_enabled ? t.enabled : t.disabled}</span>
            <div className="row-actions">
              <button className="ghost" onClick={() => setShowTelegramForm(!showTelegramForm)}>{showTelegramForm ? t.cancel : t.edit}</button>
              <button onClick={() => testDelivery('/delivery/test-telegram')}>{t.testTelegram}</button>
            </div>
          </div>
          {showTelegramForm ? (
            <div className="settings-form">
              <label className="check-row wide">
                <input type="checkbox" checked={telegramForm.telegram_enabled} onChange={(event) => setTelegramForm({ ...telegramForm, telegram_enabled: event.target.checked })} />
                {t.enabled}
              </label>
              <label className="form-field wide">
                <span>{t.botToken}</span>
                <input type="password" value={telegramForm.telegram_bot_token} placeholder={deliverySettings?.telegram_bot_token_configured ? t.configured : t.missing} onChange={(event) => { setTelegramTokenTouched(true); setTelegramForm({ ...telegramForm, telegram_bot_token: event.target.value }) }} />
              </label>
              <label className="form-field">
                <span>{t.chatId}</span>
                <input value={telegramForm.telegram_chat_id} onChange={(event) => setTelegramForm({ ...telegramForm, telegram_chat_id: event.target.value })} />
              </label>
              <label className="form-field">
                <span>Parse Mode</span>
                <select value={telegramForm.telegram_parse_mode} onChange={(event) => setTelegramForm({ ...telegramForm, telegram_parse_mode: event.target.value })}>
                  <option value="Markdown">Markdown</option>
                  <option value="HTML">HTML</option>
                  <option value="">Plain</option>
                </select>
              </label>
              <div className="form-actions wide">
                <button onClick={saveTelegram}>{t.save}</button>
                <button className="ghost" onClick={() => setShowTelegramForm(false)}>{t.cancel}</button>
              </div>
            </div>
          ) : null}
        </div>
        <div className="settings-row">
          <div className="settings-row-summary">
            <div className="settings-identity">
              <strong>{t.emailDelivery}</strong>
              <span>{deliverySettings?.email_to?.join(', ') || '-'}</span>
            </div>
            <div className="settings-meta-grid">
              <span>{t.smtpHost}: {deliverySettings?.smtp_host || '-'}</span>
              <span>{t.emailFrom}: {deliverySettings?.email_from || '-'}</span>
            </div>
            <span className={deliverySettings?.email_enabled ? 'pill ok' : 'pill'}>{deliverySettings?.email_enabled ? t.enabled : t.disabled}</span>
            <div className="row-actions">
              <button className="ghost" onClick={() => setShowEmailForm(!showEmailForm)}>{showEmailForm ? t.cancel : t.edit}</button>
              <button onClick={() => testDelivery('/delivery/test-email')}>{t.testEmail}</button>
            </div>
          </div>
          {showEmailForm ? (
            <div className="settings-form">
              <label className="check-row wide">
                <input type="checkbox" checked={emailForm.email_enabled} onChange={(event) => setEmailForm({ ...emailForm, email_enabled: event.target.checked })} />
                {t.enabled}
              </label>
              <label className="form-field">
                <span>{t.smtpHost}</span>
                <input value={emailForm.smtp_host} onChange={(event) => setEmailForm({ ...emailForm, smtp_host: event.target.value })} />
              </label>
              <label className="form-field">
                <span>{t.smtpPort}</span>
                <input type="number" value={emailForm.smtp_port} onChange={(event) => setEmailForm({ ...emailForm, smtp_port: Number(event.target.value) })} />
              </label>
              <label className="form-field">
                <span>{t.smtpUsername}</span>
                <input value={emailForm.smtp_username} onChange={(event) => setEmailForm({ ...emailForm, smtp_username: event.target.value })} />
              </label>
              <label className="form-field">
                <span>{t.smtpPassword}</span>
                <input type="password" value={emailForm.smtp_password} placeholder={deliverySettings?.smtp_password_configured ? t.configured : t.missing} onChange={(event) => { setSmtpPasswordTouched(true); setEmailForm({ ...emailForm, smtp_password: event.target.value }) }} />
              </label>
              <label className="form-field">
                <span>{t.emailFrom}</span>
                <input value={emailForm.email_from} onChange={(event) => setEmailForm({ ...emailForm, email_from: event.target.value })} />
              </label>
              <label className="form-field wide">
                <span>{t.emailTo}</span>
                <textarea value={emailForm.email_to} onChange={(event) => setEmailForm({ ...emailForm, email_to: event.target.value })} />
              </label>
              <label className="form-field wide">
                <span>{t.subjectTemplate}</span>
                <input value={emailForm.email_subject_template} onChange={(event) => setEmailForm({ ...emailForm, email_subject_template: event.target.value })} />
              </label>
              <label className="check-row">
                <input type="checkbox" checked={emailForm.smtp_use_tls} onChange={(event) => setEmailForm({ ...emailForm, smtp_use_tls: event.target.checked })} />
                TLS
              </label>
              <label className="check-row">
                <input type="checkbox" checked={emailForm.smtp_use_ssl} onChange={(event) => setEmailForm({ ...emailForm, smtp_use_ssl: event.target.checked })} />
                SSL
              </label>
              <div className="form-actions wide">
                <button onClick={saveEmail}>{t.save}</button>
                <button className="ghost" onClick={() => setShowEmailForm(false)}>{t.cancel}</button>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.youtubeSettings}</h2>
            <p className="digest-meta">{youtubeSettings?.api_key_hint || '-'}</p>
          </div>
          <div className="toolbar">
            <button className="ghost" onClick={() => setShowYoutubeForm(!showYoutubeForm)}>{showYoutubeForm ? t.cancel : t.edit}</button>
            <button onClick={() => testEndpoint('/health/test-youtube')}>{t.testYoutube}</button>
          </div>
        </div>
        <div className="settings-row-summary proxy-summary">
          <div className="settings-identity">
            <strong>YouTube Data API</strong>
            <span>{t.apiKeyHint}: {youtubeSettings?.api_key_hint || '-'}</span>
          </div>
          <div className="settings-meta-grid">
            <span>YOUTUBE_DATA_API_KEY</span>
            <span>{youtubeSettings?.configured ? t.configured : t.missing}</span>
          </div>
          <span className={youtubeSettings?.configured ? 'pill ok' : 'pill'}>{youtubeSettings?.configured ? t.configured : t.missing}</span>
        </div>
        {showYoutubeForm ? (
          <div className="settings-form">
            <label className="form-field wide">
              <span>{t.youtubeApiKey}</span>
              <input
                type="password"
                value={youtubeApiKey}
                placeholder={youtubeSettings?.api_key_configured ? '••••••••' : ''}
                onChange={(event) => setYoutubeApiKey(event.target.value)}
              />
            </label>
            <div className="form-actions wide">
              <button disabled={!youtubeApiKey.trim()} onClick={saveYoutube}>{t.save}</button>
              <button className="ghost" onClick={() => { setShowYoutubeForm(false); setYoutubeApiKey('') }}>{t.cancel}</button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.proxySettings}</h2>
            <p className="digest-meta">{proxySettings?.effective_proxy || '-'}</p>
          </div>
          <div className="toolbar">
            <button className="ghost" onClick={() => setShowProxyForm(!showProxyForm)}>{showProxyForm ? t.cancel : t.edit}</button>
            <button onClick={() => testEndpoint('/health/test-proxy')}>{t.testProxy}</button>
          </div>
        </div>
        <div className="settings-row-summary proxy-summary">
          <div className="settings-identity">
            <strong>{proxySettings?.enabled ? t.enabled : t.disabled}</strong>
            <span>{t.proxyStatus}: {proxySettings?.configured ? t.configured : t.missing}</span>
          </div>
          <div className="settings-meta-grid">
            <span>{t.proxyEffective}: <code>{proxySettings?.effective_proxy || '-'}</code></span>
            <span>{t.proxyYtDlp}: <code>{proxySettings?.effective_yt_dlp_proxy || '-'}</code></span>
          </div>
          <span className={proxySettings?.enabled ? 'pill ok' : 'pill'}>{proxySettings?.enabled ? t.enabled : t.disabled}</span>
          <span className={proxySettings?.iproyal_password_configured ? 'pill ok' : 'pill'}>{proxySettings?.iproyal_password_configured ? t.configured : t.missing}</span>
        </div>
        {showProxyForm ? (
          <div className="settings-form proxy-form">
            <label className="check-row wide proxy-toggle">
              <input type="checkbox" checked={proxyForm.enabled} onChange={(event) => setProxyForm({ ...proxyForm, enabled: event.target.checked })} />
              {t.proxyEnabled}
            </label>
            <label className="form-field">
              <span>IPRoyal Host</span>
              <input value={proxyForm.iproyal_host} onChange={(event) => setProxyForm({ ...proxyForm, iproyal_host: event.target.value })} placeholder="proxy.example.com" />
            </label>
            <label className="form-field">
              <span>IPRoyal Port</span>
              <input value={proxyForm.iproyal_port} onChange={(event) => setProxyForm({ ...proxyForm, iproyal_port: event.target.value })} placeholder="12321" />
            </label>
            <label className="form-field">
              <span>IPRoyal Username</span>
              <input value={proxyForm.iproyal_username} onChange={(event) => setProxyForm({ ...proxyForm, iproyal_username: event.target.value })} placeholder="session token" />
            </label>
            <label className="form-field">
              <span>IPRoyal Password</span>
              <input
                type="password"
                value={proxyForm.iproyal_password}
                onChange={(event) => {
                  setProxyPasswordTouched(true)
                  setProxyForm({ ...proxyForm, iproyal_password: event.target.value })
                }}
                placeholder={proxySettings?.iproyal_password_configured ? t.configured : t.missing}
              />
            </label>
            <label className="form-field wide">
              <span>HTTPS Proxy</span>
              <input value={proxyForm.youtube_proxy_https} onChange={(event) => setProxyForm({ ...proxyForm, youtube_proxy_https: event.target.value })} placeholder="https://proxy.example.test:443" />
            </label>
            <label className="form-field wide">
              <span>HTTP Proxy</span>
              <input value={proxyForm.youtube_proxy_http} onChange={(event) => setProxyForm({ ...proxyForm, youtube_proxy_http: event.target.value })} placeholder="http://proxy.example.test:80" />
            </label>
            <label className="form-field wide">
              <span>{t.proxyYtDlp}</span>
              <input value={proxyForm.yt_dlp_proxy} onChange={(event) => setProxyForm({ ...proxyForm, yt_dlp_proxy: event.target.value })} placeholder="http://user:pass@host:port" />
            </label>
            <div className="form-actions wide">
              <button onClick={saveProxy}>{t.save}</button>
              <button className="ghost" onClick={() => setShowProxyForm(false)}>{t.cancel}</button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.providers}</h2>
            <p className="digest-meta">{t.apiKey}: configured / missing</p>
          </div>
          <button onClick={() => setShowProviderForm(!showProviderForm)}>{showProviderForm ? t.cancel : t.addProvider}</button>
        </div>

        {showProviderForm ? (
          <div className="settings-form provider-add-form">
            <label className="form-field">
              <span>Provider ID</span>
              <input value={providerForm.provider} onChange={(event) => setProviderForm({ ...providerForm, provider: event.target.value })} placeholder="deepseek, grok, custom_vendor" />
            </label>
            <label className="form-field">
              <span>{t.providerType}</span>
              <select value={providerForm.provider_type} onChange={(event) => setProviderForm({ ...providerForm, provider_type: event.target.value })}>
                <ProviderTypeOptions />
              </select>
            </label>
            <label className="form-field">
              <span>{t.displayName}</span>
              <input value={providerForm.display_name} onChange={(event) => setProviderForm({ ...providerForm, display_name: event.target.value })} placeholder="DeepSeek / Grok / internal gateway" />
            </label>
            <label className="form-field">
              <span>{t.defaultModel}</span>
              <input value={providerForm.default_model} onChange={(event) => setProviderForm({ ...providerForm, default_model: event.target.value })} placeholder="model name" />
            </label>
            <label className="form-field wide">
              <span>{t.baseUrl}</span>
              <input value={providerForm.base_url} onChange={(event) => setProviderForm({ ...providerForm, base_url: event.target.value })} placeholder="https://api.example.com/v1" />
            </label>
            <label className="form-field wide">
              <span>{t.apiKey}</span>
              <input type="password" value={providerForm.api_key} onChange={(event) => setProviderForm({ ...providerForm, api_key: event.target.value })} placeholder="Stored server-side, never returned to browser" />
            </label>
            <div className="form-actions wide">
              <button onClick={addProvider}>{t.save}</button>
              <button className="ghost" onClick={() => setShowProviderForm(false)}>{t.cancel}</button>
            </div>
          </div>
        ) : null}

        <div className="provider-config-list">
          {providers.map((item) => (
            <div className={editingProvider === item.provider ? 'settings-row expanded' : 'settings-row'} key={item.provider}>
              <div className="settings-row-summary">
                <div className="settings-identity">
                  <strong>{item.display_name || item.provider}</strong>
                  <span>{item.provider} · {item.provider_type} · {item.source}</span>
                </div>
                <div className="settings-meta-grid">
                  <span>{t.baseUrl}: <code>{item.base_url || '-'}</code></span>
                  <span>{t.defaultModel}: <code>{item.default_model || '-'}</code></span>
                </div>
                <span className={item.api_key_configured ? 'pill ok' : 'pill'}>{item.api_key_configured ? t.configured : t.missing}</span>
                <div className="row-actions">
                  <button className="ghost" onClick={() => startEditProvider(item)}>{editingProvider === item.provider ? t.cancel : t.edit}</button>
                  <button className="danger" onClick={() => deleteProvider(item)}>{item.is_builtin ? 'Reset' : t.delete}</button>
                </div>
              </div>
              {editingProvider === item.provider ? (
                <div className="settings-form provider-edit-form">
                  <label className="form-field">
                    <span>{t.providerType}</span>
                    <select value={editProviderForm.provider_type} onChange={(event) => setEditProviderForm({ ...editProviderForm, provider_type: event.target.value })}>
                      <ProviderTypeOptions />
                    </select>
                  </label>
                  <label className="form-field">
                    <span>{t.displayName}</span>
                    <input value={editProviderForm.display_name} onChange={(event) => setEditProviderForm({ ...editProviderForm, display_name: event.target.value })} />
                  </label>
                  <label className="form-field wide">
                    <span>{t.baseUrl}</span>
                    <input value={editProviderForm.base_url} onChange={(event) => setEditProviderForm({ ...editProviderForm, base_url: event.target.value })} placeholder="https://api.example.com/v1" />
                  </label>
                  <label className="form-field">
                    <span>{t.defaultModel}</span>
                    <input value={editProviderForm.default_model} onChange={(event) => setEditProviderForm({ ...editProviderForm, default_model: event.target.value })} />
                  </label>
                  <label className="form-field">
                    <span>{t.apiKey}</span>
                    <input type="password" value={editProviderForm.api_key} onChange={(event) => setEditProviderForm({ ...editProviderForm, api_key: event.target.value })} placeholder={item.api_key_configured ? t.configured : t.missing} />
                  </label>
                  <label className="check-row wide">
                    <input type="checkbox" checked={editProviderForm.enabled} onChange={(event) => setEditProviderForm({ ...editProviderForm, enabled: event.target.checked })} />
                    {t.enabled}
                  </label>
                  <div className="form-actions wide">
                    <button onClick={() => saveProvider(item)}>{t.save}</button>
                    <button className="ghost" onClick={() => setEditingProvider(null)}>{t.cancel}</button>
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <div className="panel settings-span">
        <div className="settings-section-header">
          <div>
            <h2>{t.modelProfiles}</h2>
            <p className="digest-meta">{health?.llm_provider || '-'} / {health?.llm_model || '-'}</p>
          </div>
          <button onClick={() => setShowModelForm(!showModelForm)}>{showModelForm ? t.cancel : t.add}</button>
        </div>

        {showModelForm ? (
          <div className="settings-form model-add-form">
            <label className="form-field">
              <span>Provider</span>
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                <ProviderOptions providers={providers} />
              </select>
            </label>
            <label className="form-field">
              <span>Model</span>
              <input value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder="model name" />
            </label>
            <div className="form-actions wide">
              <button onClick={addModel}>{t.save}</button>
              <button className="ghost" onClick={() => setShowModelForm(false)}>{t.cancel}</button>
            </div>
          </div>
        ) : null}

        <table className="model-table">
          <thead><tr><th>Provider</th><th>Model</th><th>{t.status}</th><th>{t.actions}</th></tr></thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.model_id || `${model.provider}-${model.model_name}`}>
                <td>
                  {editingModelId === model.model_id ? (
                    <select value={editProvider} onChange={(event) => setEditProvider(event.target.value)}>
                      <ProviderOptions providers={providers} />
                    </select>
                  ) : model.provider}
                </td>
                <td>
                  {editingModelId === model.model_id ? (
                    <input value={editModelName} onChange={(event) => setEditModelName(event.target.value)} />
                  ) : <code>{model.model_name}</code>}
                </td>
                <td>{model.is_active ? <span className="pill ok">{t.active}</span> : <span className="pill">{t.disabled}</span>}</td>
                <td className="actions">
                  {model.model_id === 0 ? <span className="pill">key.env</span> : null}
                  <button className="ghost" onClick={() => testModel(model)}>{t.test}</button>
                  {!model.is_active ? <button onClick={() => activateModel(model)}>{t.enable}</button> : null}
                  {editingModelId === model.model_id ? (
                    <>
                      <button onClick={() => saveModel(model)}>{t.save}</button>
                      <button className="ghost" onClick={() => setEditingModelId(null)}>{t.cancel}</button>
                    </>
                  ) : model.model_id !== 0 ? <button className="ghost" onClick={() => startEditModel(model)}>{t.edit}</button> : null}
                  {model.model_id !== 0 ? <button className="danger" onClick={() => deleteModel(model)}>{t.delete}</button> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ProviderOptions({ providers }: { providers: LLMProvider[] }) {
  return (
    <>
      {providers.map((item) => <option key={item.provider} value={item.provider}>{item.display_name || item.provider}</option>)}
    </>
  )
}

function DeliveryChannelPicker({
  label,
  channels,
  onChange,
  t,
}: {
  label?: string
  channels: DeliveryChannels
  onChange: (channels: DeliveryChannels) => void
  t: typeof copy.zh
}) {
  return (
    <div className="delivery-picker">
      {label ? <span className="delivery-picker-label">{label}</span> : null}
      <label>
        <input
          type="checkbox"
          checked={channels.telegram}
          onChange={(event) => onChange({ ...channels, telegram: event.target.checked })}
        />
        {t.pushTelegram}
      </label>
      <label>
        <input
          type="checkbox"
          checked={channels.email}
          onChange={(event) => onChange({ ...channels, email: event.target.checked })}
        />
        {t.pushEmail}
      </label>
    </div>
  )
}

function DeliveryControls({
  summaryId,
  channels,
  onChannelsChange,
  onDeliver,
  delivering,
  t,
}: {
  summaryId?: number | null
  channels: DeliveryChannels
  onChannelsChange: (channels: DeliveryChannels) => void
  onDeliver: () => void
  delivering: boolean
  t: typeof copy.zh
}) {
  return (
    <div className="delivery-controls">
      <DeliveryChannelPicker channels={channels} onChange={onChannelsChange} t={t} />
      <button className="delivery-submit" disabled={!summaryId || delivering} onClick={onDeliver}>
        {delivering ? t.delivering : t.deliver}
      </button>
    </div>
  )
}

function formatTestResult(result: Record<string, string | boolean>): { ok: boolean; message: string } {
  const ok = Boolean(result.ok ?? result.configured)
  const provider = result.provider ? `${result.provider}` : ''
  const model = result.model ? `${result.model}` : ''
  const scope = [provider, model].filter(Boolean).join(' / ')
  const rawMessage = String(result.message || (ok ? 'Connection ok' : 'Connection failed'))
  const status = ok ? '测试通过' : '测试未通过'
  return {
    ok,
    message: scope ? `${status}: ${scope} - ${rawMessage}` : `${status}: ${rawMessage}`,
  }
}

function errorMessage(exc: unknown): string {
  return exc instanceof Error ? exc.message : String(exc)
}

function ProviderTypeOptions() {
  return (
    <>
      <option value="openai_compatible">OpenAI compatible</option>
      <option value="gemini">Gemini</option>
      <option value="claude">Claude</option>
    </>
  )
}

function CompactVideoList({ videos, t, onOpen }: { videos: Video[]; t: typeof copy.zh; onOpen?: (videoId: string) => void }) {
  return (
    <div className="compact-list">
      {videos.slice(0, 5).map((video) => (
        <button
          className={onOpen ? 'compact-list-item clickable' : 'compact-list-item'}
          key={video.video_id}
          onClick={onOpen ? () => onOpen(video.video_id) : undefined}
        >
          <strong>{video.video_title}</strong>
          <span>{video.channel_name} · {video.video_date} · {statusLabel(video.status, t)} ({video.status})</span>
        </button>
      ))}
    </div>
  )
}

function MetadataTable({ data }: { data: Record<string, unknown> }) {
  return (
    <table>
      <tbody>
        {Object.entries(data).map(([key, value]) => {
          if (key === 'transcript_clean' || key === 'transcript_raw_vtt' || key === 'transcript_raw_json' || key === 'summary') return null
          return (
            <tr key={key}>
              <th>{key}</th>
              <td><pre className="json-cell">{typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')}</pre></td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function RunVideoList({
  rows,
  onOpenVideo,
  onRetry,
  retryingKey,
  retryLabel = 'Retry',
}: {
  rows: DigestVideo[]
  onOpenVideo?: (videoId: string) => void
  onRetry?: (row: DigestVideo) => void
  retryingKey?: string
  retryLabel?: string
}) {
  if (!rows.length) return <p>No records</p>
  return (
    <div className="compact-list">
      {rows.map((row, index) => {
        const key = `${row.run_id || ''}-${row.video_id}-${row.source_id || ''}`
        const canRetry = Boolean(onRetry && row.run_id && (row.status === 'failed' || row.status === 'skipped'))
        const showOperational = Boolean(onRetry) || row.status !== 'included'
        const metaLine = `${row.channel_name || '-'} · ${row.video_date || '-'} · ${row.video_id}${showOperational ? ` · ${row.status}` : ''}`
        const sourceLine = showOperational
          ? `${row.display_name || row.source_name || `source=${row.source_id || '-'}`} · action=${row.action || '-'} · summary=${row.video_summary_id || row.summary_id || '-'}`
          : `${row.display_name || row.source_name || '-'}`
        return (
          <div className="run-video-row" key={`${row.video_id}-${row.source_id}-${index}`}>
            <div>
              {onOpenVideo ? (
                <button className="text-button" type="button" onClick={() => onOpenVideo(row.video_id)}>
                  {row.video_title || row.video_id}
                </button>
              ) : (
                <strong>{row.video_title || row.video_id}</strong>
              )}
              <span className="run-video-meta">{metaLine}</span>
              <span className="run-video-meta">{sourceLine}</span>
              {row.error_message ? <span className="run-video-error">{row.error_message}</span> : null}
            </div>
            {canRetry ? <button className="ghost" disabled={retryingKey === key} onClick={() => onRetry?.(row)}>{retryLabel}</button> : null}
          </div>
        )
      })}
    </div>
  )
}

function statusLabel(status: string, t: typeof copy.zh) {
  const labels: Record<string, string> = {
    new: t.statusNew,
    cleaned: t.statusCleaned,
    summarized: t.statusSummarized,
    failed: t.statusFailed,
    skipped: t.statusSkipped,
  }
  return labels[status] || status
}

export default App
