from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import (
    ChatWriteForbiddenError,
    FloodWaitError,
    PeerFloodError,
    PeerIdInvalidError,
    UserBannedInChannelError,
)
from telethon.tl.functions.channels import LeaveChannelRequest

from backend.storage.account_ads import get_account_ad
from backend.storage.account_meta import increment_broadcast_success, set_broadcast_status
from backend.telegram.contact_send import send_contact_card
from backend.telegram.export_groups import iter_joined_group_targets, list_joined_group_targets
from backend.telegram.forward import (
    forward_channel_message,
    pick_forward_target,
)
from backend.telegram.message_variants import add_random_padding, pick_message_variant
from backend.telegram.postbot import send_postbot_message
from backend.telegram.rich_text import parse_rich_text
from backend.telegram.spambot import try_spambot_unban
from backend.telegram.task_utils import (
    AccountIntervalGate,
    account_target_key,
    run_per_account_jobs,
    run_with_controls,
    wait_for_schedule_start,
)
from backend.telegram.utils import is_already_joined, join_target, resolve_entity


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


async def send_broadcast_message(
    client: TelegramClient,
    target: str,
    message: str,
    parse_mode: str | None,
    auto_join: bool,
    use_rich_tags: bool = False,
    use_postbot: bool = False,
    postbot_code: str = "",
    send_mode: str = "text",
    media_path: str = "",
    forward_channel: str = "",
    forward_message_id: int = 0,
    forward_message_links: list[str] | None = None,
    forward_hide_source: bool = True,
    multi_line_mode: bool = False,
    random_prefix_len: int = 0,
    random_suffix_len: int = 0,
    no_duplicate_join: bool = False,
    combined_send: bool = False,
    contact_target: str = "",
    contact_first_name: str = "",
    contact_last_name: str = "",
    auto_delete_after_sec: int = 0,
) -> None:
    if use_postbot:
        if auto_join:
            if not (no_duplicate_join and await is_already_joined(client, target)):
                try:
                    await join_target(client, target)
                except Exception:
                    pass
        entity = await resolve_entity(client, target)
        await send_postbot_message(client, entity, postbot_code, message)
        return

    if send_mode in ("forward", "sticker"):
        channel_ref, msg_id = pick_forward_target(
            forward_channel, forward_message_id, forward_message_links
        )
        await forward_channel_message(
            client, target, channel_ref, msg_id, forward_hide_source, auto_join
        )
        return

    if send_mode == "contact":
        if auto_join:
            if not (no_duplicate_join and await is_already_joined(client, target)):
                try:
                    await join_target(client, target)
                except Exception:
                    pass
        entity = await resolve_entity(client, target)
        await send_contact_card(
            client,
            entity,
            contact_target,
            contact_first_name,
            contact_last_name,
        )
        return

    if auto_join:
        if not (no_duplicate_join and await is_already_joined(client, target)):
            try:
                await join_target(client, target)
            except Exception:
                pass

    entity = await resolve_entity(client, target)
    text, mode = _prepare_message(
        message,
        parse_mode,
        use_rich_tags and not use_postbot,
        multi_line_mode,
        random_prefix_len,
        random_suffix_len,
    )

    effective_mode = send_mode
    if combined_send and media_path:
        effective_mode = "image"

    if effective_mode in ("image", "file", "combined") and media_path:
        path = Path(media_path)
        if not path.exists():
            raise ValueError(f"媒体文件不存在: {media_path}")
        force_doc = effective_mode == "file"
        sent = await client.send_file(
            entity,
            str(path),
            caption=text or None,
            parse_mode=mode,
            force_document=force_doc,
        )
        if auto_delete_after_sec > 0:
            msg_ids = [m.id for m in sent] if isinstance(sent, list) else [sent.id]
            await asyncio.sleep(auto_delete_after_sec)
            await client.delete_messages(entity, msg_ids)
    else:
        if not text.strip():
            raise ValueError("消息内容不能为空")
        sent = await client.send_message(entity, text, parse_mode=mode)
        if auto_delete_after_sec > 0:
            await asyncio.sleep(auto_delete_after_sec)
            await client.delete_messages(entity, sent.id)


