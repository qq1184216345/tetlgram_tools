from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

from telethon import TelegramClient

LINK_PATTERN = re.compile(r"https?://t\.me/[A-Za-z0-9_+/=%-]+")


@dataclass
class SpamBotResult:
    status: str
    summary: str
    full_text: str = ""
    verify_links: list[str] = field(default_factory=list)
    limited: bool = False


def _summarize(text: str) -> tuple[str, str, bool]:
    lower = text.lower()
    # 无限制判断必须优先：原文常含 “Good news, no limits...”
    if any(
        kw in lower
        for kw in (
            "good news",
            "no limits",
            "no limit",
            "not limited",
            "没有限制",
            "未被限制",
            "не ограничен",
        )
    ):
        return "ok", "账号当前无限制（SpamBot 确认）", False
    if any(kw in lower for kw in ("frozen", "冻结", "deactivated", "banned", "封禁")):
        return "frozen", "账号可能被冻结或封禁", True
    if any(
        kw in lower
        for kw in ("limited until", "your account was limited", "restrict", "限制", "禁言", "ограничен")
    ):
        return "limited", "账号存在限制/禁言", True
    if text.strip():
        return "unknown", f"已获取 SpamBot 回复，请查看全文", False
    return "empty", "SpamBot 无有效回复", False


async def check_spambot_status(client: TelegramClient) -> SpamBotResult:
    """向 SpamBot 发送 /start，返回全文与验证链接。"""
    try:
        await client.send_message("SpamBot", "/start")
        await asyncio.sleep(2.5)

        texts: list[str] = []
        verify_links: list[str] = []
        async for message in client.iter_messages("SpamBot", limit=5):
            text = message.text or message.message or ""
            if text.strip():
                texts.append(text.strip())
                verify_links.extend(LINK_PATTERN.findall(text))
            if message.buttons:
                for row in message.buttons:
                    for button in row:
                        url = getattr(button, "url", None)
                        if url:
                            verify_links.append(str(url))

        full_text = "\n\n---\n\n".join(texts)
        unique_links = list(dict.fromkeys(verify_links))
        status, summary, limited = _summarize(full_text)
        if unique_links and limited:
            summary = f"{summary}；发现 {len(unique_links)} 个验证链接"
        return SpamBotResult(
            status=status,
            summary=summary,
            full_text=full_text,
            verify_links=unique_links,
            limited=limited,
        )
    except Exception as exc:
        return SpamBotResult(
            status="error",
            summary=f"SpamBot 检测失败: {exc}",
            full_text="",
            verify_links=[],
            limited=False,
        )


async def try_spambot_unban(client: TelegramClient) -> str:
    result = await check_spambot_status(client)
    if result.status == "ok":
        return (
            f"{result.summary}。"
            "若提示只能给双向联系人发消息，属账号限制而非整号刷爆；"
            "建议拉长间隔，并优先向已互为联系人的用户发送"
        )

    try:
        async for message in client.iter_messages("SpamBot", limit=3):
            if not message.buttons:
                continue
            for row in message.buttons:
                for button in row:
                    label = (button.text or "").lower()
                    if any(
                        kw in label
                        for kw in ("done", "ok", "yes", "好的", "确定", "提交", "this is me")
                    ):
                        await message.click(data=button.data)
                        await asyncio.sleep(2)
                        extra = ""
                        if result.verify_links:
                            extra = f"；验证链接: {', '.join(result.verify_links[:3])}"
                        return f"已向 SpamBot 提交解封请求{extra}"

        if result.verify_links:
            return (
                f"{result.summary}；请手动打开验证链接: "
                + ", ".join(result.verify_links[:5])
            )
        return result.summary or "已向 SpamBot 发送 /start，请查看账号状态"
    except Exception as exc:
        return f"SpamBot 解封失败: {exc}"
