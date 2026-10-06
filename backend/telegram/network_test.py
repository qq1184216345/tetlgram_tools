from __future__ import annotations

from telethon import TelegramClient
from telethon.sessions import MemorySession
from telethon.tl.functions.help import GetConfigRequest

from backend.telegram.api_presets import API_PRESETS
from backend.config import settings
from backend.telegram.device_profiles import client_device_kwargs
from backend.telegram.proxy import format_proxy, resolve_proxy


async def test_telegram_connection(
    proxy_state: bool | None = None,
    use_system_proxy: bool | None = None,
    proxy_type: str | None = None,
    proxy_list: str | None = None,
) -> str:
    api_id = settings.api_id or int(API_PRESETS["telegram_desktop"]["api_id"])
    api_hash = settings.api_hash or str(API_PRESETS["telegram_desktop"]["api_hash"])

    proxy = resolve_proxy(proxy_state, use_system_proxy, proxy_type, proxy_list)
    used = format_proxy(proxy)
    client = TelegramClient(
        MemorySession(),
        api_id,
        api_hash,
        proxy=proxy,
        connection_retries=1,
        timeout=12,
        **client_device_kwargs(),
    )
    try:
        await client.connect()
        if not client.is_connected():
            raise RuntimeError("未能建立 TCP 连接")
        await client(GetConfigRequest())
        if proxy:
            return f"网络连接正常，已通过 {used} 连上 Telegram"
        return "网络连接正常（当前为直连，未走代理）"
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        if proxy:
            raise RuntimeError(
                f"走代理 {used} 连不上 Telegram：{detail}。"
                "请确认代理软件已开启，系统代理一般是 HTTP（Clash 多为 7890，v2rayN 多为 10809），"
                "不要用 SOCKS5 去连 HTTP 端口。"
            ) from exc
        raise RuntimeError(
            f"直连 Telegram 失败：{detail}。"
            "本机浏览器能上网不等于软件能连 TG。请勾选「自动检测系统代理」或填 127.0.0.1:7890（HTTP）后保存再测。"
        ) from exc
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
