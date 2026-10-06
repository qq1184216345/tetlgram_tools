import { API_BASE } from "../config/ports";

export { API_BASE };

export interface ApiResponse {
  success: boolean;
  message: string;
  data?: Record<string, unknown>;
}

export interface AccountInfo {
  id: string;
  phone: string;
  username: string;
  first_name: string;
  last_name: string;
  status: "offline" | "online" | "connecting" | "error";
  proxy: string;
  session_file: string;
  error: string;
  join_status: string;
  broadcast_status: string;
  broadcast_success_count: number;
  has_custom_ad: boolean;
  has_session_json: boolean;
  has_two_fa_hint: boolean;
}

export interface AppConfig {
  api_id: number;
  api_hash: string;
  socks5_ip: string;
  socks5_port: number;
  proxy_state: boolean;
  proxy_type: string;
  proxy_list: string;
  use_system_proxy: boolean;
  success_account_path: string;
  failed_account_path: string;
  ai_api_url: string;
  ai_api_key: string;
  ai_model: string;
  ai_verify_enabled: boolean;
  device_profile?: string;
}

export interface DeviceProfile {
  id: string;
  label: string;
  device_model: string;
  system_version: string;
  app_version: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  accounts: number;
}

export interface TaskProgress {
  current: number;
  total: number;
  success: number;
  failed: number;
}

export interface TaskLogEntry {
  time: string;
  level: string;
  message: string;
}

export interface TaskFailedItem {
  target: string;
  reason: string;
  account_id?: string;
}

export interface TaskInfo {
  id: string;
  type: "connect_accounts" | "broadcast" | "join_group" | "dm" | "scrape_members" | "scrape_groups" | "invite" | "warm_group" | "monitor" | "filter_groups" | "update_profile" | "extract_links" | "leave_groups" | "channel_comment" | "clone_channel" | "scrape_profiles";
  status: "pending" | "running" | "paused" | "stopping" | "stopped" | "completed" | "error";
  progress: TaskProgress;
  logs: TaskLogEntry[];
  created_at: string;
  error: string;
  result_file: string;
  failed_items?: TaskFailedItem[];
  account_ids?: string[];
  resumable?: boolean;
}

export interface BroadcastTaskRequest {
  account_ids: string[];
  targets: string[];
  use_joined_groups?: boolean;
  message: string;
  parse_mode?: string | null;
  interval_min: number;
  interval_max: number;
  auto_join: boolean;
  use_rich_tags: boolean;
  use_postbot: boolean;
  send_mode: string;
  media_path: string;
  forward_channel: string;
  forward_message_id: number;
  forward_message_links: string[];
  forward_hide_source: boolean;
  multi_line_mode: boolean;
  random_prefix_len: number;
  random_suffix_len: number;
  thread_count: number;
  start_hour: number;
  end_hour: number;
  schedule_start_at?: string;
  schedule_end_at?: string;
  auto_spambot_unban: boolean;
  postbot_code: string;
  no_duplicate_join: boolean;
  random_order: boolean;
  round_rest_min: number;
  round_rest_max: number;
  exit_muted_groups: boolean;
  combined_send: boolean;
  contact_target: string;
  contact_first_name: string;
  contact_last_name: string;
  auto_delete_after_sec: number;
  remove_muted_accounts: boolean;
  guest_mode: boolean;
}

export interface JoinGroupTaskRequest {
  account_ids: string[];
  targets: string[];
  interval_min: number;
  interval_max: number;
  start_hour: number;
  end_hour: number;
  schedule_start_at?: string;
  schedule_end_at?: string;
  no_duplicate_join: boolean;
  request_join: boolean;
  auto_pass_verify: boolean;
  thread_count: number;
}

export interface LeaveGroupsTaskRequest {
  account_ids: string[];
  targets?: string[];
  include_channels?: boolean;
}

export interface MessageTemplateRequest {
  broadcast: string;
  dm: string;
}

export interface ChatHistoryMessage {
  id: number;
  date: string;
  sender: string;
  text: string;
  out: boolean;
}

export interface DmTaskRequest {
  account_ids: string[];
  targets: string[];
  message: string;
  parse_mode?: string | null;
  interval_min: number;
  interval_max: number;
  use_rich_tags: boolean;
  use_postbot: boolean;
  send_mode: string;
  media_path: string;
  multi_line_mode: boolean;
  random_prefix_len: number;
  random_suffix_len: number;
  thread_count: number;
  start_hour: number;
  end_hour: number;
  schedule_start_at?: string;
  schedule_end_at?: string;
  auto_spambot_unban: boolean;
  postbot_code: string;
  target_type: string;
  forward_channel: string;
  forward_message_id: number;
  forward_message_links: string[];
  forward_hide_source: boolean;
  contact_target: string;
  contact_first_name: string;
  contact_last_name: string;
  voice_call?: boolean;
  save_result_files?: boolean;
  result_with_timestamp?: boolean;
}

