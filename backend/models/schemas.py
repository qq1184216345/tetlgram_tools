from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AccountStatus(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    CONNECTING = "connecting"
    ERROR = "error"


class AccountInfo(BaseModel):
    id: str
    phone: str = ""
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    status: AccountStatus = AccountStatus.OFFLINE
    proxy: str = ""
    session_file: str
    error: str = ""
    join_status: str = ""
    broadcast_status: str = ""
    broadcast_success_count: int = 0
    has_custom_ad: bool = False
    has_session_json: bool = False
    has_two_fa_hint: bool = False


class AccountCustomAdRequest(BaseModel):
    message: str = ""


class AccountProxyRequest(BaseModel):
    proxy: str = ""


class AssignProxiesRequest(BaseModel):
    account_ids: list[str] = Field(default_factory=list)


class ChatHistoryRequest(BaseModel):
    target: str
    limit: int = 50


class LoginStartRequest(BaseModel):
    phone: str
    api_id: Optional[int] = None
    api_hash: Optional[str] = None


class LoginVerifyRequest(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None


class QrLoginPasswordRequest(BaseModel):
    password: str


class QrLoginStatusResponse(BaseModel):
    login_id: str
    status: str
    qr_url: str = ""
    qr_image: str = ""
    error: str = ""
    account: Optional["AccountInfo"] = None


class ProxyTestRequest(BaseModel):
    proxy_state: bool | None = None
    use_system_proxy: bool | None = None
    proxy_type: str | None = None
    proxy_list: str | None = None


class AppConfig(BaseModel):
    api_id: int = 0
    api_hash: str = ""
    socks5_ip: str = ""
    socks5_port: int = 0
    proxy_state: bool = False
    proxy_type: str = "socks5"
    proxy_list: str = ""
    use_system_proxy: bool = False
    success_account_path: str = ""
    failed_account_path: str = ""
    ai_api_url: str = ""
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_verify_enabled: bool = False
    device_profile: str = "apple_desktop"


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.3"
    accounts: int = 0


class ApiResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[dict] = None


class LicenseStatusReport(BaseModel):
    token: str = ""
    email: str = ""
    expires_at: Optional[str] = None
    licensed: bool = False
    checked_at: str = ""


class TaskModule(str, Enum):
    ACCOUNTS = "accounts"
    BROADCAST = "broadcast"
    SCRAPE = "scrape"
    DM = "dm"
    INVITE = "invite"
    WARM = "warm"
    MONITOR = "monitor"
    FILTER = "filter"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class TaskType(str, Enum):
    CONNECT_ACCOUNTS = "connect_accounts"
    BROADCAST = "broadcast"
    JOIN_GROUP = "join_group"
    DM = "dm"
    SCRAPE_MEMBERS = "scrape_members"
    SCRAPE_GROUPS = "scrape_groups"
    INVITE = "invite"
    WARM_GROUP = "warm_group"
    MONITOR = "monitor"
    FILTER_GROUPS = "filter_groups"
    UPDATE_PROFILE = "update_profile"
    EXTRACT_LINKS = "extract_links"
    LEAVE_GROUPS = "leave_groups"
    CHANNEL_COMMENT = "channel_comment"
    CLONE_CHANNEL = "clone_channel"
    SCRAPE_PROFILES = "scrape_profiles"


class TaskLogEntry(BaseModel):
    time: str
    level: str = "info"
    message: str


class TaskProgress(BaseModel):
    current: int = 0
    total: int = 0
    success: int = 0
    failed: int = 0


class TaskFailedItem(BaseModel):
    target: str
    reason: str
    account_id: str = ""


class TaskInfo(BaseModel):
    id: str
    type: TaskType
    status: TaskStatus
    progress: TaskProgress = Field(default_factory=TaskProgress)
    logs: list[TaskLogEntry] = Field(default_factory=list)
    created_at: str = ""
    error: str = ""
    result_file: str = ""
    failed_items: list[TaskFailedItem] = Field(default_factory=list)
    account_ids: list[str] = Field(default_factory=list)
    resumable: bool = False


class BroadcastTaskRequest(BaseModel):
    account_ids: list[str]
    targets: list[str] = Field(default_factory=list)
    use_joined_groups: bool = False
    message: str
    parse_mode: Optional[str] = None
    interval_min: int = 30
    interval_max: int = 60
    auto_join: bool = False
    use_rich_tags: bool = False
    use_postbot: bool = False
    postbot_code: str = ""
    send_mode: str = "text"
    media_path: str = ""
    forward_channel: str = ""
    forward_message_id: int = 0
    forward_message_links: list[str] = Field(default_factory=list)
    forward_hide_source: bool = True
    multi_line_mode: bool = False
    random_prefix_len: int = 0
    random_suffix_len: int = 0
    thread_count: int = 1
    start_hour: int = 0
    end_hour: int = 24
    schedule_start_at: str = ""
    schedule_end_at: str = ""
    auto_spambot_unban: bool = False
    no_duplicate_join: bool = False
    random_order: bool = False
    round_rest_min: int = 0
    round_rest_max: int = 0
    exit_muted_groups: bool = False
    combined_send: bool = False
    contact_target: str = ""
    contact_first_name: str = ""
    contact_last_name: str = ""
    auto_delete_after_sec: int = 0
    remove_muted_accounts: bool = False
    guest_mode: bool = False


class ConnectAccountsRequest(BaseModel):
    account_ids: list[str]


class JoinGroupTaskRequest(BaseModel):
    account_ids: list[str]
    targets: list[str]
    interval_min: int = 60
    interval_max: int = 120
    start_hour: int = 0
    end_hour: int = 24
    schedule_start_at: str = ""
    schedule_end_at: str = ""
    no_duplicate_join: bool = True
    request_join: bool = False
    auto_pass_verify: bool = True
    thread_count: int = 1


class LeaveGroupsTaskRequest(BaseModel):
    account_ids: list[str]
    targets: list[str] = Field(default_factory=list)
    include_channels: bool = False


class MessageTemplateRequest(BaseModel):
    broadcast: str = ""
    dm: str = ""


class DmTaskRequest(BaseModel):
    account_ids: list[str]
    targets: list[str]
    message: str
    parse_mode: Optional[str] = None
    interval_min: int = 30
    interval_max: int = 60
    use_rich_tags: bool = False
    use_postbot: bool = False
    postbot_code: str = ""
    send_mode: str = "text"
    media_path: str = ""
    multi_line_mode: bool = False
    random_prefix_len: int = 0
    random_suffix_len: int = 0
    thread_count: int = 1
    start_hour: int = 0
    end_hour: int = 24
    schedule_start_at: str = ""
    schedule_end_at: str = ""
    auto_spambot_unban: bool = False
    target_type: str = "user"
    forward_channel: str = ""
    forward_message_id: int = 0
    forward_message_links: list[str] = Field(default_factory=list)
    forward_hide_source: bool = True
    contact_target: str = ""
    contact_first_name: str = ""
    contact_last_name: str = ""
    voice_call: bool = False
    save_result_files: bool = True
    result_with_timestamp: bool = True


class ScrapeMembersTaskRequest(BaseModel):
    account_ids: list[str]
    group_links: list[str]
    active_days: int = 0
    require_name: bool = False
    hidden_group_mode: bool = False
    message_limit: int = Field(default=2000, ge=1, le=50000)
    save_path: str = ""


class ScrapeGroupsTaskRequest(BaseModel):
    account_ids: list[str]
    keywords: list[str]
    bot_username: str = "soso"
    min_members: int = 0
    filter_channels: bool = True
    save_path: str = ""
    thread_count: int = 0


class InviteTaskRequest(BaseModel):
    account_ids: list[str]
    group_link: str
    user_targets: list[str]
    interval_min: int = 60
    interval_max: int = 120
    make_public: bool = False
    account_loop_count: int = 1
    stop_after_n: int = 0
    thread_count: int = 1
    save_result_files: bool = True
    result_with_timestamp: bool = True


class WarmGroupTaskRequest(BaseModel):
    account_ids: list[str]
    group_links: list[str] = Field(default_factory=list)
    group_link: str = ""
    messages: list[str]
    interval_min: int = 30
    interval_max: int = 90
    rounds: int = 1
    join_only: bool = False


class MonitorTaskRequest(BaseModel):
    account_ids: list[str]
    mode: str = "keyword"
    reply_message: str = ""
    parse_mode: Optional[str] = None
    forward_group_link: str = ""
    monitor_group_posts: bool = False
    keywords: list[str] = Field(default_factory=list)
    notify_group_link: str = ""
    dm_on_match: str = ""
    global_match: bool = False
    auto_spambot_unban: bool = False


class FilterGroupsTaskRequest(BaseModel):
    account_ids: list[str]
    title_keyword: str = ""
    min_members: int = 0
    max_members: int = 0
    require_sticker: bool = False
    require_forum: bool = False
    require_send_text: bool = False
    require_send_links: bool = False
    require_send_photos: bool = False
    require_send_videos: bool = False
    exclude_bot_admins: bool = False
    group_links: list[str] = Field(default_factory=list)
    mode: str = "caps"  # caps | ad_length
    ad_message_limit: int = 10
    max_ad_chars: int = 150
    interval_sec: float = 5


class ScrapeProfilesTaskRequest(BaseModel):
    account_ids: list[str]
    targets: list[str]
    interval_sec: float = 5


class ExportAccountGroupsRequest(BaseModel):
    account_ids: list[str]
    mode: str = "both"  # all | addlist | both


class KeepOnlineRequest(BaseModel):
    account_ids: list[str] = Field(default_factory=list)
    interval_sec: float = 60
    enable: bool = True


class ChannelCommentTaskRequest(BaseModel):
    account_ids: list[str]
    posts: list[dict] = Field(default_factory=list)
    comment: str = ""
    interval_min: int = 10
    interval_max: int = 30


class CloneChannelTaskRequest(BaseModel):
    account_ids: list[str]
    source: str
    title: str = ""
    about: str = ""
    message_limit: int = 50
    bind_to_profile: bool = True


class ExtractLinksTaskRequest(BaseModel):
    account_ids: list[str]
    source_links: list[str]
    message_limit: int = 1000
    thread_count: int = 1
    extract_links: bool = True
    extract_usernames: bool = True
    save_path: str = ""
    validate_links: bool = False
    min_members: int = 0
    max_members: int = 0
    only_groups: bool = True


class AccountStatusCheckRequest(BaseModel):
    account_ids: list[str] = Field(default_factory=list)


class PrivacyBatchRequest(BaseModel):
    account_ids: list[str]
    phone: str = "disallow_all"
    last_seen: str = "disallow_all"
    profile_photo: str = "allow_all"
    invite: str = "disallow_all"


class KickDevicesRequest(BaseModel):
    hashes: list[int] = Field(default_factory=list)


class VoiceCallRequest(BaseModel):
    account_id: str
    target: str


class InviteAdminsRequest(BaseModel):
    admin_account_id: str
    group_link: str
    account_ids: list[str]
    promote: bool = True


class ProfileUpdateTaskRequest(BaseModel):
    account_ids: list[str]
    use_random_config: bool = True
    update_first_name: bool = False
    update_last_name: bool = False
    update_about: bool = False
    update_username: bool = False
    update_avatar: bool = False
    update_password: bool = False
    first_name: str = ""
    last_name: str = ""
    about: str = ""
    username: str = ""
    old_password: str = ""
    new_password: str = ""
    interval_min: int = 5
    interval_max: int = 15
    remove_2fa: bool = False


class TdataConvertRequest(BaseModel):
    tdata_path: str
    session_name: str = ""


class ImportSessionPathsRequest(BaseModel):
    paths: list[str] = Field(default_factory=list)
