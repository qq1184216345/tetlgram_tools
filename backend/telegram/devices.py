from __future__ import annotations

from telethon import TelegramClient
from telethon.tl.functions.account import (
    GetAuthorizationsRequest,
    ResetAuthorizationRequest,
    SetPrivacyRequest,
)
from telethon.tl.types import (
    InputPrivacyKeyChatInvite,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyKeyProfilePhoto,
    InputPrivacyKeyStatusTimestamp,
    InputPrivacyValueAllowAll,
    InputPrivacyValueDisallowAll,
)


async def list_authorizations(client: TelegramClient) -> list[dict]:
    result = await client(GetAuthorizationsRequest())
    devices: list[dict] = []
    for auth in result.authorizations:
        devices.append(
            {
                "hash": auth.hash,
                "device_model": auth.device_model or "",
                "platform": auth.platform or "",
                "system_version": auth.system_version or "",
                "app_name": auth.app_name or "",
                "app_version": auth.app_version or "",
                "country": auth.country or "",
                "ip": auth.ip or "",
                "date_active": getattr(auth, "date_active", None).isoformat()
                if getattr(auth, "date_active", None)
                else "",
                "current": bool(getattr(auth, "current", False)),
            }
        )
    return devices


async def kick_other_sessions(client: TelegramClient) -> int:
    result = await client(GetAuthorizationsRequest())
    kicked = 0
    for auth in result.authorizations:
        if getattr(auth, "current", False):
            continue
        try:
            await client(ResetAuthorizationRequest(hash=auth.hash))
            kicked += 1
        except Exception:
            pass
    return kicked


async def kick_sessions_by_hashes(client: TelegramClient, hashes: list[int]) -> int:
    """按 hash 踢指定会话；自动跳过当前设备。"""
    if not hashes:
        return await kick_other_sessions(client)
    result = await client(GetAuthorizationsRequest())
    current_hashes = {
        int(auth.hash)
        for auth in result.authorizations
        if getattr(auth, "current", False)
    }
    kicked = 0
    for raw in hashes:
        h = int(raw)
        if h in current_hashes or h == 0:
            continue
        try:
            await client(ResetAuthorizationRequest(hash=h))
            kicked += 1
        except Exception:
            pass
    return kicked


PRIVACY_KEYS = {
    "phone": InputPrivacyKeyPhoneNumber,
    "last_seen": InputPrivacyKeyStatusTimestamp,
    "profile_photo": InputPrivacyKeyProfilePhoto,
    "invite": InputPrivacyKeyChatInvite,
}


async def set_privacy_batch(
    client: TelegramClient,
    rules: dict[str, str],
) -> list[str]:
    """rules: key -> allow_all | disallow_all"""
    applied: list[str] = []
    for key, mode in rules.items():
        key_cls = PRIVACY_KEYS.get(key)
        if not key_cls:
            continue
        value = InputPrivacyValueAllowAll() if mode == "allow_all" else InputPrivacyValueDisallowAll()
        await client(SetPrivacyRequest(key=key_cls(), rules=[value]))
        applied.append(key)
    return applied