async def run_broadcast_loop(
    account_ids: list[str],
    targets: list[str],
    message: str,
    parse_mode: str | None,
    interval_min: int,
    interval_max: int,
    auto_join: bool,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    use_joined_groups: bool = False,
    on_set_total: Callable[[int], None] | None = None,
    use_rich_tags: bool = False,
    use_postbot: bool = False,
    postbot_code: str = "",
    send_mode: str = "text",
    media_path: str = "",
    forward_channel: str = "",
    forward_message_id: int = 0,
    forward_message_links: list[str] | None = None,
    forward_hide_source: bool = True,
    multi_line_mode: bool = False,
    random_prefix_len: int = 0,
    random_suffix_len: int = 0,
    thread_count: int = 1,
    pause_event: asyncio.Event | None = None,
    start_hour: int = 0,
    end_hour: int = 24,
    auto_spambot_unban: bool = False,
    no_duplicate_join: bool = False,
    random_order: bool = False,
    round_rest_min: int = 0,
    round_rest_max: int = 0,
    exit_muted_groups: bool = False,
    combined_send: bool = False,
    contact_target: str = "",
    contact_first_name: str = "",
    contact_last_name: str = "",
    auto_delete_after_sec: int = 0,
    remove_muted_accounts: bool = False,
    on_remove_account: Callable[[str], Awaitable[None]] | None = None,
    guest_mode: bool = False,
    schedule_start_at: str = "",
    schedule_end_at: str = "",
    skip_keys: set[str] | None = None,
    initial_success: int = 0,
    initial_failed: int = 0,
    on_job_done: Callable[[str, str], None] | None = None,
) -> None:
    pause = pause_event or asyncio.Event()
    if not pause_event:
        pause.set()

    success = max(0, int(initial_success))
    failed = max(0, int(initial_failed))
    lock = asyncio.Lock()
    processed_since_rest = 0
    active_ids = list(account_ids)
    removed_ids: set[str] = set()
    effective_auto_join = False if (guest_mode or use_joined_groups) else auto_join
    gate = AccountIntervalGate(interval_min, interval_max)

    for account_id in account_ids:
        set_broadcast_status(account_id, "running")

    if await wait_for_schedule_start(schedule_start_at, should_stop, on_log):
        return

    async def drop_muted_account(account_id: str, reason: str) -> None:
        async with lock:
            if account_id in removed_ids:
                return
            removed_ids.add(account_id)
            if account_id in active_ids:
                active_ids.remove(account_id)
        set_broadcast_status(account_id, "muted")
        on_log("warn", f"[{account_id}] 已从群发池剔除（{reason}）")
        if remove_muted_accounts and on_remove_account:
            try:
                await on_remove_account(account_id)
                on_log("info", f"[{account_id}] 已删除禁言账号会话")
            except Exception as exc:
                on_log("error", f"[{account_id}] 删除禁言账号失败: {exc}")

    async def process_one(account_id: str, target: str) -> None:
        nonlocal success, failed, processed_since_rest
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

        async with lock:
            if account_id in removed_ids or account_id not in active_ids:
                failed += 1
                on_progress(success + failed, success, failed)
                on_log("warn", f"[{account_id}] 已从群发池剔除，跳过: {target}")
                return
            if not active_ids:
                on_log("error", "无可用账号，停止发送")
                return

        acc_lock = await gate.lock_for(account_id)
        async with acc_lock:
            if await gate.wait_turn(account_id, should_stop, on_log):
                return
            custom_ad = get_account_ad(account_id)
            effective_message = custom_ad or message
            if custom_ad:
                on_log("info", f"[{account_id}] 使用独立广告语")
            armed = False
            try:
                on_log("info", f"[{account_id}] 正在发送: {target}")
                client = await get_client(account_id)
                await send_broadcast_message(
                    client,
                    target,
                    effective_message,
                    parse_mode,
                    effective_auto_join,
                    use_rich_tags,
                    use_postbot,
                    postbot_code,
                    send_mode,
                    media_path,
                    forward_channel,
                    forward_message_id,
                    forward_message_links,
                    forward_hide_source,
                    multi_line_mode,
                    random_prefix_len,
                    random_suffix_len,
                    no_duplicate_join,
                    combined_send,
                    contact_target,
                    contact_first_name,
                    contact_last_name,
                    auto_delete_after_sec,
                )
                async with lock:
                    success += 1
                    processed_since_rest += 1
                increment_broadcast_success(account_id, 1)
                on_log("success", f"[{account_id}] 发送成功: {target}")
            except PeerIdInvalidError:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                on_log("error", f"[{account_id}] Peer ID 无效，跳过: {target}")
            except PeerFloodError:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                on_log(
                    "warn",
                    f"[{account_id}] 双向限制/防刷（仅本目标失败，账号继续）: {target}",
                )
                if auto_spambot_unban:
                    try:
                        client = await get_client(account_id)
                        result = await try_spambot_unban(client)
                        on_log("warn", f"[{account_id}] {result}")
                    except Exception as exc:
                        on_log("error", f"[{account_id}] SpamBot 处理失败: {exc}")
                armed = True
            except FloodWaitError as exc:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                on_log("warn", f"[{account_id}] 频繁限制 {exc.seconds}s，其它号继续: {target}")
                gate.block_for(account_id, exc.seconds)
                armed = True
            except UserBannedInChannelError:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                on_log("error", f"[{account_id}] 账号被禁言: {target}")
                if auto_spambot_unban:
                    try:
                        client = await get_client(account_id)
                        result = await try_spambot_unban(client)
                        on_log("warn", f"[{account_id}] {result}")
                    except Exception as exc:
                        on_log("error", f"[{account_id}] SpamBot 处理失败: {exc}")
                await drop_muted_account(account_id, "群内禁言")
                armed = True
            except ChatWriteForbiddenError:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                on_log("error", f"[{account_id}] 无发言权限: {target}")
                if exit_muted_groups:
                    try:
                        client = await get_client(account_id)
                        entity = await resolve_entity(client, target)
                        await client(LeaveChannelRequest(entity))
                        on_log("info", f"[{account_id}] 已退出禁言群: {target}")
                    except Exception as exc:
                        on_log("warn", f"[{account_id}] 退群失败: {exc}")
                await drop_muted_account(account_id, "无发言权限")
                armed = True
            except Exception as exc:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                err = str(exc).lower()
                if "peer id" in err or "peeridinvalid" in err:
                    on_log("error", f"[{account_id}] Peer ID 异常，跳过: {target}")
                else:
                    on_log("error", f"[{account_id}] 发送失败 {target}: {exc}")

            async with lock:
                current = success + failed
                on_progress(current, success, failed)
            if on_job_done:
                on_job_done(account_id, target)

            if (
                round_rest_max > 0
                and processed_since_rest >= max(1, len(active_ids) or 1)
                and not should_stop()
            ):
                rest = random.randint(max(1, round_rest_min), round_rest_max)
                on_log("info", f"本轮完成，休息 {rest} 秒...")
                await asyncio.sleep(rest)
                processed_since_rest = 0

            if not armed:
                gate.arm(account_id)

    discovered_total = success + failed

    async def run_joined_account(account_id: str) -> None:
        nonlocal discovered_total
        if should_stop():
            return
        try:
            client = await get_client(account_id)
        except Exception as exc:
            on_log("error", f"[{account_id}] 连接失败: {exc}")
            return
        on_log("info", f"[{account_id}] 已就绪，边扫群边发送")
        sent_any = False

        async def send_target(target: str) -> None:
            nonlocal discovered_total, sent_any
            if skip_keys and account_target_key(account_id, target) in skip_keys:
                return
            async with lock:
                discovered_total += 1
                if on_set_total:
                    on_set_total(discovered_total)
            if not sent_any:
                on_log("info", f"[{account_id}] 立即开始发送: {target}")
                sent_any = True
            await process_one(account_id, target)

        try:
            if random_order:
                acc_targets = await list_joined_group_targets(client)
                random.shuffle(acc_targets)
                on_log("info", f"[{account_id}] 已加入群组 {len(acc_targets)} 个")
                for target in acc_targets:
                    if should_stop():
                        return
                    await send_target(target)
            else:
                async for target in iter_joined_group_targets(client):
                    if should_stop():
                        return
                    await send_target(target)
        except Exception as exc:
            on_log("error", f"[{account_id}] 读取已加入群组失败: {exc}")
            return
        if not sent_any:
            on_log("warn", f"[{account_id}] 没有可发送的已加入群组")

    if use_joined_groups:
        on_log("info", f"各账号并行启动：连上即发，首次发送不等间隔（{len(account_ids)} 个账号）")
        await asyncio.gather(*[run_joined_account(account_id) for account_id in account_ids])
        if discovered_total <= success + failed and success + failed == 0:
            on_log("warn", "所选账号没有可发送的已加入群组")
    else:
        work_targets = list(targets)
        if random_order:
            random.shuffle(work_targets)
        jobs = [(aid, target) for aid in account_ids for target in work_targets]
        if skip_keys:
            kept: list[tuple[str, str]] = []
            skipped = 0
            for aid, target in jobs:
                if account_target_key(aid, target) in skip_keys:
                    skipped += 1
                else:
                    kept.append((aid, target))
            jobs = kept
            if skipped:
                on_log("info", f"从暂停处继续，已跳过 {skipped} 项，按最新配置发送剩余 {len(jobs)} 项")
        on_log(
            "info",
            f"各账号并行群发：{len(account_ids)} 个账号 × {len(work_targets)} 个目标，首次立即发送",
        )
        if on_set_total:
            on_set_total(success + failed + len(jobs))
        on_progress(success + failed, success, failed)
        await run_per_account_jobs(jobs, process_one, should_stop)

    for account_id in account_ids:
        set_broadcast_status(account_id, "idle")
