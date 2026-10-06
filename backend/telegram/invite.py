from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, UserNotMutualContactError
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest, ExportChatInviteRequest

from backend.telegram.dm import resolve_user
from backend.telegram.result_files import append_result_line
from backend.telegram.task_utils import AccountIntervalGate, run_per_account_jobs
from backend.telegram.utils import resolve_entity

INVITE_SUCCESS_FILE = "拉人成功.txt"
INVITE_FAIL_FILE = "拉人失败.txt"


async def invite_user_to_group(
    client: TelegramClient, group_link: str, user_target: str
) -> None:
    group = await resolve_entity(client, group_link)
    user = await resolve_user(client, user_target)

    if hasattr(group, "megagroup") or getattr(group, "broadcast", False):
        await client(InviteToChannelRequest(group, [user]))
    else:
        await client(AddChatUserRequest(group.id, user, fwd_limit=10))


async def run_invite_loop(
    account_ids: list[str],
    group_link: str,
    user_targets: list[str],
    interval_min: int,
    interval_max: int,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    make_public: bool = False,
    account_loop_count: int = 1,
    stop_after_n: int = 0,
    thread_count: int = 1,
    save_result_files: bool = True,
    result_with_timestamp: bool = False,
) -> None:
    success = 0
    failed = 0
    lock = asyncio.Lock()
    invited_total = 0
    public_exported = False
    gate = AccountIntervalGate(interval_min, interval_max)

    def _write_ok(target: str) -> None:
        if save_result_files:
            append_result_line(INVITE_SUCCESS_FILE, target, with_timestamp=result_with_timestamp)

    def _write_fail(target: str, reason: str = "") -> None:
        if save_result_files:
            append_result_line(
                INVITE_FAIL_FILE, target, with_timestamp=result_with_timestamp, extra=reason
            )

    async def process_one(account_id: str, target: str) -> None:
        nonlocal success, failed, invited_total, public_exported
        if should_stop():
            return
        if stop_after_n > 0 and invited_total >= stop_after_n:
            return

        acc_lock = await gate.lock_for(account_id)
        async with acc_lock:
            if await gate.wait_turn(account_id, should_stop, on_log):
                return
            try:
                client = await get_client(account_id)
                do_export = False
                if make_public:
                    async with lock:
                        do_export = not public_exported
                        public_exported = True
                if do_export:
                    try:
                        group = await resolve_entity(client, group_link)
                        result = await client(ExportChatInviteRequest(peer=group))
                        on_log("info", f"[{account_id}] 群邀请链接: {result.link}")
                    except Exception as exc:
                        on_log("warn", f"[{account_id}] 获取公开链接失败: {exc}")

                on_log("info", f"[{account_id}] 正在拉人: {target}")
                await invite_user_to_group(client, group_link, target)
                async with lock:
                    success += 1
                    invited_total += 1
                on_log("success", f"[{account_id}] 拉人成功: {target}")
                _write_ok(target)
                gate.arm(account_id)
            except UserPrivacyRestrictedError:
                async with lock:
                    failed += 1
                on_log("error", f"[{account_id}] 用户隐私限制: {target}")
                _write_fail(target, "隐私限制")
                gate.arm(account_id)
            except UserNotMutualContactError:
                async with lock:
                    failed += 1
                on_log("error", f"[{account_id}] 非互相联系人: {target}")
                _write_fail(target, "非互相联系人")
                gate.arm(account_id)
            except FloodWaitError as exc:
                async with lock:
                    failed += 1
                on_log("warn", f"[{account_id}] 频繁限制 {exc.seconds}s，其它号继续")
                _write_fail(target, f"FloodWait {exc.seconds}s")
                gate.block_for(account_id, exc.seconds)
            except Exception as exc:
                async with lock:
                    failed += 1
                on_log("error", f"[{account_id}] 拉人失败 {target}: {exc}")
                _write_fail(target, str(exc)[:200])
                gate.arm(account_id)

            async with lock:
                on_progress(success + failed, success, failed)

    jobs: list[tuple[str, str]] = []
    for loop_round in range(max(1, account_loop_count)):
        for index, target in enumerate(user_targets):
            account_id = account_ids[(index + loop_round) % len(account_ids)]
            jobs.append((account_id, target))
    on_log("info", f"各账号并行拉人：{len(account_ids)} 个账号，首次立即执行")
    await run_per_account_jobs(
        jobs,
        process_one,
        should_stop,
        max_parallel=0 if int(thread_count) <= 1 else int(thread_count),
    )