export interface ProfileUpdateTaskRequest {
  account_ids: string[];
  use_random_config: boolean;
  update_first_name: boolean;
  update_last_name: boolean;
  update_about: boolean;
  update_username: boolean;
  update_avatar: boolean;
  update_password: boolean;
  first_name: string;
  last_name: string;
  about: string;
  username: string;
  old_password: string;
  new_password: string;
  interval_min: number;
  interval_max: number;
  remove_2fa?: boolean;
}

export interface QrLoginStatus {
  login_id: string;
  status: "waiting" | "need_password" | "success" | "expired" | "error" | "cancelled";
  qr_url: string;
  qr_image?: string;
  error: string;
  account?: AccountInfo;
}

export interface ScrapeMembersTaskRequest {
  account_ids: string[];
  group_links: string[];
  active_days: number;
  require_name: boolean;
  hidden_group_mode: boolean;
  message_limit: number;
  save_path: string;
}

export interface ScrapeGroupsTaskRequest {
  account_ids: string[];
  keywords: string[];
  bot_username: string;
  min_members: number;
  filter_channels: boolean;
  save_path: string;
  thread_count: number;
}

export interface ApiPreset {
  id: string;
  label: string;
  api_id: number;
  api_hash: string;
}

export interface InviteTaskRequest {
  account_ids: string[];
  group_link: string;
  user_targets: string[];
  interval_min: number;
  interval_max: number;
  make_public: boolean;
  account_loop_count: number;
  stop_after_n: number;
  thread_count: number;
  save_result_files?: boolean;
  result_with_timestamp?: boolean;
}

export interface WarmGroupTaskRequest {
  account_ids: string[];
  group_links: string[];
  group_link?: string;
  messages: string[];
  interval_min: number;
  interval_max: number;
  rounds: number;
  join_only: boolean;
}

export interface MonitorTaskRequest {
  account_ids: string[];
  mode: "dm_forward" | "keyword";
  reply_message: string;
  parse_mode?: string | null;
  forward_group_link: string;
  monitor_group_posts: boolean;
  keywords: string[];
  notify_group_link: string;
  dm_on_match: string;
  global_match: boolean;
  auto_spambot_unban: boolean;
}

export interface ExtractLinksTaskRequest {
  account_ids: string[];
  source_links: string[];
  message_limit: number;
  thread_count: number;
  extract_links: boolean;
  extract_usernames: boolean;
  save_path: string;
  validate_links?: boolean;
  min_members?: number;
  max_members?: number;
  only_groups?: boolean;
}

export interface FilterGroupsTaskRequest {
  account_ids: string[];
  title_keyword: string;
  min_members: number;
  max_members: number;
  require_sticker?: boolean;
  require_forum?: boolean;
  require_send_text?: boolean;
  require_send_links?: boolean;
  require_send_photos?: boolean;
  require_send_videos?: boolean;
  exclude_bot_admins?: boolean;
  group_links?: string[];
  mode?: "caps" | "ad_length";
  ad_message_limit?: number;
  max_ad_chars?: number;
  interval_sec?: number;
}

export interface ScrapeProfilesTaskRequest {
  account_ids: string[];
  targets: string[];
  interval_sec?: number;
}

export interface ChannelCommentTaskRequest {
  account_ids: string[];
  posts: Array<{ channel: string; message_id: number; comment?: string }>;
  comment: string;
  interval_min: number;
  interval_max: number;
}

