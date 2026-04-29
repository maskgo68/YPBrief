export type Language = 'zh' | 'en'
export type Page = 'dashboard' | 'sources' | 'videos' | 'digests' | 'prompts' | 'automation' | 'settings'
export type VideoTab = 'summary' | 'transcript' | 'vtt' | 'metadata'
export type DigestTab = 'summary' | 'included' | 'failed' | 'metadata'
export type VideoMode = 'reading' | 'maintenance'

export type Dashboard = {
  stats: Record<string, number>
  latest_digest: Digest | null
  latest_run: DigestRun | null
  recent_videos: Video[]
  recent_run_videos: DigestVideo[]
}

export type Digest = {
  summary_id: number
  range_start: string
  range_end?: string | null
  model_provider: string
  model_name: string
  prompt_version?: string | null
  created_at: string
  preview?: string
  content_markdown?: string
  included_count?: number
  failed_count?: number
  skipped_count?: number
  latest_run_id?: number | null
  latest_run_type?: string | null
  latest_run_status?: string | null
  latest_run_window_start?: string | null
  latest_run_window_end?: string | null
  latest_run_included_count?: number | null
  latest_run_failed_count?: number | null
  latest_run_skipped_count?: number | null
  latest_run_created_at?: string | null
  latest_run_completed_at?: string | null
  scheduled_job_id?: number | null
  scheduled_job_name?: string | null
  runs?: DigestRun[]
  videos?: DigestVideo[]
  included_videos?: DigestVideo[]
  failed_videos?: DigestVideo[]
}

export type Source = {
  source_id: number
  source_type: string
  source_name: string
  display_name?: string | null
  youtube_id: string
  url?: string
  channel_name?: string | null
  playlist_id?: string | null
  enabled: number
  group_id?: number | null
  group_name?: string | null
  group_display_name?: string | null
  last_checked_at?: string | null
  last_error?: string | null
}

export type SourceGroup = {
  group_id: number
  group_name: string
  display_name?: string | null
  description?: string | null
  enabled: number
  digest_title?: string | null
  digest_language: string
  run_time: string
  timezone: string
  max_videos_per_source: number
  telegram_enabled?: number | null
  email_enabled?: number | null
  source_count?: number
}

export type Video = {
  video_id: string
  video_title: string
  video_url?: string
  video_date?: string | null
  channel_name: string
  status: string
  summary_latest_id?: number | null
  has_transcript?: boolean
  fetched_at?: string | null
  cleaned_at?: string | null
  summarized_at?: string | null
  error_message?: string | null
}

export type VideoDetail = Video & {
  fetched_at?: string | null
  cleaned_at?: string | null
  summarized_at?: string | null
  transcript_clean?: string | null
  transcript_raw_vtt?: string | null
  transcript_raw_json?: string | null
  duration?: number | null
  created_at?: string | null
  updated_at?: string | null
  sources?: Array<Record<string, string | number | null>>
  summary?: Digest | null
}

export type QuickVideoProcessResult = {
  video_id: string
  summary_id?: number | null
  reused: boolean
  status: string
  source_vtt?: string | null
  transcript_md?: string | null
  summary_md?: string | null
}

export type Prompt = {
  prompt_id: number
  prompt_type: string
  prompt_name: string
  version: string
  language: string
  is_active: number
  group_id?: number | null
  group_name?: string | null
  group_display_name?: string | null
  user_template: string
  system_prompt?: string
  variables?: string[]
  created_at?: string
  updated_at?: string
}

export type Health = {
  status: string
  database_path: string
  export_dir: string
  youtube_api_key: boolean
  llm_provider: string
  llm_model: string
  gemini_api_key: boolean
  openai_api_key: boolean
  proxy: boolean
  active_model?: ModelProfile | null
  provider_keys?: Record<string, boolean>
}

export type AuthStatus = {
  auth_required: boolean
  authenticated: boolean
}

export type ProxySettings = {
  enabled: boolean
  configured: boolean
  youtube_proxy_http: string
  youtube_proxy_https: string
  iproyal_host: string
  iproyal_port: string
  iproyal_username: string
  iproyal_password_configured: boolean
  yt_dlp_proxy: string
  effective_proxy: string
  effective_yt_dlp_proxy: string
}

export type YoutubeSettings = {
  configured: boolean
  api_key_configured: boolean
  api_key_hint?: string
}

export type ScheduledJob = {
  job_id: number
  job_name: string
  enabled: boolean
  timezone: string
  run_time: string
  digest_language: 'zh' | 'en'
  scope_type: 'all_enabled' | 'groups' | 'sources'
  group_ids: number[]
  source_ids: number[]
  window_mode: 'last_1' | 'last_3' | 'last_7' | 'all_time'
  max_videos_per_source?: number | null
  process_missing_videos: boolean
  retry_failed_once: boolean
  send_empty_digest: boolean
  telegram_enabled: boolean
  feishu_enabled: boolean
  email_enabled: boolean
  recent_runs?: DigestRun[]
  created_at?: string | null
  updated_at?: string | null
}

export type DeliverySettings = {
  telegram_enabled: boolean
  telegram_bot_token_configured: boolean
  telegram_bot_token_hint?: string
  telegram_chat_id: string
  telegram_parse_mode: string
  telegram_send_as_file_if_too_long: boolean
  feishu_enabled: boolean
  feishu_webhook_url_configured: boolean
  feishu_webhook_url_hint?: string
  feishu_secret_configured: boolean
  feishu_secret_hint?: string
  email_enabled: boolean
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_password_configured: boolean
  smtp_password_hint?: string
  smtp_use_tls: boolean
  smtp_use_ssl: boolean
  email_from: string
  email_to: string[]
  email_subject_template: string
  email_attach_markdown: boolean
}

export type DeliveryLog = {
  delivery_id: number
  summary_id?: number | null
  run_id?: number | null
  channel: string
  status: string
  target?: string | null
  scheduled_job_name?: string | null
  error_message?: string | null
  created_at?: string | null
}

export type DeliveryResult = {
  delivery_id?: number
  channel: string
  status: string
  target?: string | null
  error_message?: string | null
  created_at?: string | null
}

export type ModelProfile = {
  model_id: number
  provider: string
  model_name: string
  is_active: number
  source?: string | null
}

export type LLMProvider = {
  provider: string
  provider_type: string
  display_name?: string | null
  base_url?: string | null
  default_model?: string | null
  enabled: number
  notes?: string | null
  source?: string | null
  is_builtin?: boolean
  api_key_configured: boolean
}

export type DigestRun = {
  run_id: number
  status: string
  run_type?: string
  window_start?: string | null
  window_end?: string | null
  source_ids_json?: string | null
  summary_id?: number | null
  included_count: number
  failed_count: number
  skipped_count: number
  created_at?: string | null
  completed_at?: string | null
  error_message?: string | null
  scheduled_job_id?: number | null
  scheduled_job_name?: string | null
  deliveries?: DeliveryResult[]
  empty_digest_delivered?: boolean
  videos?: Array<Record<string, string | number | null>>
}

export type DigestVideo = {
  run_id?: number
  video_id: string
  source_id?: number | null
  status: string
  action?: string | null
  error_message?: string | null
  video_summary_id?: number | null
  summary_id?: number | null
  video_title?: string | null
  video_url?: string | null
  video_date?: string | null
  channel_name?: string | null
  source_name?: string | null
  display_name?: string | null
  source_type?: string | null
}
