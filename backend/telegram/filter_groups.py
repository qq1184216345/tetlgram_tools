from __future__ import annotations
import asyncio
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantsRequest
from telethon.tl.types import Channel, ChannelParticipantsAdmins, Chat, User
from backend.config import SCRAPE_DIR
from backend.telegram.utils import resolve_entity
LINK_ONLY = re.compile(r"https?://t\.me/[A-Za-z0-9_+/-]+", re.I)
def _save_csv(rows: list[dict], prefix: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.csv"
    path = SCRAPE_DIR / filename
    if not rows:
        path.write_text("", encoding="utf-8")
        return str(path)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)
def _write_link_list(filename: str, links: list[str]) -> Path:
    SCRAPE_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRAPE_DIR / filename
    unique: list[str] = []
    seen: set[str] = set()
    for link in links:
        text = (link or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    path.write_text("\n".join(unique) + ("\n" if unique else ""), encoding="utf-8")
    return path
def _public_link(entity, fallback: str = "") -> str:
    username = getattr(entity, "username", "") or ""
    if username:
        return f"https://t.me/{username}"
    return fallback.strip()
def _rights_allow(banned, field: str) -> bool:
    """ChatBannedRights: True means the action is banned."""
    if banned is None:
        return True
    return not bool(getattr(banned, field, False))
async def _probe_group_caps(client: TelegramClient, entity) -> dict:
    """探测人数、发送权限、是否论坛、是否有机器人管理。"""
    is_forum = bool(getattr(entity, "forum", False))
    default_banned = getattr(entity, "default_banned_rights", None)
    banned = default_banned
    members = getattr(entity, "participants_count", 0) or 0
    if isinstance(entity, Channel):
        try:
            full = await client(GetFullChannelRequest(entity))
            members = getattr(full.full_chat, "participants_count", members) or members
            banned = getattr(full.full_chat, "banned_rights", None) or default_banned
        except Exception:
            pass
    can_send_messages = _rights_allow(banned, "send_messages")
    can_send_media = _rights_allow(banned, "send_media")
    can_send_photos = _rights_allow(banned, "send_photos") and can_send_media
    can_send_videos = _rights_allow(banned, "send_videos") and can_send_media
    can_embed_links = _rights_allow(banned, "embed_links") and can_send_messages
    can_send_stickers = _rights_allow(banned, "send_stickers")
    has_bot_admin = False
    if isinstance(entity, Channel):
        try:
            result = await client(
                GetParticipantsRequest(
                    channel=entity,
                    filter=ChannelParticipantsAdmins(),
                    offset=0,
                    limit=100,
                    hash=0,
                )
            )
            has_bot_admin = any(
                isinstance(u, User) and bool(getattr(u, "bot", False)) for u in result.users
            )
        except Exception:
            pass
    return {
        "is_forum": is_forum,
        "can_send_messages": can_send_messages,
        "can_send_media": can_send_media,
        "can_send_photos": can_send_photos,
        "can_send_videos": can_send_videos,
        "can_embed_links": can_embed_links,
        "can_send_stickers": can_send_stickers,
        "has_bot_admin": has_bot_admin,
        "members": members,
    }
def _match_caps(
    caps: dict,
    *,
    require_sticker: bool,
    require_forum: bool,
    require_send_text: bool,
    require_send_links: bool,
    require_send_photos: bool,
    require_send_videos: bool,
    exclude_bot_admins: bool,
) -> bool:
    if require_sticker and not caps["can_send_stickers"]:
        return False
    if require_forum and not caps["is_forum"]:
        return False
    if require_send_text and not caps["can_send_messages"]:
        return False
    if require_send_links and not caps["can_embed_links"]:
        return False
    if require_send_photos and not caps["can_send_photos"]:
        return False
    if require_send_videos and not caps["can_send_videos"]:
        return False
    if exclude_bot_admins and caps["has_bot_admin"]:
        return False
    return True
async def _classify_ad_length(
    client: TelegramClient,
    entity,
    *,
    message_limit: int,
    max_ad_chars: int,
) -> tuple[str, int, int]:
    """返回 (short|long|empty, scanned, over_limit_count)。
    竞品逻辑：连续 N 条消息字数都 < 阈值 → 短广告群，否则长广告群。
    """
    limit = max(1, message_limit)
    threshold = max(1, max_ad_chars)
    scanned = 0
    over = 0
    async for message in client.iter_messages(entity, limit=limit):
        text = (message.message or message.text or "").strip()
        if not text:
            continue
        scanned += 1
        if len(text) >= threshold:
            over += 1
    if scanned == 0:
        return "empty", 0, 0
    if over == 0:
        return "short", scanned, over
    return "long", scanned, over
async def run_filter_groups_loop(
    account_ids: list[str],
    title_keyword: str,
    min_members: int,
    max_members: int,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    require_sticker: bool = False,
    require_forum: bool = False,
    require_send_text: bool = False,
    require_send_links: bool = False,
    require_send_photos: bool = False,
    require_send_videos: bool = False,
    exclude_bot_admins: bool = False,
    group_links: list[str] | None = None,
    mode: str = "caps",
    ad_message_limit: int = 10,
    max_ad_chars: int = 150,
    interval_sec: float = 0,
) -> str:
    account_id = account_ids[0]
    client = await get_client(account_id)
    results: list[dict] = []
    checked = 0
    links = [x.strip() for x in (group_links or []) if x.strip()]
    short_links: list[str] = []
    long_links: list[str] = []
    matched_links: list[str] = []
    is_ad_mode = (mode or "caps").strip().lower() in {"ad", "ad_length", "ads"}
    async def consider_caps(entity, title: str, source_link: str = "") -> None:
        nonlocal checked
        checked += 1
        caps = await _probe_group_caps(client, entity)
        members = caps["members"]
        if title_keyword and title_keyword.lower() not in title.lower():
            on_log("warn", f"群组链接不符合要求!! {title}")
            return
        if members < min_members or (max_members > 0 and members > max_members):
            on_log("warn", f"群组链接不符合要求!! {title} ({members}人)")
            return
        if not _match_caps(
            caps,
            require_sticker=require_sticker,
            require_forum=require_forum,
            require_send_text=require_send_text,
            require_send_links=require_send_links,
            require_send_photos=require_send_photos,
            require_send_videos=require_send_videos,
            exclude_bot_admins=exclude_bot_admins,
        ):
            on_log("warn", f"群组链接不符合要求!! {title}")
            return
        link = _public_link(entity, source_link)
        results.append(
            {
                "title": title,
                "members": members,
                "username": getattr(entity, "username", "") or "",
                "link": link,
                "id": entity.id,
                "can_send_messages": caps["can_send_messages"],
                "can_embed_links": caps["can_embed_links"],
                "can_send_photos": caps["can_send_photos"],
                "can_send_videos": caps["can_send_videos"],
                "can_send_stickers": caps["can_send_stickers"],
                "has_bot_admin": caps["has_bot_admin"],
                "is_forum_topic": caps["is_forum"],
            }
        )
        if link:
            matched_links.append(link)
        on_log(
            "success",
            f"符合筛选要求!! {title} ({members} 人) "
            f"文字={'是' if caps['can_send_messages'] else '否'} "
            f"链接={'是' if caps['can_embed_links'] else '否'} "
            f"图={'是' if caps['can_send_photos'] else '否'} "
            f"视频={'是' if caps['can_send_videos'] else '否'} "
            f"贴纸={'是' if caps['can_send_stickers'] else '否'} "
            f"Bot管={'是' if caps['has_bot_admin'] else '否'} "
            f"话题={'是' if caps['is_forum'] else '否'}",
        )
    async def consider_ad(entity, title: str, source_link: str = "") -> None:
        nonlocal checked
        checked += 1
        link = _public_link(entity, source_link) or source_link
        kind, scanned, over = await _classify_ad_length(
            client,
            entity,
            message_limit=ad_message_limit,
            max_ad_chars=max_ad_chars,
        )
        if kind == "empty":
            on_log("warn", f"{title} 无可读消息，跳过")
            return
        if kind == "short":
            short_links.append(link)
            on_log(
                "success",
                f"短广告群: {title} — 连续{scanned}条消息均 < {max_ad_chars} 字",
            )
        else:
            long_links.append(link)
            on_log(
                "info",
                f"长广告群: {title} — 连续{scanned}条中有 {over} 条 ≥ {max_ad_chars} 字",
            )
        results.append(
            {
                "title": title,
                "link": link,
                "ad_type": kind,
                "scanned": scanned,
                "over_limit": over,
                "max_ad_chars": max_ad_chars,
            }
        )
    consider = consider_ad if is_ad_mode else consider_caps
    if links:
        on_log(
            "info",
            f"[{account_id}] 开始{'长短广告' if is_ad_mode else '权限人数'}筛选 {len(links)} 个群...",
        )
        for i, link in enumerate(links, start=1):
            if should_stop():
                break
            try:
                entity = await resolve_entity(client, link)
                if isinstance(entity, Channel) and getattr(entity, "broadcast", False) and not entity.megagroup:
                    on_log("warn", f"跳过频道: {link}")
                    continue
                if not isinstance(entity, (Channel, Chat)):
                    continue
                title = getattr(entity, "title", None) or link
                on_log("info", f"筛至第 ({i}) 个群... {title}")
                await consider(entity, title, link)
            except Exception as exc:
                on_log("warn", f"跳过 {link}: {exc}")
            on_progress(checked, len(results), 0)
            if interval_sec > 0:
                await asyncio.sleep(interval_sec)
    else:
        on_log("info", f"[{account_id}] 开始扫描已加入的群组...")
        async for dialog in client.iter_dialogs():
            if should_stop():
                break
            entity = dialog.entity
            if not isinstance(entity, (Channel, Chat)):
                continue
            if isinstance(entity, Channel) and getattr(entity, "broadcast", False) and not entity.megagroup:
                continue
            await consider(entity, dialog.title or "")
            on_progress(checked, len(results), 0)
            if interval_sec > 0:
                await asyncio.sleep(interval_sec)
    on_progress(checked, len(results), 0)
    if is_ad_mode:
        short_path = _write_link_list("筛群短广告群.txt", short_links)
        long_path = _write_link_list("筛群长广告群.txt", long_links)
        csv_path = _save_csv(results, "filtered_ad_groups")
        on_log(
            "info",
            f"筛选完成：短广告 {len(short_links)} / 长广告 {len(long_links)}；"
            f"已保存 {short_path.name}、{long_path.name}、{Path(csv_path).name}",
        )
        return str(short_path)
    else:
        txt_path = _write_link_list("符合要求群链接.txt", matched_links)
        csv_path = _save_csv(results, "filtered_groups")
        on_log(
            "info",
            f"筛选完成，共 {len(results)} 个群组，已保存: {txt_path} ；明细 CSV: {csv_path}",
        )
        return str(txt_path)