export interface CloneChannelTaskRequest {
  account_ids: string[];
  source: string;
  title: string;
  about: string;
  message_limit: number;
  bind_to_profile: boolean;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
      ...options,
    });
  } catch {
    throw new Error("无法连接后端，请确认服务已启动（改过导入逻辑后需要重启后端）");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = body.detail;
    let message = "请求失败";
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map((item: { msg?: string }) => item.msg ?? String(item)).join("; ");
    } else if (!detail && response.status >= 500) {
      message = "后端导入失败，请查看后端窗口日志";
    }
    throw new Error(message);
  }

  return response.json();
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  listAccounts: () => request<AccountInfo[]>("/api/accounts"),
  connectAccount: (id: string) =>
    request<AccountInfo>(`/api/accounts/${id}/connect`, { method: "POST" }),
  disconnectAccount: (id: string) =>
    request(`/api/accounts/${id}/disconnect`, { method: "POST" }),
  deleteAccount: (id: string) =>
    request(`/api/accounts/${id}`, { method: "DELETE" }),
  checkAccountStatus: (id: string) =>
    request<ApiResponse>(`/api/accounts/${id}/check-status`, { method: "POST" }),
  checkAccountsStatus: (account_ids: string[]) =>
    request<ApiResponse>("/api/accounts/check-status", {
      method: "POST",
      body: JSON.stringify({ account_ids }),
    }),
  listAccountDevices: (id: string) =>
    request<ApiResponse>(`/api/accounts/${id}/devices`),
  kickAccountDevices: (id: string, hashes?: number[]) =>
    request<ApiResponse>(`/api/accounts/${id}/kick-devices`, {
      method: "POST",
      body: JSON.stringify({ hashes: hashes ?? [] }),
    }),
  privacyBatch: (payload: {
    account_ids: string[];
    phone?: string;
    last_seen?: string;
    profile_photo?: string;
    invite?: string;
  }) =>
    request<ApiResponse>("/api/accounts/privacy-batch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  voiceCall: (account_id: string, target: string) =>
    request<ApiResponse>("/api/accounts/voice-call", {
      method: "POST",
      body: JSON.stringify({ account_id, target }),
    }),
  setAccountProxy: (id: string, proxy: string) =>
    request<ApiResponse>(`/api/accounts/${id}/proxy`, {
      method: "PUT",
      body: JSON.stringify({ proxy }),
    }),
  assignAccountProxies: (account_ids: string[]) =>
    request<ApiResponse>("/api/accounts/assign-proxies", {
      method: "POST",
      body: JSON.stringify({ account_ids }),
    }),
  getAccountCustomAd: (id: string) =>
    request<{ message: string }>(`/api/accounts/${id}/custom-ad`),
  setAccountCustomAd: (id: string, message: string) =>
    request<ApiResponse>(`/api/accounts/${id}/custom-ad`, {
      method: "PUT",
      body: JSON.stringify({ message }),
    }),
  getChatHistory: (accountId: string, target: string, limit = 50) =>
    request<ChatHistoryMessage[]>(`/api/accounts/${accountId}/chat-history`, {
      method: "POST",
      body: JSON.stringify({ target, limit }),
    }),
  getMessageTemplates: () => request<MessageTemplateRequest>("/api/message-templates"),
  saveMessageTemplates: (templates: MessageTemplateRequest) =>
    request<ApiResponse>("/api/message-templates", {
      method: "PUT",
      body: JSON.stringify(templates),
    }),
  startLogin: (phone: string) =>
    request("/api/accounts/login/start", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),
  verifyLogin: (phone: string, code: string, password?: string) =>
    request<AccountInfo>("/api/accounts/login/verify", {
      method: "POST",
      body: JSON.stringify({ phone, code, password: password || undefined }),
    }),
  startQrLogin: () =>
    request<ApiResponse>("/api/accounts/login/qr/start", { method: "POST" }),
  getQrLoginStatus: (loginId: string) =>
    request<QrLoginStatus>(`/api/accounts/login/qr/${loginId}/status`),
  refreshQrLogin: (loginId: string) =>
    request<ApiResponse>(`/api/accounts/login/qr/${loginId}/refresh`, { method: "POST" }),
  completeQrLogin: (loginId: string, password: string) =>
    request<AccountInfo>(`/api/accounts/login/qr/${loginId}/password`, {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  cancelQrLogin: (loginId: string) =>
    request(`/api/accounts/login/qr/${loginId}`, { method: "DELETE" }),
  importSessions: async (files: FileList) => {
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/api/accounts/import-sessions`, {
        method: "POST",
        body: form,
      });
    } catch {
      throw new Error("无法连接后端，请确认服务已启动（改过导入逻辑后需要重启后端）");
    }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail ?? "导入失败");
    }
    return response.json();
  },
  importSessionPaths: (paths: string[]) =>
    request<ApiResponse>("/api/accounts/import-session-paths", {
      method: "POST",
      body: JSON.stringify({ paths }),
    }),
  getProfileConfig: () =>
    request<Record<string, { exists?: boolean; count: number }>>("/api/profile-config"),
  convertTdata: (tdata_path: string, session_name?: string) =>
    request<ApiResponse>("/api/accounts/convert-tdata", {
      method: "POST",
      body: JSON.stringify({ tdata_path: tdata_path || "", session_name: session_name || "" }),
    }),
  getConfig: () => request<AppConfig>("/api/config"),
  getAppInfo: () =>
    request<{
      version: string;
      data_dir: string;
      project_root: string;
      backend_host: string;
      backend_port: number;
      suggested_data_dir: string;
      update_manifest_url: string;
    }>("/api/app-info"),
  getApiPresets: () => request<ApiPreset[]>("/api/config/api-presets"),
  getDeviceProfiles: () => request<DeviceProfile[]>("/api/config/device-profiles"),
  detectSystemProxy: () => request<ApiResponse>("/api/config/detect-proxy"),
  testProxy: (config?: {
    proxy_state?: boolean;
    use_system_proxy?: boolean;
    proxy_type?: string;
    proxy_list?: string;
  }) =>
    request<ApiResponse>("/api/proxy/test", {
      method: "POST",
      body: JSON.stringify(config ?? {}),
    }),
  probeProxies: (proxy_type: string, proxy_list: string) =>
    request<ApiResponse>("/api/proxy/probe", {
      method: "POST",
      body: JSON.stringify({ proxy_type, proxy_list }),
    }),
  saveConfig: (config: AppConfig) =>
    request("/api/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),
  listTasks: () => request<TaskInfo[]>("/api/tasks"),
  getTask: (id: string) => request<TaskInfo>(`/api/tasks/${id}`),
  startConnectAccounts: (accountIds: string[]) =>
    request<TaskInfo>("/api/accounts/connect-batch", {
      method: "POST",
      body: JSON.stringify({ account_ids: accountIds }),
    }),
  startBroadcast: (payload: BroadcastTaskRequest) =>
    request<TaskInfo>("/api/tasks/broadcast", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startJoinGroup: (payload: JoinGroupTaskRequest) =>
    request<TaskInfo>("/api/tasks/join-group", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startDm: (payload: DmTaskRequest) =>
    request<TaskInfo>("/api/tasks/dm", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startScrapeMembers: (payload: ScrapeMembersTaskRequest) =>
    request<TaskInfo>("/api/tasks/scrape-members", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startScrapeGroups: (payload: ScrapeGroupsTaskRequest) =>
    request<TaskInfo>("/api/tasks/scrape-groups", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startInvite: (payload: InviteTaskRequest) =>
    request<TaskInfo>("/api/tasks/invite", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  setInviteAdmins: (payload: {
    admin_account_id: string;
    group_link: string;
    account_ids: string[];
    promote: boolean;
  }) =>
    request<{ success: boolean; message: string; data?: { results: Array<{ account_id: string; ok: boolean; message: string }> } }>(
      "/api/invite/set-admins",
      { method: "POST", body: JSON.stringify(payload) },
    ),
  startWarmGroup: (payload: WarmGroupTaskRequest) =>
    request<TaskInfo>("/api/tasks/warm-group", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startMonitor: (payload: MonitorTaskRequest) =>
    request<TaskInfo>("/api/tasks/monitor", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startExtractLinks: (payload: ExtractLinksTaskRequest) =>
    request<TaskInfo>("/api/tasks/extract-links", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startFilterGroups: (payload: FilterGroupsTaskRequest) =>
    request<TaskInfo>("/api/tasks/filter-groups", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startScrapeProfiles: (payload: ScrapeProfilesTaskRequest) =>
    request<TaskInfo>("/api/tasks/scrape-profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  exportAccountGroups: (payload: { account_ids: string[]; mode?: "all" | "addlist" | "both" }) =>
    request<ApiResponse>("/api/accounts/export-groups", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getKeepOnline: () => request<{ accounts: string[] }>("/api/accounts/keep-online"),
  setKeepOnline: (payload: { account_ids: string[]; enable: boolean; interval_sec?: number }) =>
    request<ApiResponse>("/api/accounts/keep-online", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startProfileUpdate: (payload: ProfileUpdateTaskRequest) =>
    request<TaskInfo>("/api/tasks/update-profile", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startLeaveGroups: (payload: LeaveGroupsTaskRequest) =>
    request<TaskInfo>("/api/tasks/leave-groups", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startChannelComment: (payload: ChannelCommentTaskRequest) =>
    request<TaskInfo>("/api/tasks/channel-comment", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startCloneChannel: (payload: CloneChannelTaskRequest) =>
    request<TaskInfo>("/api/tasks/clone-channel", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  stopTask: (id: string) =>
    request<TaskInfo>(`/api/tasks/${id}/stop`, { method: "POST" }),
  pauseTask: (id: string) =>
    request<TaskInfo>(`/api/tasks/${id}/pause`, { method: "POST" }),
  resumeTask: (id: string) =>
    request<TaskInfo>(`/api/tasks/${id}/resume`, { method: "POST" }),
  exportTaskLog: (id: string) =>
    request<ApiResponse>(`/api/tasks/${id}/export`, { method: "POST" }),
  reportLicenseStatus: (payload: {
    token: string;
    email: string;
    expires_at: string | null;
    licensed: boolean;
    checked_at: string;
  }) =>
    request<ApiResponse>("/api/license/report", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getLicenseStatus: () => request<ApiResponse>("/api/license/status"),
};
