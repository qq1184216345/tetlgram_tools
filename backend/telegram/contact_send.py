from __future__ import annotations

import re

from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputMediaContact, InputPhoneContact

from backend.telegram.utils import resolve_entity


async def resolve_contact_user(client: TelegramClient, target: str):
    raw = target.strip()
    if not raw:
        raise ValueError("联系人目标为空")

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
                        first_name="Contact",
                        last_name="",
                    )
                ]
            )
        )
        if result.users:
            return result.users[0]
        raise ValueError(f"无法通过手机号找到联系人: {phone}")

    if re.match(r"^\d+$", raw):
        return await client.get_entity(int(raw))

    return await resolve_entity(client, raw)


async def send_contact_card(
    client: TelegramClient,
    entity,
    contact_target: str,
    first_name: str = "",
    last_name: str = "",
) -> None:
    user = await resolve_contact_user(client, contact_target)
    phone = getattr(user, "phone", None) or ""
    if not phone:
        raise ValueError("目标用户无公开手机号，无法发送名片")

    display_first = first_name.strip() or getattr(user, "first_name", None) or "Contact"
    display_last = last_name.strip() or getattr(user, "last_name", None) or ""

    await client.send_file(
        entity,
        InputMediaContact(
            phone_number=phone if phone.startswith("+") else f"+{phone}",
            first_name=display_first,
            last_name=display_last,
            vcard="",
        ),
    )
