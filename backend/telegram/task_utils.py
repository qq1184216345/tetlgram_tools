from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime
from typing import Callable, Optional


def account_target_key(account_id: str, target: str) -> str:
    return f"{(account_id or '').strip()}\t{(target or '').strip()}"


def target_only_key(target: str) -> str:
    return (target or "").strip()


def _parse_dt(value: str) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        # datetime-local: 2026-08-30T18:30
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


async def wait_if_paused(
    pause_event: asyncio.Event,
    should_stop: Callable[[], bool],
) -> bool:
    while not pause_event.is_set():
        if should_stop():
            return True
        await asyncio.sleep(0.3)
    return should_stop()


def is_in_time_window(start_hour: int, end_hour: int) -> bool:
    """每日时段窗口。0–24 表示全天放开。支持跨夜（如 22–6）。"""
    start = max(0, min(24, int(start_hour)))
    end = max(0, min(24, int(end_hour)))
    if start <= 0 and end >= 24:
        return True
    if start == end:
        return True
    hour = datetime.now().hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def is_past_schedule_end(schedule_end_at: str) -> bool:
    end_at = _parse_dt(schedule_end_at)
    if not end_at:
        return False
    return datetime.now() >= end_at


async def wait_for_schedule_start(
    schedule_start_at: str,
    should_stop: Callable[[], bool],
    on_log: Optional[Callable[[str, str], None]] = None,
) -> bool:
    """等到 schedule_start_at；若已过则立即继续。返回 True 表示应停止。"""
    start_at = _parse_dt(schedule_start_at)
    if not start_at:
        return should_stop()

    now = datetime.now()
    if now >= start_at:
        return should_stop()

    if on_log:
        on_log("info", f"定时群发：将于 {start_at.strftime('%Y-%m-%d %H:%M')} 开始，等待中…")

    while datetime.now() < start_at:
        if should_stop():
            return True
        remaining = (start_at - datetime.now()).total_seconds()
        await asyncio.sleep(min(30, max(1, remaining)))

    if on_log:
        on_log("info", "已到达定时开始时间，开始发送")
    return should_stop()


async def wait_for_time_window(
    start_hour: int,
    end_hour: int,
    should_stop: Callable[[], bool],
    on_log: Optional[Callable[[str, str], None]] = None,
) -> bool:
    if is_in_time_window(start_hour, end_hour):
        return should_stop()

    label = f"{int(start_hour):02d}:00–{int(end_hour):02d}:00"
    if on_log:
        on_log("info", f"当前不在每日发送时段（{label}），等待进入窗口…")

    while not is_in_time_window(start_hour, end_hour):
        if should_stop():
            return True
        await asyncio.sleep(20)

    if on_log:
        on_log("info", f"已进入发送时段 {label}")
    return should_stop()


async def run_with_controls(
    pause_event: asyncio.Event,
    should_stop: Callable[[], bool],
    start_hour: int = 0,
    end_hour: int = 24,
    on_log: Optional[Callable[[str, str], None]] = None,
    schedule_start_at: str = "",
    schedule_end_at: str = "",
) -> bool:
    """
    统一任务闸门：
    1) 等到定时开始时刻
    2) 若超过定时结束时刻则停止
    3) 等待每日发送时段
    4) 处理暂停
    返回 True 表示调用方应停止当前目标/任务。
    """
    if await wait_for_schedule_start(schedule_start_at, should_stop, on_log):
        return True

    if is_past_schedule_end(schedule_end_at):
        if on_log:
            on_log("warn", "已超过定时结束时间，停止发送")
        return True

    if await wait_for_time_window(start_hour, end_hour, should_stop, on_log):
        return True

    return await wait_if_paused(pause_event, should_stop)


class AccountIntervalGate:
    """每个账号独立冷却，互不排队。"""

    def __init__(self, interval_min: int = 0, interval_max: int = 0) -> None:
        lo = max(0, int(interval_min))
        hi = max(lo, int(interval_max))
        self._lo = lo
        self._hi = hi
        self._next_ts: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def lock_for(self, account_id: str) -> asyncio.Lock:
        async with self._guard:
            lock = self._locks.get(account_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[account_id] = lock
            return lock

    async def wait_turn(
        self,
        account_id: str,
        should_stop: Callable[[], bool],
        on_log: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        due = self._next_ts.get(account_id, 0.0)
        wait_s = due - time.monotonic()
        if wait_s > 0.05:
            if on_log:
                on_log("info", f"[{account_id}] 间隔等待 {max(1, int(wait_s))} 秒")
            deadline = due
            while time.monotonic() < deadline:
                if should_stop():
                    return True
                await asyncio.sleep(min(0.4, max(0.05, deadline - time.monotonic())))
        return should_stop()

    def arm(self, account_id: str) -> int:
        delay = random.randint(self._lo, self._hi) if self._hi > 0 else 0
        self._next_ts[account_id] = time.monotonic() + delay
        return delay

    def block_for(self, account_id: str, seconds: float) -> None:
        extra = max(0.0, float(seconds))
        self._next_ts[account_id] = max(
            self._next_ts.get(account_id, 0.0),
            time.monotonic() + extra,
        )


async def run_per_account_jobs(
    jobs: list[tuple[str, str]],
    process_one: Callable,
    should_stop: Callable[[], bool],
    max_parallel: int = 0,
) -> None:
    """每个账号一条流水线，互不等待；账号内按间隔串行，第一条立即执行。"""
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for account_id, target in jobs:
        if account_id not in grouped:
            order.append(account_id)
            grouped[account_id] = []
        grouped[account_id].append(target)

    async def run_account(account_id: str, targets: list[str]) -> None:
        for target in targets:
            if should_stop():
                return
            await process_one(account_id, target)

    if not order:
        return
    limit = len(order) if max_parallel <= 0 else min(len(order), max(1, int(max_parallel)))
    if limit >= len(order):
        await asyncio.gather(*[run_account(account_id, grouped[account_id]) for account_id in order])
        return
    sem = asyncio.Semaphore(limit)

    async def run_limited(account_id: str) -> None:
        async with sem:
            await run_account(account_id, grouped[account_id])

    await asyncio.gather(*[run_limited(account_id) for account_id in order])
