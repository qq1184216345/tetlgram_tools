from __future__ import annotations

import re

from telethon import TelegramClient
from telethon.errors import InviteHashExpiredError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import ChatInviteAlready


INVITE_PATTERNS = [
    re.compile(r"(?:https?://)?t\.me/\+([A-Za-z0-9_-]+)"),
    re.compile(r"(?:https?://)?t\.me/joinchat/([A-Za-z0-9_-]+)"),
]


PEER_ID_RE = re.compile(r"^-?\d+$")


def is_peer_id_target(raw: str) -> bool:
    return bool(PEER_ID_RE.fullmatch(raw.strip()))


def normalize_target(raw: str) -> str:
    target = raw.strip()
    if not target:
        return ""
    if is_peer_id_target(target):
        return target
    if target.startswith("https://t.me/") or target.startswith("http://t.me/"):
        return target
    if target.startswith("t.me/"):
        return f"https://{target}"
    if target.startswith("@"):
        return target
    if target.startswith("+"):
        return f"https://t.me/{target}"
    return f"https://t.me/{target.lstrip('/')}"


def extract_invite_hash(target: str) -> str | None:
    for pattern in INVITE_PATTERNS:
        match = pattern.search(target)
        if match:
            return match.group(1)
    return None


async def _resolve_invite_chat(client: TelegramClient, invite_hash: str):
    """解析私有邀请链接对应群实体（已加入时用 CheckChatInvite）。"""
    try:
        updates = await client(ImportChatInviteRequest(invite_hash))
        chats = getattr(updates, "chats", None) or []
        if chats:
            return chats[0]
    except UserAlreadyParticipantError:
        pass
    except InviteHashExpiredError as exc:
        raise ValueError("邀请链接已过期") from exc

    try:
        invite_info = await client(CheckChatInviteRequest(invite_hash))
    except InviteHashExpiredError as exc:
        raise ValueError("邀请链接已过期") from exc
    except Exception as exc:
        raise ValueError("无法解析邀请链接，请确认仍有效且账号已入群") from exc

    if isinstance(invite_info, ChatInviteAlready):
        chat = invite_info.chat
        try:
            return await client.get_entity(chat)
        except Exception:
            return chat

    raise ValueError("尚未加入该群，请先加群后再发送")


async def collect_joined_usernames_and_titles(client: TelegramClient) -> tuple[set[str], set[str]]:
    usernames: set[str] = set()
    titles: set[str] = set()
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        uname = (getattr(entity, "username", "") or "").lower()
        if uname:
            usernames.add(uname)
        title = (getattr(entity, "title", "") or "").lower()
        if title:
            titles.add(title)
    return usernames, titles


def public_target_key(target: str) -> str:
    normalized = normalize_target(target)
    return normalized.rsplit("/", 1)[-1].lstrip("@").lower()


async def is_already_joined(client: TelegramClient, target: str) -> bool:
    normalized = normalize_target(target)
    invite_hash = extract_invite_hash(normalized)
    if invite_hash:
        try:
            invite_info = await client(CheckChatInviteRequest(invite_hash))
            return isinstance(invite_info, ChatInviteAlready)
        except Exception:
            return False

    username = public_target_key(target)
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        entity_username = (getattr(entity, "username", "") or "").lower()
        if entity_username and entity_username == username.lstrip("@"):
            return True
        title = (getattr(entity, "title", "") or "").lower()
        if title and title == username:
            return True
    return False


def is_joined_in_lookup(
    target: str,
    usernames: set[str],
    titles: set[str],
) -> bool | None:
    """公开群用会话缓存判断；邀请链返回 None，需再调 is_already_joined。"""
    if extract_invite_hash(normalize_target(target)):
        return None
    key = public_target_key(target)
    return key in usernames or key in titles


async def join_target(client: TelegramClient, target: str, request_join: bool = False) -> None:
    normalized = normalize_target(target)
    invite_hash = extract_invite_hash(normalized)
    if invite_hash:
        try:
            await client(ImportChatInviteRequest(invite_hash))
        except UserAlreadyParticipantError:
            return
        except InviteHashExpiredError as exc:
            raise ValueError("邀请链接已过期") from exc
        return

    username = normalized.rsplit("/", 1)[-1].lstrip("@")
    entity = await client.get_entity(username)
    try:
        await client(JoinChannelRequest(entity))
    except UserAlreadyParticipantError:
        return


async def resolve_entity(client: TelegramClient, target: str):
    raw = target.strip()
    if is_peer_id_target(raw):
        return await client.get_entity(int(raw))

    normalized = normalize_target(raw)
    invite_hash = extract_invite_hash(normalized)
    if invite_hash:
        return await _resolve_invite_chat(client, invite_hash)

    username = normalized.rsplit("/", 1)[-1].lstrip("@")
    if username.startswith("+"):
        raise ValueError("无法解析群组，请先加入该群")
    return await client.get_entity(username)
