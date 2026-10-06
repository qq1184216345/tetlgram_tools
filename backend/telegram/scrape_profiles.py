from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import (
    User,
    UserStatusEmpty,
    UserStatusLastMonth,
    UserStatusLastWeek,
    UserStatusOffline,
    UserStatusOnline,
    UserStatusRecently,
)

from backend.config import SCRAPE_DIR
from backend.telegram.task_utils import AccountIntervalGate


def _status_text(user: User) -> str:
    status = getattr(user, "status", None)
    if isinstance(status, UserStatusOnline):
        return "在线"
    if isinstance(status, UserStatusRecently):
        return "最近在线"
    if isinstance(status, UserStatusLastWeek):
        return "一周内上线"
    if isinstance(status, UserStatusLastMonth):
        return "一月内上线"
    if isinstance(status, UserStatusOffline):
        return "最近在线"
    if isinstance(status, UserStatusEmpty) or status is None:
        return "未知"
    return "最近在线"


def _nickname(user: User) -> str:
    first = user.first_name if user.first_name is not None else "None"
    last = user.last_name if user.last_name is not None else "None"
    return f"{first} {last}".strip()


def format_profile_line(user: User) -> str:
    username = (user.username or str(user.id)).lstrip("@")
    nick = _nickname(user)
    online = _status_text(user)
    about = getattr(user, "about", None)
    if about is None or str(about).strip() == "":
        about_part = "null"
    else:
        cleaned = str(about).replace("\n", " ").strip()
        about_part = '"' + cleaned + '"'
    return (
        username
        + ' - - - 昵称："'
        + nick
        + '" | 在线状态："'
        + online
        + '" | 简介：'
        + about_part
    )


async def run_scrape_profiles_loop(
    account_ids: list[str],
    targets: list[str],
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    interval_sec: float = 5,
) -> str:
    if not account_ids:
        raise ValueError("请至少选择一个账号")
    if not targets:
        raise ValueError("请填写用户名列表")

    SCRAPE_DIR.mkdir(parents=True, exist_ok=True)
    output = SCRAPE_DIR / "过滤用户.txt"
    lines: list[str] = []
    success = 0
    failed = 0
    delay = max(0, int(interval_sec))
    gate = AccountIntervalGate(delay, delay)

    for index, raw in enumerate(targets):
        if should_stop():
            break
        target = raw.strip()
        if not target:
            continue
        account_id = account_ids[index % len(account_ids)]
        if await gate.wait_turn(account_id, should_stop, on_log):
            break
        try:
            client = await get_client(account_id)
            entity = await client.get_entity(target)
            if not isinstance(entity, User):
                failed += 1
                on_log("warn", f"[{account_id}] 不是用户: {target}")
            else:
                about = None
                try:
                    full_user = await client(GetFullUserRequest(entity))
                    about = getattr(full_user.full_user, "about", None)
                except Exception:
                    pass
                setattr(entity, "about", about)
                lines.append(format_profile_line(entity))
                success += 1
                on_log("success", f"[{account_id}] 用户: {target}-获取成功ok-")
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 获取失败 {target}: {exc}")
        gate.arm(account_id)

        on_progress(index + 1, success, failed)

    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    on_log("info", f"过滤用户任务已完成，已保存: {output}")
    return str(output)
