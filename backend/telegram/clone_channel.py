from __future__ import annotations

import asyncio
import re
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.account import UpdatePersonalChannelRequest
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditPhotoRequest,
)
from telethon.tl.types import InputChannel, InputChatUploadedPhoto

from backend.telegram.utils import resolve_entity

POST_LINK = re.compile(
    r"(?:https?://)?t\.me/([A-Za-z0-9_]+)/(\d+)",
    re.I,
)


def parse_post_link(link: str) -> tuple[str, int] | None:
    match = POST_LINK.search(link.strip())
    if not match:
        return None
    return match.group(1), int(match.group(2))


async def clone_channel(
    client: TelegramClient,
    source: str,
    title: str = "",
    about: str = "",
    message_limit: int = 50,
    bind_to_profile: bool = True,
    on_log: Callable[[str, str], None] | None = None,
) -> dict:
    """克隆指定频道部分帖子到新频道，并可绑定到个人主页。"""
    source_entity = await resolve_entity(client, source)
    src_title = title or (getattr(source_entity, "title", "") or "克隆频道")
    src_about = about or (getattr(source_entity, "about", "") or "")

    created = await client(
        CreateChannelRequest(
            title=src_title[:128],
            about=src_about[:255],
            megagroup=False,
            broadcast=True,
        )
    )
    new_channel = created.chats[0]
    if on_log:
        on_log("success", f"已创建频道: {new_channel.title} ({new_channel.id})")

    # 复制头像（若可取）
    try:
        photo = await client.download_profile_photo(source_entity, file=bytes)
        if photo:
            uploaded = await client.upload_file(photo)
            await client(
                EditPhotoRequest(
                    channel=InputChannel(new_channel.id, new_channel.access_hash),
                    photo=InputChatUploadedPhoto(file=uploaded),
                )
            )
    except Exception:
        pass

    copied = 0
    messages = []
    async for msg in client.iter_messages(source_entity, limit=max(1, message_limit)):
        messages.append(msg)
    for msg in reversed(messages):
        try:
            await client.forward_messages(new_channel, msg)
            copied += 1
            await asyncio.sleep(0.4)
        except FloodWaitError as exc:
            await asyncio.sleep(exc.seconds)
        except Exception:
            try:
                if msg.message:
                    await client.send_message(new_channel, msg.message)
                    copied += 1
            except Exception:
                pass

    bound = False
    if bind_to_profile:
        try:
            await client(
                UpdatePersonalChannelRequest(
                    channel=InputChannel(new_channel.id, new_channel.access_hash)
                )
            )
            bound = True
            if on_log:
                on_log("success", "已将频道绑定到个人主页")
        except Exception as exc:
            if on_log:
                on_log("warn", f"绑定主页失败: {exc}")

    username = getattr(new_channel, "username", "") or ""
    return {
        "channel_id": new_channel.id,
        "title": new_channel.title,
        "username": username,
        "copied": copied,
        "bound": bound,
        "link": f"https://t.me/{username}" if username else f"channel:{new_channel.id}",
    }


async def run_clone_channel_loop(
    account_ids: list[str],
    source: str,
    title: str,
    about: str,
    message_limit: int,
    bind_to_profile: bool,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
) -> None:
    success = 0
    failed = 0
    for index, account_id in enumerate(account_ids):
        if should_stop():
            break
        try:
            client = await get_client(account_id)
            result = await clone_channel(
                client,
                source,
                title=title,
                about=about,
                message_limit=message_limit,
                bind_to_profile=bind_to_profile,
                on_log=on_log,
            )
            success += 1
            on_log(
                "success",
                f"[{account_id}] 克隆完成: {result.get('title')} "
                f"复制 {result.get('copied')} 条，绑定={result.get('bound')}",
            )
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 克隆失败: {exc}")
        on_progress(index + 1, success, failed)
