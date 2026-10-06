from __future__ import annotations

import os
import secrets

from telethon import TelegramClient
from telethon.tl.functions.phone import RequestCallRequest
from telethon.tl.types import PhoneCallProtocol

from backend.telegram.dm import resolve_user


async def start_voice_call(client: TelegramClient, target: str) -> str:
    """
    向目标发起语音通话信令（实验功能）。

    说明：完整语音通话需要 libtgvoip 级别的密钥交换与媒体通道，
    Telethon 侧仅能发出 RequestCall；多数情况下对方不会真正接通。
    """
    user = await resolve_user(client, target)
    protocol = PhoneCallProtocol(
        min_layer=65,
        max_layer=92,
        udp_p2p=True,
        udp_reflector=True,
        library_versions=["2.4.4", "2.7.7", "3.0.0"],
    )
    random_id = int.from_bytes(os.urandom(4), "big") % 2_000_000_000 or 1
    result = await client(
        RequestCallRequest(
            user_id=user,
            random_id=random_id,
            g_a_hash=secrets.token_bytes(32),
            protocol=protocol,
        )
    )
    call_id = getattr(getattr(result, "phone_call", None), "id", None)
    suffix = f"（call_id={call_id}）" if call_id else ""
    return (
        f"已向 {target} 发送通话请求{suffix}。"
        "【实验】多数情况不会真正响铃接通，请用官方 App 通话。"
    )
