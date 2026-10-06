from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError, PeerIdInvalidError, UserPrivacyRestrictedError
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from backend.config import LOG_DIR
from backend.telegram.contact_send import send_contact_card
from backend.telegram.forward import forward_channel_message, pick_forward_target
from backend.telegram.message_variants import add_random_padding, pick_message_variant
from backend.telegram.postbot import send_postbot_message
from backend.telegram.result_files import append_result_line
from backend.telegram.rich_text import parse_rich_text
from backend.telegram.spambot import try_spambot_unban
from backend.telegram.task_utils import (
    AccountIntervalGate,
    run_per_account_jobs,
    run_with_controls,
    wait_for_schedule_start,
)
from backend.telegram.utils import resolve_entity


def _append_dm_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"私信_{datetime.now().strftime('%Y%m%d')}.txt"
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


DM_SUCCESS_FILE = "私信成功.txt"
DM_FAIL_FILE = "私信失败.txt"


async def resolve_user(client: TelegramClient, target: str):
    raw = target.strip()
    if not raw:
        raise ValueError("目标为空")

    if raw.startswith("@"):
        return await client.get_entity(raw)

    if raw.startswith("+") or raw.isdigit():
        phone = raw if raw.startswith("+") else f"+{raw}"
        result = await client(
            ImportContactsRequest(
                [
                    InputPhoneContact(
                        client_id=0,
                        phone=phone,
                        first_name="tmp",
                        last_name="",
                    )
                ]
            )
        )
        if result.users:
            return result.users[0]
        raise ValueError(f"无法通过手机号找到用户: {phone}")

    if re.match(r"^\d+$", raw):
        return await client.get_entity(int(raw))

    return await client.get_entity(raw)


async def resolve_dm_target(client: TelegramClient, target: str, target_type: str):
    if target_type == "group":
        return await resolve_entity(client, target)
    return await resolve_user(client, target)


def _prepare_message(
    message: str,
    parse_mode: str | None,
    use_rich_tags: bool,
    multi_line_mode: bool,
    random_prefix_len: int,
    random_suffix_len: int,
) -> tuple[str, str | None]:
    text = pick_message_variant(message, multi_line_mode)
    text = add_random_padding(text, random_prefix_len, random_suffix_len)
    if use_rich_tags:
        return parse_rich_text(text)
    return text, parse_mode or None


