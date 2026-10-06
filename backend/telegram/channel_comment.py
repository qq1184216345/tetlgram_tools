from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import GetFullChannelRequest

from backend.telegram.task_utils import AccountIntervalGate
from backend.telegram.utils import resolve_entity


async def comment_on_channel_post(
    client: TelegramClient,
    channel_ref: str,
    message_id: int,
    comment: str,
) -> None:
    """在频道帖子关联讨论组下评论。"""
    channel = await resolve_entity(client, channel_ref)
    full = await client(GetFullChannelRequest(channel))
    linked_id = getattr(full.full_chat, "linked_chat_id", None)
    if not linked_id:
        raise ValueError("该频道未开启讨论组，无法评论")

    msg = await client.get_messages(channel, ids=message_id)
    if not msg:
        raise ValueError(f"找不到频道消息 ID={message_id}")

    # comment_to 必须发给频道实体；Telethon 会解析到讨论组对应消息
    await client.send_message(
        channel,
        comment,
        comment_to=msg.id,
    )


async def run_channel_comment_loop(
    account_ids: list[str],
    posts: list[dict],
    comment: str,
    interval_min: int,
    interval_max: int,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
) -> None:
    import random

    success = 0
    failed = 0
    gate = AccountIntervalGate(interval_min, interval_max)
    for index, post in enumerate(posts):
        if should_stop():
            break
        account_id = account_ids[index % len(account_ids)]
        channel = str(post.get("channel", "")).strip()
        msg_id = int(post.get("message_id", 0) or 0)
        text = str(post.get("comment", "")).strip() or comment
        if not channel or not msg_id or not text:
            failed += 1
            on_log("error", f"无效帖子配置: {post}")
            on_progress(index + 1, success, failed)
            continue
        if await gate.wait_turn(account_id, should_stop, on_log):
            break
        try:
            client = await get_client(account_id)
            await comment_on_channel_post(client, channel, msg_id, text)
            success += 1
            on_log("success", f"[{account_id}] 评论成功: {channel}/{msg_id}")
            gate.arm(account_id)
        except FloodWaitError as exc:
            failed += 1
            on_log("warn", f"[{account_id}] 频繁限制 {exc.seconds}s，其它号继续")
            gate.block_for(account_id, exc.seconds)
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 评论失败 {channel}/{msg_id}: {exc}")
            gate.arm(account_id)
        on_progress(index + 1, success, failed)
