from __future__ import annotations

import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import ChatAdminRequiredError, FloodWaitError
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import (
    Channel,
    ChannelParticipantsSearch,
    UserStatusLastMonth,
    UserStatusLastWeek,
    UserStatusOffline,
    UserStatusOnline,
    UserStatusRecently,
)

from backend.config import SCRAPE_DIR
from backend.telegram.utils import resolve_entity

LINK_PATTERN = re.compile(r"https?://t\.me/[A-Za-z0-9_+/-]+")


def _resolve_save_dir(save_path: str) -> Path:
    if save_path.strip():
        path = Path(save_path.strip())
        path.mkdir(parents=True, exist_ok=True)
        return path
    SCRAPE_DIR.mkdir(parents=True, exist_ok=True)
    return SCRAPE_DIR


def _save_csv(rows: list[dict], prefix: str, save_path: str = "") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.csv"
    path = _resolve_save_dir(save_path) / filename
    if not rows:
        path.write_text("", encoding="utf-8")
        return str(path)

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def _is_active_user(user, active_days: int) -> bool:
    if active_days <= 0:
        return True

    status = getattr(user, "status", None)
    if status is None:
        return True
    if isinstance(status, (UserStatusOnline, UserStatusRecently)):
        return True
    if isinstance(status, UserStatusLastWeek):
        return active_days >= 7
    if isinstance(status, UserStatusLastMonth):
        return active_days >= 30
    if isinstance(status, UserStatusOffline) and status.was_online:
        now = datetime.now(timezone.utc)
        was_online = status.was_online
        if was_online.tzinfo is None:
            was_online = was_online.replace(tzinfo=timezone.utc)
        delta_days = (now - was_online).days
        return delta_days <= active_days
    return False


def _user_to_row(user, group_link: str) -> dict:
    return {
        "user_id": user.id,
        "username": user.username or "",
        "phone": getattr(user, "phone", "") or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "group": group_link,
    }


def _filter_member(user, active_days: int, require_name: bool) -> bool:
    if user.bot:
        return False
    if require_name and not (user.first_name or user.last_name):
        return False
    return _is_active_user(user, active_days)


async def scrape_group_members(
    client: TelegramClient,
    group_link: str,
    active_days: int = 0,
    require_name: bool = False,
) -> list[dict]:
    entity = await resolve_entity(client, group_link)
    members: list[dict] = []
    offset = 0

    while True:
        result = await client(
            GetParticipantsRequest(
                channel=entity,
                filter=ChannelParticipantsSearch(""),
                offset=offset,
                limit=200,
                hash=0,
            )
        )
        if not result.users:
            break

        for user in result.users:
            if not _filter_member(user, active_days, require_name):
                continue
            members.append(_user_to_row(user, group_link))

        offset += len(result.users)
        if len(result.users) < 200:
            break

    return members


async def scrape_members_from_messages(
    client: TelegramClient,
    group_link: str,
    message_limit: int,
    active_days: int = 0,
    require_name: bool = False,
    on_log: Callable[[str, str], None] | None = None,
) -> list[dict]:
    entity = await resolve_entity(client, group_link)
    users_map: dict[int, dict] = {}
    limit = max(1, int(message_limit or 2000))
    scanned = 0
    if on_log:
        on_log("info", f"正在扫描最新 {limit} 条发言…")

    async for message in client.iter_messages(entity, limit=limit):
        scanned += 1
        sender = getattr(message, "sender", None)
        if sender is None:
            sender = await message.get_sender()
        if not sender or not hasattr(sender, "id"):
            continue
        if not _filter_member(sender, active_days, require_name):
            continue
        users_map[sender.id] = _user_to_row(sender, group_link)
        if on_log and scanned % 500 == 0:
            on_log("info", f"已扫描 {scanned}/{limit} 条，当前用户 {len(users_map)} 个")

    if on_log:
        on_log("info", f"最新 {scanned} 条发言中提取到 {len(users_map)} 个用户")
    return list(users_map.values())


async def search_groups_via_bot(
    client: TelegramClient,
    bot_username: str,
    keyword: str,
    min_members: int = 0,
    filter_channels: bool = True,
) -> list[dict]:
    bot = await client.get_entity(bot_username.lstrip("@"))
    await client.send_message(bot, keyword)
    await asyncio.sleep(4)

    links: list[str] = []
    async for message in client.iter_messages(bot, limit=10):
        if not message.text:
            continue
        found = LINK_PATTERN.findall(message.text)
        links.extend(found)

    unique = list(dict.fromkeys(links))
    results: list[dict] = []

    for link in unique:
        row = {"keyword": keyword, "link": link, "bot": bot_username, "members": 0}
        try:
            entity = await resolve_entity(client, link)
            if isinstance(entity, Channel):
                if filter_channels and entity.broadcast and not entity.megagroup:
                    continue
                members = getattr(entity, "participants_count", 0) or 0
                row["members"] = members
                if min_members > 0 and members < min_members:
                    continue
        except Exception:
            if min_members > 0:
                continue
        results.append(row)

    return results


