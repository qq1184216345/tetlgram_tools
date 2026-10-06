from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserAlreadyParticipantError

from backend.storage.account_meta import set_join_status
from backend.telegram.join_verify import try_pass_join_verification
from backend.telegram.task_utils import (
    AccountIntervalGate,
    account_target_key,
    run_per_account_jobs,
    run_with_controls,
    wait_for_schedule_start,
)
from backend.telegram.utils import (
    collect_joined_usernames_and_titles,
    is_already_joined,
    is_joined_in_lookup,
    join_target,
    normalize_target,
)


async def _account_covers_target(
    client: TelegramClient,
    target: str,
    usernames: set[str],
    titles: set[str],
) -> bool:
    cached = is_joined_in_lookup(target, usernames, titles)
    if cached is not None:
        return cached
    return await is_already_joined(client, target)


async def run_join_group_loop(
    account_ids: list[str],
    targets: list[str],
    interval_min: int,
    interval_max: int,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    pause_event: asyncio.Event | None = None,
    start_hour: int = 0,
    end_hour: int = 24,
    no_duplicate_join: bool = True,
    request_join: bool = False,
    auto_pass_verify: bool = True,
    schedule_start_at: str = "",
    schedule_end_at: str = "",
    thread_count: int = 1,
    skip_keys: set[str] | None = None,
    initial_success: int = 0,
    initial_failed: int = 0,
    on_job_done: Callable[[str], None] | None = None,
) -> None:
    pause = pause_event or asyncio.Event()
    if not pause_event:
        pause.set()

    if await wait_for_schedule_start(schedule_start_at, should_stop, on_log):
        return

    success = max(0, int(initial_success))
    failed = max(0, int(initial_failed))
    lock = asyncio.Lock()
    claimed: set[str] = set()
    gate = AccountIntervalGate(interval_min, interval_max)
    lookups: dict[str, tuple[set[str], set[str]]] = {}
    work_targets = [t.strip() for t in targets if t.strip()]
    resume_keys = skip_keys or set()
    if resume_keys and no_duplicate_join:
        kept = [t for t in work_targets if normalize_target(t) not in resume_keys]
        skipped_resume = len(work_targets) - len(kept)
        work_targets = kept
        if skipped_resume:
            on_log(
                "info",
                f"从暂停处继续，已跳过 {skipped_resume} 个群，按最新配置处理剩余 {len(work_targets)} 个",
            )

    if no_duplicate_join:
        on_log("info", "不重复加群：并行检查勾选账号已加入的群…")

        async def scan_account(account_id: str) -> None:
            try:
                client = await get_client(account_id)
                usernames, titles = await collect_joined_usernames_and_titles(client)
                lookups[account_id] = (usernames, titles)
                for target in work_targets:
                    key = normalize_target(target)
                    async with lock:
                        if key in claimed:
                            continue
                    if await _account_covers_target(client, target, usernames, titles):
                        async with lock:
                            if key in claimed:
                                continue
                            claimed.add(key)
                        if on_job_done:
                            on_job_done(key)
                        on_log("info", f"[{account_id}] 已在群内，其它账号不再加入: {target}")
            except Exception as exc:
                on_log("warn", f"[{account_id}] 检查已加入群失败: {exc}")

        await asyncio.gather(*[scan_account(account_id) for account_id in account_ids])
        remaining = [t for t in work_targets if normalize_target(t) not in claimed]
        skipped = len(work_targets) - len(remaining)
        success += skipped
        jobs = [(account_ids[i % len(account_ids)], t) for i, t in enumerate(remaining)]
        on_log(
            "info",
            f"不重复加群：{len(work_targets)} 个目标，已有账号在群 {skipped} 个，待加入 {len(remaining)} 个；各号并行，首次立即加入",
        )
        on_progress(success + failed, success, failed)
    else:
        jobs = [(aid, t) for aid in account_ids for t in work_targets]
        if resume_keys:
            kept_jobs = [
                (aid, t)
                for aid, t in jobs
                if account_target_key(aid, t) not in resume_keys
            ]
            skipped_resume = len(jobs) - len(kept_jobs)
            jobs = kept_jobs
            if skipped_resume:
                on_log(
                    "info",
                    f"从暂停处继续，已跳过 {skipped_resume} 项，按最新配置处理剩余 {len(jobs)} 项",
                )
        on_log(
            "info",
            f"各账号并行加群：{len(account_ids)} 个账号 × {len(work_targets)} 个目标，首次立即加入",
        )
        on_progress(success + failed, success, failed)

    async def process_one(account_id: str, target: str) -> None:
        nonlocal success, failed
        if should_stop():
            return
        if await run_with_controls(
            pause,
            should_stop,
            start_hour,
            end_hour,
            on_log,
            schedule_start_at="",
            schedule_end_at=schedule_end_at,
        ):
            return

        key = normalize_target(target)
        if no_duplicate_join:
            async with lock:
                if key in claimed:
                    return

        if await gate.wait_turn(account_id, should_stop, on_log):
            return

        set_join_status(account_id, "running")
        flood_blocked = False
        try:
            on_log("info", f"[{account_id}] 正在加入: {target}")
            client = await get_client(account_id)
            if account_id not in lookups:
                lookups[account_id] = await collect_joined_usernames_and_titles(client)
            usernames, titles = lookups[account_id]
            already = await _account_covers_target(client, target, usernames, titles)
            if no_duplicate_join:
                async with lock:
                    if key in claimed:
                        return
                    claimed.add(key)
            if already:
                async with lock:
                    success += 1
                on_log("info", f"[{account_id}] 已在群内，跳过: {target}")
            else:
                await _join_one(client, account_id, target)
        except UserAlreadyParticipantError:
            async with lock:
                if no_duplicate_join:
                    claimed.add(key)
                success += 1
            on_log("info", f"[{account_id}] 已在群内: {target}")
        except FloodWaitError as exc:
            async with lock:
                if no_duplicate_join:
                    claimed.discard(key)
                failed += 1
            on_log(
                "warn",
                f"[{account_id}] 频繁限制 {exc.seconds}s，该账号稍后重试，其它号继续: {target}",
            )
            gate.block_for(account_id, exc.seconds)
            flood_blocked = True
        except Exception as exc:
            async with lock:
                if no_duplicate_join:
                    claimed.discard(key)
                failed += 1
            on_log("error", f"[{account_id}] 加群失败 {target}: {exc}")
        finally:
            set_join_status(account_id, "idle")
            if not flood_blocked:
                gate.arm(account_id)
            async with lock:
                on_progress(success + failed, success, failed)
            if on_job_done:
                on_job_done(
                    key if no_duplicate_join else account_target_key(account_id, target)
                )

    async def _join_one(client: TelegramClient, account_id: str, target: str) -> None:
        nonlocal success
        await join_target(client, target, request_join=request_join)
        if auto_pass_verify and not request_join:
            try:
                from backend.config import settings

                use_ai = bool(getattr(settings, "ai_verify_enabled", False))
                passed = await try_pass_join_verification(
                    client,
                    target,
                    timeout=10.0 if use_ai else 8.0,
                    on_log=on_log,
                    use_ai=use_ai,
                )
                if passed:
                    on_log("success", f"[{account_id}] 已自动过验证: {target}")
            except Exception as exc:
                on_log("warn", f"[{account_id}] 过验证尝试失败: {exc}")
        async with lock:
            success += 1
        msg = f"[{account_id}] 加群成功: {target}"
        if request_join:
            msg = f"[{account_id}] 已申请加群: {target}"
        on_log("success", msg)

    if not jobs:
        on_log("info", "没有需要新加入的群")
        return

    await run_per_account_jobs(
        jobs,
        process_one,
        should_stop,
        max_parallel=0 if int(thread_count) <= 1 else int(thread_count),
    )
