from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import ChatWriteForbiddenError, FloodWaitError

from backend.telegram.task_utils import AccountIntervalGate
from backend.telegram.utils import join_target, resolve_entity


async def run_warm_group_loop(
    account_ids: list[str],
    group_links: list[str],
    messages: list[str],
    interval_min: int,
    interval_max: int,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    rounds: int = 1,
    join_only: bool = False,
) -> None:
    if not group_links:
        raise ValueError("请至少填写一个群组链接")

    total_steps = len(group_links) * max(1, len(messages)) * rounds if not join_only else len(group_links) * rounds
    success = 0
    failed = 0
    current = 0
    gate = AccountIntervalGate(interval_min, interval_max)

    for round_num in range(rounds):
        if should_stop():
            break
        on_log("info", f"--- 第 {round_num + 1}/{rounds} 轮 ---")

        for group_link in group_links:
            if should_stop():
                break

            account_id = account_ids[current % len(account_ids)]
            if await gate.wait_turn(account_id, should_stop, on_log):
                break
            try:
                client = await get_client(account_id)
                await join_target(client, group_link)
                on_log("success", f"[{account_id}] 已加入群: {group_link}")
                gate.arm(account_id)

                if join_only or not messages:
                    success += 1
                    current += 1
                    on_progress(current, success, failed)
                else:
                    entity = await resolve_entity(client, group_link)
                    for index, message in enumerate(messages):
                        if should_stop():
                            break
                        sender_id = account_ids[(current + index) % len(account_ids)]
                        if await gate.wait_turn(sender_id, should_stop, on_log):
                            break
                        sender = await get_client(sender_id)
                        try:
                            await sender.send_message(entity, message)
                            success += 1
                            current += 1
                            on_log("success", f"[{sender_id}] 发送成功: {message[:30]}...")
                            gate.arm(sender_id)
                        except ChatWriteForbiddenError:
                            failed += 1
                            current += 1
                            on_log("error", f"[{sender_id}] 无发言权限")
                            gate.arm(sender_id)
                        except FloodWaitError as exc:
                            failed += 1
                            current += 1
                            on_log("warn", f"[{sender_id}] 频繁限制 {exc.seconds}s，其它号继续")
                            gate.block_for(sender_id, exc.seconds)
                        except Exception as exc:
                            failed += 1
                            current += 1
                            on_log("error", f"[{sender_id}] 发送失败: {exc}")
                            gate.arm(sender_id)
                        on_progress(current, success, failed)
            except FloodWaitError as exc:
                failed += 1
                current += 1
                on_log("warn", f"[{account_id}] 频繁限制 {exc.seconds}s，其它号继续")
                gate.block_for(account_id, exc.seconds)
                on_progress(current, success, failed)
            except Exception as exc:
                failed += 1
                current += 1
                on_log("error", f"[{account_id}] 炒群失败 {group_link}: {exc}")
                gate.arm(account_id)
                on_progress(current, success, failed)
