from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Awaitable, Callable

from telethon import TelegramClient

_online_tasks: dict[str, asyncio.Task] = {}
_online_stop: dict[str, asyncio.Event] = {}


def is_keep_online_enabled(account_id: str) -> bool:
    task = _online_tasks.get(account_id)
    return bool(task and not task.done())


def list_keep_online_accounts() -> list[str]:
    return [aid for aid, task in _online_tasks.items() if task and not task.done()]


async def _heartbeat_loop(
    account_id: str,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None] | None,
    interval_sec: float,
) -> None:
    stop = _online_stop[account_id]
    tick = 0
    while not stop.is_set():
        try:
            client = await get_client(account_id)
            stamp = datetime.now().strftime("%H:%M:%S")
            await client.send_message("me", f"keep-online {stamp}")
            tick += 1
            if on_log:
                on_log("info", f"[{account_id}] 收藏夹心跳 #{tick}")
        except Exception as exc:
            if on_log:
                on_log("warn", f"[{account_id}] 保持在线失败: {exc}")
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(30.0, interval_sec))
            break
        except asyncio.TimeoutError:
            continue


async def start_keep_online(
    account_ids: list[str],
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None] | None = None,
    interval_sec: float = 60,
) -> list[str]:
    started: list[str] = []
    for account_id in account_ids:
        if is_keep_online_enabled(account_id):
            if on_log:
                on_log("info", f"[{account_id}] 保持在线已在运行")
            started.append(account_id)
            continue
        stop = asyncio.Event()
        _online_stop[account_id] = stop
        task = asyncio.create_task(
            _heartbeat_loop(account_id, get_client, on_log, interval_sec)
        )
        _online_tasks[account_id] = task
        started.append(account_id)
        if on_log:
            on_log("success", f"[{account_id}] 启用维持账号在线已设置成功")
    return started


async def stop_keep_online(account_ids: list[str] | None = None) -> list[str]:
    targets = account_ids or list(_online_tasks.keys())
    stopped: list[str] = []
    for account_id in targets:
        stop = _online_stop.get(account_id)
        task = _online_tasks.get(account_id)
        if stop:
            stop.set()
        if task:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2)
            except Exception:
                task.cancel()
        _online_tasks.pop(account_id, None)
        _online_stop.pop(account_id, None)
        stopped.append(account_id)
    return stopped
