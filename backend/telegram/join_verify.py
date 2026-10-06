from __future__ import annotations

import asyncio
import re
from typing import Callable

from telethon import TelegramClient, events
from telethon.tl.custom import Button

from backend.config import settings
from backend.telegram.ai_verify import ask_ai_for_verification
from backend.telegram.utils import resolve_entity

MATH_PATTERN = re.compile(
    r"(\d+)\s*([+\-×xX*÷/])\s*(\d+)\s*=\s*\??",
)


def _calc(a: int, op: str, b: int) -> int | None:
    if op in ("+",):
        return a + b
    if op in ("-",):
        return a - b
    if op in ("*", "×", "x", "X"):
        return a * b
    if op in ("/", "÷") and b != 0:
        return a // b
    return None


async def try_pass_join_verification(
    client: TelegramClient,
    target: str,
    timeout: float = 15.0,
    on_log: Callable[[str, str], None] | None = None,
    use_ai: bool = True,
) -> bool:
    """尝试自动处理加群验证：算数 / 按钮 / AI 中转站。"""
    try:
        entity = await resolve_entity(client, target)
    except Exception:
        return False

    solved = False
    pending_ai: list = []

    @client.on(events.NewMessage(chats=entity))
    async def handler(event):  # type: ignore[no-untyped-def]
        nonlocal solved
        if solved:
            return
        text = event.raw_text or ""
        match = MATH_PATTERN.search(text)
        if match:
            a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
            answer = _calc(a, op, b)
            if answer is not None:
                try:
                    await event.reply(str(answer))
                    solved = True
                    if on_log:
                        on_log("info", f"已回答算数验证: {a}{op}{b}={answer}")
                except Exception:
                    pass
                return

        buttons = await event.get_buttons()
        button_labels: list[str] = []
        if buttons:
            for row in buttons:
                for button in row:
                    label = getattr(button, "text", None) or ""
                    if label:
                        button_labels.append(label)
                    lower = label.lower()
                    if any(
                        kw in lower
                        for kw in (
                            "verify",
                            "confirm",
                            "i am",
                            "human",
                            "通过",
                            "验证",
                            "我是",
                            "确认",
                            "点击",
                            "press",
                            "tap",
                        )
                    ):
                        try:
                            await event.click(text=button.text)
                            solved = True
                            if on_log:
                                on_log("info", f"已点击验证按钮: {button.text}")
                            return
                        except Exception:
                            try:
                                if isinstance(button, Button) or hasattr(button, "data"):
                                    await event.click(data=button.data)
                                    solved = True
                                    return
                            except Exception:
                                pass

        # 复杂验证：交给 AI
        if use_ai and (getattr(settings, "ai_api_url", "") or "").strip():
            pending_ai.append((event, text, button_labels))

    try:
        await asyncio.sleep(timeout)
        if not solved and pending_ai:
            event, text, button_labels = pending_ai[-1]
            if on_log:
                on_log("info", "规则未命中，正在请求 AI 中转站...")
            result = await ask_ai_for_verification(text, button_labels)
            if result.get("error"):
                if on_log:
                    on_log("warn", f"AI 验证失败: {result['error']}")
            elif result.get("action") == "reply" and result.get("text"):
                await event.reply(result["text"])
                solved = True
                if on_log:
                    on_log("success", f"AI 已回复验证: {result['text']}")
            elif result.get("action") == "click" and result.get("button"):
                try:
                    await event.click(text=result["button"])
                    solved = True
                    if on_log:
                        on_log("success", f"AI 已点击按钮: {result['button']}")
                except Exception as exc:
                    if on_log:
                        on_log("warn", f"AI 点击按钮失败: {exc}")
    finally:
        client.remove_event_handler(handler)

    return solved