async def run_dm_loop(
    account_ids: list[str],
    targets: list[str],
    message: str,
    parse_mode: str | None,
    interval_min: int,
    interval_max: int,
    use_rich_tags: bool,
    use_postbot: bool,
    postbot_code: str,
    send_mode: str,
    media_path: str,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    multi_line_mode: bool = False,
    random_prefix_len: int = 0,
    random_suffix_len: int = 0,
    thread_count: int = 1,
    pause_event: asyncio.Event | None = None,
    start_hour: int = 0,
    end_hour: int = 24,
    auto_spambot_unban: bool = False,
    target_type: str = "user",
    forward_channel: str = "",
    forward_message_id: int = 0,
    forward_message_links: list[str] | None = None,
    forward_hide_source: bool = True,
    contact_target: str = "",
    contact_first_name: str = "",
    contact_last_name: str = "",
    voice_call: bool = False,
    save_result_files: bool = True,
    result_with_timestamp: bool = False,
    schedule_start_at: str = "",
    schedule_end_at: str = "",
) -> list[dict]:
    pause = pause_event or asyncio.Event()
    if not pause_event:
        pause.set()

    failed_items: list[dict] = []
    if await wait_for_schedule_start(schedule_start_at, should_stop, on_log):
        return failed_items

    success = 0
    failed = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(max(8, len(account_ids) * max(1, thread_count)))
    # PeerFlood / 双向限制：仅对该目标记失败，可选问一次 SpamBot；不整号停用
    flood_checked: set[str] = set()
    gate = AccountIntervalGate(interval_min, interval_max)

    def _write_ok(target: str) -> None:
        if save_result_files:
            append_result_line(DM_SUCCESS_FILE, target, with_timestamp=result_with_timestamp)

    def _write_fail(target: str, reason: str = "") -> None:
        if save_result_files:
            append_result_line(
                DM_FAIL_FILE, target, with_timestamp=result_with_timestamp, extra=reason
            )

    async def record_failure(account_id: str, target: str, reason: str) -> None:
        nonlocal failed
        async with lock:
            failed += 1
            failed_items.append(
                {"target": target, "reason": reason, "account_id": account_id}
            )

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

        acc_lock = await gate.lock_for(account_id)
        async with acc_lock:
            if await gate.wait_turn(account_id, should_stop, on_log):
                return
            async with sem:
                armed = False
                try:
                    client = await get_client(account_id)
                    entity = await resolve_dm_target(client, target, target_type)

                    if use_postbot:
                        text, _ = _prepare_message(
                            message, parse_mode, False, multi_line_mode,
                            random_prefix_len, random_suffix_len,
                        )
                        await send_postbot_message(client, entity, postbot_code, text)
                    elif voice_call and target_type == "user":
                        from backend.telegram.voice_call import start_voice_call

                        result = await start_voice_call(client, target)
                        on_log("success", f"[{account_id}] {result}")
                    elif send_mode in ("forward", "sticker"):
                        channel_ref, msg_id = pick_forward_target(
                            forward_channel, forward_message_id, forward_message_links
                        )
                        await forward_channel_message(
                            client, target, channel_ref, msg_id, forward_hide_source, False
                        )
                    elif send_mode == "contact":
                        await send_contact_card(
                            client,
                            entity,
                            contact_target,
                            contact_first_name,
                            contact_last_name,
                        )
                    elif send_mode in ("image", "file") and media_path:
                        path = Path(media_path)
                        if not path.exists():
                            raise ValueError(f"媒体文件不存在: {media_path}")
                        text, mode = _prepare_message(
                            message, parse_mode, use_rich_tags, multi_line_mode,
                            random_prefix_len, random_suffix_len,
                        )
                        await client.send_file(
                            entity,
                            str(path),
                            caption=text or None,
                            parse_mode=mode,
                            force_document=send_mode == "file",
                        )
                    else:
                        text, mode = _prepare_message(
                            message, parse_mode, use_rich_tags, multi_line_mode,
                            random_prefix_len, random_suffix_len,
                        )
                        await client.send_message(entity, text, parse_mode=mode)

                    async with lock:
                        success += 1
                    msg = f"[{account_id}] 私信成功: {target}"
                    on_log("success", msg)
                    _append_dm_log(f"SUCCESS {msg}")
                    _write_ok(target)
                except PeerIdInvalidError:
                    reason = "Peer ID 无效"
                    await record_failure(account_id, target, reason)
                    msg = f"[{account_id}] {reason}: {target}"
                    on_log("error", msg)
                    _append_dm_log(f"FAIL {msg}")
                    _write_fail(target, reason)
                except UserPrivacyRestrictedError:
                    reason = "用户隐私限制，无法私信"
                    await record_failure(account_id, target, reason)
                    msg = f"[{account_id}] {reason}: {target}"
                    on_log("error", msg)
                    _append_dm_log(f"FAIL {msg}")
                    _write_fail(target, reason)
                except PeerFloodError:
                    # Telegram 常把「只能给双向联系人发消息」也报成 PeerFlood，
                    # 不等于整号刷爆；只记本目标失败，账号继续跑后续目标。
                    reason = "双向联系人限制/防刷（仅本目标失败，账号继续）"
                    await record_failure(account_id, target, reason)
                    msg = f"[{account_id}] {reason}: {target}"
                    on_log("warn", msg)
                    _append_dm_log(f"FAIL {msg}")
                    _write_fail(target, reason)

                    if auto_spambot_unban and account_id not in flood_checked:
                        flood_checked.add(account_id)
                        try:
                            client = await get_client(account_id)
                            result = await try_spambot_unban(client)
                            on_log("warn", f"[{account_id}] {result}")
                        except Exception as exc:
                            on_log("error", f"[{account_id}] SpamBot 处理失败: {exc}")
                    armed = True
                except FloodWaitError as exc:
                    reason = f"频繁限制，需等待 {exc.seconds}s"
                    await record_failure(account_id, target, reason)
                    on_log("warn", f"[{account_id}] {reason}，其它号继续: {target}")
                    _write_fail(target, reason)
                    gate.block_for(account_id, exc.seconds)
                    armed = True
                except Exception as exc:
                    reason = str(exc)[:200] or "未知错误"
                    await record_failure(account_id, target, reason)
                    msg = f"[{account_id}] 私信失败 {target}: {reason}"
                    on_log("error", msg)
                    _append_dm_log(f"FAIL {msg}")
                    _write_fail(target, reason)

                async with lock:
                    current = success + failed
                    on_progress(current, success, failed)

                if not armed:
                    gate.arm(account_id)

    # 勾选的每个账号都要对全部目标各发一遍（非分流）
    jobs = [(aid, target) for aid in account_ids for target in targets]
    on_log(
        "info",
        f"各账号并行私信：{len(account_ids)} 个账号 × {len(targets)} 个目标，首次立即发送",
    )
    await run_per_account_jobs(jobs, process_one, should_stop)
    return failed_items
