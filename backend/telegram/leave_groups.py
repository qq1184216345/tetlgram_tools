from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.messages import DeleteChatUserRequest
from telethon.tl.types import Channel, Chat

from backend.telegram.task_utils import run_with_controls
from backend.telegram.utils import resolve_entity


async def leave_all_groups(
    client: TelegramClient,
    account_id: str,
    on_log: Callable[[str, str], None],
    include_channels: bool = False,
) -> tuple[int, int]:
    success = 0
    failed = 0
    me = await client.get_me()

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not isinstance(entity, (Channel, Chat)):
            continue
        if isinstance(entity, Channel) and not entity.megagroup and not include_channels:
            continue
        try:
            if isinstance(entity, Channel):
                await client(LeaveChannelRequest(entity))
            else:
                await client(DeleteChatUserRequest(entity.id, me.id))
            success += 1
            title = getattr(entity, "title", str(entity.id))
            on_log("success", f"[{account_id}] 已退出: {title}")
        except FloodWaitError as exc:
            failed += 1
            on_log("warn", f"[{account_id}] 频繁限制，等待 {exc.seconds}s")
            await asyncio.sleep(exc.seconds)
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 退群失败: {exc}")
        await asyncio.sleep(1)

    return success, failed


async def leave_specific_targets(
    client: TelegramClient,
    account_id: str,
    targets: list[str],
    on_log: Callable[[str, str], None],
) -> tuple[int, int]:
    success = 0
    failed = 0
    me = await client.get_me()

    for target in targets:
        try:
            entity = await resolve_entity(client, target)
            if isinstance(entity, Channel):
                await client(LeaveChannelRequest(entity))
            elif isinstance(entity, Chat):
                await client(DeleteChatUserRequest(entity.id, me.id))
            else:
                await client.delete_dialog(entity)
            success += 1
            title = getattr(entity, "title", target)
            on_log("success", f"[{account_id}] 已退出指定: {title}")
        except FloodWaitError as exc:
            failed += 1
            on_log("warn", f"[{account_id}] 频繁限制，等待 {exc.seconds}s: {target}")
            await asyncio.sleep(exc.seconds)
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 退出失败 {target}: {exc}")
        await asyncio.sleep(1)

    return success, failed


async def run_leave_groups_loop(
    account_ids: list[str],
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    pause_event: asyncio.Event | None = None,
    targets: list[str] | None = None,
    include_channels: bool = False,
) -> None:
    pause = pause_event or asyncio.Event()
    if not pause_event:
        pause.set()

    success_accounts = 0
    failed_accounts = 0
    specific = [t.strip() for t in (targets or []) if t.strip()]

    for index, account_id in enumerate(account_ids):
        if await run_with_controls(pause, should_stop):
            break
        try:
            client = await get_client(account_id)
            if specific:
                ok, fail = await leave_specific_targets(
                    client, account_id, specific, on_log
                )
            else:
                ok, fail = await leave_all_groups(
                    client, account_id, on_log, include_channels=include_channels
                )
            on_log("info", f"[{account_id}] 退群完成: 成功 {ok}, 失败 {fail}")
            success_accounts += 1
        except Exception as exc:
            failed_accounts += 1
            on_log("error", f"[{account_id}] 退群任务失败: {exc}")
        on_progress(index + 1, success_accounts, failed_accounts)
