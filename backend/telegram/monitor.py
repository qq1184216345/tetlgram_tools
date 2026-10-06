from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from telethon import TelegramClient, events

from backend.telegram.spambot import try_spambot_unban

from backend.config import LOG_DIR
from backend.telegram.utils import resolve_entity

LINK_PATTERN = re.compile(r"https?://t\.me/[A-Za-z0-9_+/-]+")
USERNAME_PATTERN = re.compile(r"@[A-Za-z0-9_]{4,}")


def _match_keyword(text: str, keyword: str, global_match: bool) -> bool:
    lowered = text.lower()
    kw = keyword.lower().strip()
    if not kw:
        return False
    if global_match:
        return lowered == kw
    return kw in lowered


def _append_monitor_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"监控_{datetime.now().strftime('%Y%m%d')}.txt"
    path = LOG_DIR / filename
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


async def run_monitor_loop(
    account_ids: list[str],
    mode: str,
    reply_message: str,
    parse_mode: str | None,
    forward_group_link: str,
    monitor_group_posts: bool,
    keywords: list[str],
    notify_group_link: str,
    dm_on_match: str,
    global_match: bool,
    auto_spambot_unban: bool,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    should_stop: Callable[[], bool],
) -> None:
    handlers: list[tuple[TelegramClient, Callable]] = []
    forward_entity = None
    notify_entity = None

    if mode == "dm_forward" and forward_group_link.strip():
        sample_client = await get_client(account_ids[0])
        forward_entity = await resolve_entity(sample_client, forward_group_link.strip())

    if mode == "keyword" and notify_group_link.strip():
        sample_client = await get_client(account_ids[0])
        notify_entity = await resolve_entity(sample_client, notify_group_link.strip())

    for account_id in account_ids:
        client = await get_client(account_id)

        async def handler(event, aid: str = account_id, bound_client: TelegramClient = client) -> None:
            if should_stop() or event.out:
                return

            try:
                text = event.raw_text or ""

                if mode == "dm_forward":
                    if not reply_message.strip() and not forward_entity:
                        return
                    if monitor_group_posts:
                        if not (event.is_group or event.is_channel):
                            return
                    elif not event.is_private:
                        return

                    if reply_message.strip():
                        await event.reply(reply_message, parse_mode=parse_mode or None)

                    if forward_entity:
                        await bound_client.forward_messages(forward_entity, event.message)

                    source = "群组" if event.is_group or event.is_channel else "私信"
                    msg = f"[{aid}] 私信转发模式 ({source}): {text[:60]}"
                    on_log("success", msg)
                    _append_monitor_log(msg)
                    return

                if mode == "keyword":
                    if not (event.is_group or event.is_channel):
                        return
                    if notify_entity and event.chat_id == notify_entity.id:
                        return

                    matched = any(
                        _match_keyword(text, keyword, global_match) for keyword in keywords
                    )
                    if keywords and not matched:
                        return

                    sender = await event.get_sender()
                    if dm_on_match.strip() and sender:
                        await bound_client.send_message(sender, dm_on_match)

                    if notify_entity:
                        await bound_client.forward_messages(notify_entity, event.message)

                    msg = f"[{aid}] 关键词匹配: {text[:60]}"
                    on_log("success", msg)
                    _append_monitor_log(msg)
            except Exception as exc:
                on_log("error", f"[{aid}] 监控处理失败: {exc}")
                if auto_spambot_unban and "restricted" in str(exc).lower():
                    try:
                        result = await try_spambot_unban(bound_client)
                        on_log("warn", f"[{aid}] {result}")
                    except Exception:
                        pass

        client.add_event_handler(handler, events.NewMessage(incoming=True))
        handlers.append((client, handler))
        on_log("info", f"[{account_id}] 监控已启动 ({mode})")

    try:
        while not should_stop():
            await asyncio.sleep(1)
    finally:
        for client, handler in handlers:
            client.remove_event_handler(handler)
        on_log("info", "监控已停止")
