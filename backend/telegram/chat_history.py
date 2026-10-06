from __future__ import annotations

from telethon import TelegramClient

from backend.telegram.dm import resolve_user
from backend.telegram.utils import resolve_entity


async def fetch_chat_history(
    client: TelegramClient,
    target: str,
    limit: int = 50,
) -> list[dict]:
    try:
        entity = await resolve_entity(client, target)
    except Exception:
        entity = await resolve_user(client, target)

    messages: list[dict] = []
    async for message in client.iter_messages(entity, limit=limit):
        sender = await message.get_sender()
        sender_name = ""
        if sender:
            sender_name = getattr(sender, "username", "") or getattr(sender, "first_name", "") or str(
                getattr(sender, "id", "")
            )
        messages.append(
            {
                "id": message.id,
                "date": message.date.isoformat() if message.date else "",
                "sender": sender_name,
                "text": message.text or "",
                "out": bool(message.out),
            }
        )
    return list(reversed(messages))
