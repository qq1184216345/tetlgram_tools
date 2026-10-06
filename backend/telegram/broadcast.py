from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
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


def format_group_ref(target: str) -> str:
    raw = (target or "").strip()
    if not raw:
        return "未知群"
    if raw.startswith("@") or "t.me/" in raw.lower() or "telegram.me/" in raw.lower():
        return raw
    if raw.startswith("-") or raw.lstrip("-").isdigit():
        return f"群ID {raw}"
    return raw


async def describe_group(client: TelegramClient, target: str) -> str:
    ref = format_group_ref(target)
    try:
        entity = await resolve_entity(client, target)
        title = (getattr(entity, "title", None) or "").strip()
        if not title:
            title = " ".join(
                part
                for part in (
                    getattr(entity, "first_name", None),
                    getattr(entity, "last_name", None),
                )
                if part
            ).strip()
        username = getattr(entity, "username", None)
        handle = f"@{username}" if username else ref
        if title and handle and handle.lstrip("@") not in title.replace(" ", ""):
            return f"{title}（{handle}）"
        return title or handle
    except Exception:
        return ref


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
    skip_explained: set[str] = set()
    effective_auto_join = False if (guest_mode or use_joined_groups) else auto_join
    gate = AccountIntervalGate(interval_min, interval_max)

    for account_id in account_ids:
        set_broadcast_status(account_id, "running")

    if await wait_for_schedule_start(schedule_start_at, should_stop, on_log):
        return

    spambot_tried: set[str] = set()

    async def drop_restricted_account(account_id: str, why: str) -> None:
        async with lock:
            if account_id in removed_ids:
                return
            removed_ids.add(account_id)
            if account_id in active_ids:
                active_ids.remove(account_id)
        set_broadcast_status(account_id, "muted")
        on_log("warn", f"[{account_id}] {why}")
        if remove_muted_accounts and on_remove_account:
            try:
                await on_remove_account(account_id)
                on_log("info", f"[{account_id}] 已删除该受限账号的登录会话")
            except Exception as exc:
                on_log("error", f"[{account_id}] 删除受限账号失败: {exc}")

    async def maybe_spambot(account_id: str) -> None:
        if not auto_spambot_unban or account_id in spambot_tried:
            return
        spambot_tried.add(account_id)
        try:
            client = await get_client(account_id)
            result = await try_spambot_unban(client)
            on_log("warn", f"[{account_id}] {result}")
        except Exception as exc:
            on_log("error", f"[{account_id}] SpamBot 处理失败: {exc}")

    async def group_label(account_id: str, target: str) -> str:
        try:
            client = await get_client(account_id)
            return await describe_group(client, target)
        except Exception:
            return format_group_ref(target)

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
                first_skip = account_id not in skip_explained
                if first_skip:
                    skip_explained.add(account_id)
                    on_log(
                        "info",
                        f"[{account_id}] 本账号已因官方限制停发，排队中尚未发出的群会直接跳过，不再逐条列出",
                    )
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
                where = await group_label(account_id, target)
                on_log(
                    "warn",
                    f"[{account_id}] 【双向限制】官方防刷，只能给互为联系人发"
                    f"（不是群管理员禁言）。本条跳过，其它群继续: {where}",
                )
                await maybe_spambot(account_id)
                armed = True
            except FloodWaitError as exc:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                on_log(
                    "warn",
                    f"[{account_id}] 【频繁限制】操作过快，需等待 {exc.seconds} 秒，其它号继续: {target}",
                )
                gate.block_for(account_id, exc.seconds)
                armed = True
            except UserBannedInChannelError:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                where = await group_label(account_id, target)
                on_log(
                    "error",
                    f"[{account_id}] 【官方限制】该号被 Telegram 限制在超级群/频道发言"
                    f"（不是「{where}」管理员禁言）",
                )
                await maybe_spambot(account_id)
                await drop_restricted_account(
                    account_id,
                    "因官方限制，本任务已停用这个号群发，其它号继续",
                )
                armed = True
            except ChatWriteForbiddenError:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                where = await group_label(account_id, target)
                on_log(
                    "error",
                    f"[{account_id}] 【群内禁言】「{where}」管理员禁止发言或仅管理员可发。"
                    "已跳过该群，其它群继续",
                )
                if exit_muted_groups:
                    try:
                        client = await get_client(account_id)
                        entity = await resolve_entity(client, target)
                        await client(LeaveChannelRequest(entity))
                        on_log("info", f"[{account_id}] 已退出该群: {where}")
                    except Exception as exc:
                        on_log("warn", f"[{account_id}] 退出「{where}」失败: {exc}")
                armed = True
            except ChannelPrivateError:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                where = await group_label(account_id, target)
                on_log(
                    "error",
                    f"[{account_id}] 【无法访问】「{where}」已私密、被踢或未加入。"
                    "已跳过该群，其它群继续",
                )
            except Exception as exc:
                async with lock:
                    failed += 1
                    processed_since_rest += 1
                err = str(exc).lower()
                where = format_group_ref(target)
                if "userbannedinchannel" in err or "banned from sending messages in super" in err:
                    on_log(
                        "error",
                        f"[{account_id}] 【官方限制】该号被 Telegram 限制在超级群/频道发言"
                        f"（不是「{where}」管理员禁言）: {exc}",
                    )
                    await maybe_spambot(account_id)
                    await drop_restricted_account(
                        account_id,
                        "因官方限制，本任务已停用这个号群发，其它号继续",
                    )
                    armed = True
                elif "chatwriteforbidden" in err or "not allowed to write" in err:
                    on_log(
                        "error",
                        f"[{account_id}] 【群内禁言】「{where}」管理员禁止发言或仅管理员可发。"
                        "已跳过该群，其它群继续",
                    )
                elif "peerflood" in err:
                    on_log(
                        "warn",
                        f"[{account_id}] 【双向限制】官方防刷（不是群管理员禁言）。"
                        f"本条跳过，其它群继续: {where}",
                    )
                    armed = True
                elif "peer id" in err or "peeridinvalid" in err:
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
