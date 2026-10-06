from __future__ import annotations

import random
import re

from telethon import TelegramClient

from backend.telegram.utils import join_target, resolve_entity

CHANNEL_MSG_PATTERN = re.compile(
    r"(?:https?://)?t\.me/(?:c/(\d+)|([A-Za-z0-9_]+))/(\d+)"
)


def parse_channel_message_link(link: str) -> tuple[str, int]:
    match = CHANNEL_MSG_PATTERN.search(link.strip())
    if not match:
        raise ValueError("无效的频道消息链接，格式: t.me/channel/123 或 t.me/c/xxx/123")

    private_id, username, msg_id = match.groups()
    channel_ref = f"-100{private_id}" if private_id else username
    return channel_ref, int(msg_id)


def collect_forward_candidates(
    forward_channel: str,
    forward_message_id: int,
    forward_message_links: list[str] | None = None,
) -> list[tuple[str, int]]:
    candidates: list[tuple[str, int]] = []
    for link in forward_message_links or []:
        link = link.strip()
        if not link:
            continue
        candidates.append(parse_channel_message_link(link))

    if forward_message_id:
        channel_ref = forward_channel.strip()
        if not channel_ref:
            raise ValueError("请提供频道引用或消息链接")
        if CHANNEL_MSG_PATTERN.search(channel_ref):
            channel_ref, forward_message_id = parse_channel_message_link(channel_ref)
        candidates.append((channel_ref, forward_message_id))
    elif forward_channel.strip() and CHANNEL_MSG_PATTERN.search(forward_channel):
        candidates.append(parse_channel_message_link(forward_channel))

    if not candidates:
        raise ValueError("请提供至少一条频道消息链接或消息 ID")
    return candidates


def pick_forward_target(
    forward_channel: str,
    forward_message_id: int,
    forward_message_links: list[str] | None = None,
) -> tuple[str, int]:
    candidates = collect_forward_candidates(
        forward_channel, forward_message_id, forward_message_links
    )
    return random.choice(candidates)


async def forward_channel_message(
    client: TelegramClient,
    target: str,
    channel_ref: str,
    message_id: int,
    hide_source: bool,
    auto_join: bool,
) -> None:
    if auto_join:
        try:
            await join_target(client, target)
        except Exception:
            pass

    source = await resolve_entity(client, channel_ref)
    dest = await resolve_entity(client, target)

    await client.forward_messages(
        dest,
        message_id,
        source,
        drop_author=hide_source,
    )
