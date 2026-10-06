from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, Chat
from backend.config import SCRAPE_DIR
from backend.telegram.result_files import format_caihong_timestamp
from backend.telegram.utils import resolve_entity
# 兼容 https://t.me/... 与 t.me/+邀请码 / t.me/username
LINK_PATTERN = re.compile(r"(?:https?://)?t\.me/[A-Za-z0-9_+/-]+", re.I)
USERNAME_PATTERN = re.compile(r"@[A-Za-z0-9_]{4,}")
def _normalize_link(link: str) -> str:
    text = link.strip()
    if text.lower().startswith("http://") or text.lower().startswith("https://"):
        return text
    if text.lower().startswith("t.me/"):
        return text  # 竞品邀请链常保留无协议前缀
    return text
def _resolve_output_path(save_path: str) -> Path:
    if save_path.strip():
        path = Path(save_path.strip())
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        path.mkdir(parents=True, exist_ok=True)
        return path / "综合功能提取链接.txt"
    SCRAPE_DIR.mkdir(parents=True, exist_ok=True)
    return SCRAPE_DIR / "综合功能提取链接.txt"
async def extract_from_source(
    client: TelegramClient,
    source_link: str,
    message_limit: int,
    extract_links: bool,
    extract_usernames: bool,
) -> tuple[list[str], list[str]]:
    """按消息出现顺序收集，保留竞品风格的链接原样。"""
    entity = await resolve_entity(client, source_link)
    links: list[str] = []
    usernames: list[str] = []
    seen_links: set[str] = set()
    seen_users: set[str] = set()
    async for message in client.iter_messages(entity, limit=message_limit):
        text = message.text or ""
        if extract_links:
            for match in LINK_PATTERN.findall(text):
                norm = _normalize_link(match)
                key = norm.lower()
                if key in seen_links:
                    continue
                seen_links.add(key)
                links.append(norm)
        if extract_usernames:
            for match in USERNAME_PATTERN.findall(text):
                if match.lower() in seen_users:
                    continue
                seen_users.add(match.lower())
                usernames.append(match)
    return links, usernames
async def validate_group_link(
    client: TelegramClient,
    link: str,
    min_members: int = 0,
    max_members: int = 0,
    only_groups: bool = True,
) -> dict | None:
    """校验链接是否为有效群/频道，并按人数筛选。返回 None 表示不通过。"""
    try:
        entity = await resolve_entity(client, link)
    except Exception as exc:
        return {"link": link, "ok": False, "reason": str(exc)}
    title = getattr(entity, "title", "") or getattr(entity, "username", "") or link
    members = getattr(entity, "participants_count", 0) or 0
    is_channel = isinstance(entity, Channel) and not entity.megagroup
    is_group = isinstance(entity, Chat) or (isinstance(entity, Channel) and entity.megagroup)
    if only_groups and is_channel and not is_group:
        try:
            if isinstance(entity, Channel):
                full = await client(GetFullChannelRequest(entity))
                members = getattr(full.full_chat, "participants_count", members) or members
        except Exception:
            pass
        return {
            "link": link,
            "ok": False,
            "reason": "是频道而非群组",
            "title": title,
            "members": members,
            "type": "channel",
        }
    if isinstance(entity, Channel):
        try:
            full = await client(GetFullChannelRequest(entity))
            members = getattr(full.full_chat, "participants_count", members) or members
        except Exception:
            pass
    if members < min_members:
        return {
            "link": link,
            "ok": False,
            "reason": f"人数不足 ({members} < {min_members})",
            "title": title,
            "members": members,
        }
    if max_members > 0 and members > max_members:
        return {
            "link": link,
            "ok": False,
            "reason": f"人数超限 ({members} > {max_members})",
            "title": title,
            "members": members,
        }
    username = getattr(entity, "username", "") or ""
    return {
        "link": link,
        "ok": True,
        "title": title,
        "members": members,
        "username": username,
        "type": "group" if is_group else "channel",
    }
async def run_extract_links_loop(
    account_ids: list[str],
    source_links: list[str],
    message_limit: int,
    extract_links: bool,
    extract_usernames: bool,
    save_path: str,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    validate_links: bool = False,
    min_members: int = 0,
    max_members: int = 0,
    only_groups: bool = True,
) -> str:
    all_links: list[str] = []
    all_usernames: list[str] = []
    seen_links: set[str] = set()
    seen_users: set[str] = set()
    success = 0
    failed = 0
    first_source = source_links[0] if source_links else ""
    for index, source in enumerate(source_links):
        if should_stop():
            break
        account_id = account_ids[index % len(account_ids)]
        try:
            client = await get_client(account_id)
            links, usernames = await extract_from_source(
                client,
                source,
                message_limit,
                extract_links,
                extract_usernames,
            )
            for link in links:
                key = link.lower()
                if key not in seen_links:
                    seen_links.add(key)
                    all_links.append(link)
            for user in usernames:
                key = user.lower()
                if key not in seen_users:
                    seen_users.add(key)
                    all_usernames.append(user)
            success += 1
            on_log(
                "success",
                f"[{account_id}] {source} 提取 {len(links)} 链接, {len(usernames)} 用户名",
            )
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 提取失败 {source}: {exc}")
        on_progress(index + 1, success, failed)
    validated_ok: list[str] = []
    validated_fail: list[str] = []
    if validate_links and all_links and account_ids:
        account_id = account_ids[0]
        try:
            client = await get_client(account_id)
            on_log("info", f"开始筛选校验 {len(all_links)} 个链接...")
            for i, link in enumerate(all_links):
                if should_stop():
                    break
                result = await validate_group_link(
                    client, link, min_members, max_members, only_groups
                )
                if result and result.get("ok"):
                    validated_ok.append(link)
                    on_log(
                        "success",
                        f"通过: {result.get('title')} ({result.get('members', 0)}人) {link}",
                    )
                else:
                    reason = (result or {}).get("reason", "无效")
                    validated_fail.append(f"{link}\t# {reason}")
                    on_log("warn", f"剔除: {link} — {reason}")
                if (i + 1) % 10 == 0:
                    on_progress(i + 1, len(validated_ok), len(validated_fail))
        except Exception as exc:
            on_log("error", f"链接筛选失败: {exc}")
    output_path = _resolve_output_path(save_path)
    lines: list[str] = []
    # 竞品格式：首行 时间戳:源链接，其后混排链接与 @，无分节标题
    header_source = first_source.strip() or "extract"
    lines.append(f"{format_caihong_timestamp()}:{header_source}")
    if validate_links:
        lines.extend(validated_ok)
        if not validated_ok:
            lines.append("# 无通过链接")
    else:
        if extract_links:
            lines.extend(all_links)
        if extract_usernames:
            lines.extend(all_usernames)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    on_log("info", f"结果已保存: {output_path}")
    # 兼容旧调用方未使用的变量
    _ = datetime.now()
    return str(output_path)
