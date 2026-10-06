export type PageId =
  | "accounts"
  | "broadcast"
  | "scrape"
  | "dm"
  | "invite"
  | "warm"
  | "monitor"
  | "extract"
  | "filter"
  | "settings";

export interface NavItem {
  id: PageId;
  label: string;
  icon: string;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    id: "accounts",
    label: "账号中心",
    icon: "👤",
    description: "导入 session、手动登录、批量修改资料",
  },
  {
    id: "broadcast",
    label: "群发 / 加群",
    icon: "📢",
    description: "批量群发、自动加群、转发频道消息",
  },
  {
    id: "scrape",
    label: "用户 / 群采集",
    icon: "🔍",
    description: "采集群成员、关键词搜索公开群",
  },
  {
    id: "dm",
    label: "私信",
    icon: "✉️",
    description: "按手机号或用户名批量私信",
  },
  {
    id: "invite",
    label: "群拉人",
    icon: "👥",
    description: "批量邀请用户入群",
  },
  {
    id: "warm",
    label: "炒群",
    icon: "🔥",
    description: "多账号自动互动提高群活跃度",
  },
  {
    id: "monitor",
    label: "监控 / 自动回复",
    icon: "👁️",
    description: "私信转发、关键词监控双模式",
  },
  {
    id: "extract",
    label: "综合功能",
    icon: "🔗",
        description: "提取链接、评论频道帖子、克隆频道绑定主页",
  },
  {
    id: "filter",
    label: "过滤筛群",
    icon: "🎯",
    description: "按条件筛选目标群组",
  },
  {
    id: "settings",
    label: "设置",
    icon: "⚙️",
    description: "API、代理与全局配置",
  },
];