async def run_scrape_members_loop(
    account_ids: list[str],
    group_links: list[str],
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    active_days: int = 0,
    require_name: bool = False,
    hidden_group_mode: bool = False,
    message_limit: int = 2000,
    save_path: str = "",
) -> str:
    all_members: list[dict] = []
    success = 0
    failed = 0
    message_limit = max(1, min(50000, int(message_limit or 2000)))

    for index, link in enumerate(group_links):
        if should_stop():
            break

        account_id = account_ids[index % len(account_ids)]
        try:
            client = await get_client(account_id)
            if hidden_group_mode:
                members = await scrape_members_from_messages(
                    client,
                    link,
                    message_limit,
                    active_days,
                    require_name,
                    on_log=lambda level, msg: on_log(level, f"[{account_id}] {msg}"),
                )
                mode = "发言用户"
            else:
                try:
                    members = await scrape_group_members(
                        client,
                        link,
                        active_days,
                        require_name,
                    )
                    mode = "成员"
                except ChatAdminRequiredError:
                    on_log(
                        "warn",
                        f"[{account_id}] 无法查看成员列表，改为提取最新 {max(1, int(message_limit or 2000))} 条发言用户: {link}",
                    )
                    members = await scrape_members_from_messages(
                        client,
                        link,
                        message_limit,
                        active_days,
                        require_name,
                        on_log=lambda level, msg: on_log(level, f"[{account_id}] {msg}"),
                    )
                    mode = "发言用户"
            all_members.extend(members)
            success += 1
            on_log(
                "success",
                f"[{account_id}] 采集完成 {link}，获取 {len(members)} 个{mode}",
            )
        except FloodWaitError as exc:
            failed += 1
            on_log("warn", f"[{account_id}] 频繁限制，等待 {exc.seconds}s")
            await asyncio.sleep(exc.seconds)
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 采集失败 {link}: {exc}")

        on_progress(index + 1, success, failed)

    output = _save_csv(all_members, "members", save_path)
    # 竞品风格：另存纯用户名列表
    usernames = [
        (row.get("username") or "").strip()
        for row in all_members
        if (row.get("username") or "").strip()
    ]
    unique_users: list[str] = []
    seen: set[str] = set()
    for name in usernames:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_users.append(name)
    user_txt = _resolve_save_dir(save_path) / "采集的群用户.txt"
    user_txt.write_text("\n".join(unique_users) + ("\n" if unique_users else ""), encoding="utf-8")
    on_log("info", f"结果已保存: {output} ；用户名列表: {user_txt}")
    return output


async def run_scrape_groups_loop(
    account_ids: list[str],
    keywords: list[str],
    bot_username: str,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    min_members: int = 0,
    filter_channels: bool = True,
    save_path: str = "",
    thread_count: int = 0,
) -> str:
    all_groups: list[dict] = []
    total = len(keywords)
    success = 0
    failed = 0
    lock = asyncio.Lock()
    workers = thread_count if thread_count > 0 else len(keywords)
    sem = asyncio.Semaphore(max(1, min(workers, len(keywords))))

    async def process_keyword(index: int, keyword: str) -> None:
        nonlocal success, failed
        if should_stop():
            return

        async with sem:
            account_id = account_ids[index % len(account_ids)]
            try:
                client = await get_client(account_id)
                groups = await search_groups_via_bot(
                    client,
                    bot_username,
                    keyword,
                    min_members,
                    filter_channels,
                )
                async with lock:
                    all_groups.extend(groups)
                    success += 1
                on_log(
                    "success",
                    f"[{account_id}] 关键词「{keyword}」找到 {len(groups)} 个群组",
                )
            except FloodWaitError as exc:
                async with lock:
                    failed += 1
                on_log("warn", f"[{account_id}] 频繁限制，等待 {exc.seconds}s")
                await asyncio.sleep(exc.seconds)
            except Exception as exc:
                async with lock:
                    failed += 1
                on_log("error", f"[{account_id}] 搜索失败「{keyword}」: {exc}")

            async with lock:
                on_progress(success + failed, success, failed)

    await asyncio.gather(
        *[process_keyword(i, keyword) for i, keyword in enumerate(keywords)]
    )

    output = _save_csv(all_groups, "groups", save_path)
    on_log("info", f"结果已保存: {output}")
    return output
