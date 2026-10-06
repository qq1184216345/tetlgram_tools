from __future__ import annotations

from telethon import TelegramClient


def _normalize_postbot_code(code: str) -> str:
    raw = code.strip()
    if raw.startswith("https://t.me/postbot"):
        return raw
    if raw.startswith("@postbot"):
        return raw.split(maxsplit=1)[-1] if " " in raw else raw
    return raw


async def send_postbot_message(
    client: TelegramClient,
    entity,
    code: str,
    fallback_text: str = "",
) -> None:
    payload = _normalize_postbot_code(code or fallback_text)
    if not payload:
        raise ValueError("PostBot 代码或消息内容不能为空")

    query_text = payload
    if payload.startswith("http"):
        if "start=" in payload:
            query_text = payload.rsplit("start=", 1)[-1]
        else:
            await client.send_message(entity, payload)
            return

    try:
        results = await client.inline_query("postbot", query_text)
        if results:
            await results[0].click(entity)
            return
    except Exception:
        pass

    if payload != query_text:
        try:
            results = await client.inline_query("postbot", payload)
            if results:
                await results[0].click(entity)
                return
        except Exception:
            pass

    await client.send_message(entity, code.strip() or payload)
