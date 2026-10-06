from __future__ import annotations

import asyncio
import itertools
import os
import socket
import sys
import threading
from typing import Optional
from urllib.parse import unquote, urlparse
from urllib.request import getproxies

from backend.config import settings

_PROXY_COUNTER = itertools.count()
_PROXY_LOCK = threading.Lock()

_COMMON_HTTP_PORTS = (7890, 7897, 9191, 20171, 7892, 33210)
_COMMON_SOCKS_PORTS = (10808, 1080, 10809, 7891, 2080, 10900)


def _parse_host_port(host: str, port: str) -> tuple[str, int]:
    return host.strip(), int(port.strip())


def _ensure_proxy_url(value: str, default_scheme: str = "http") -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" in raw:
        return raw
    return f"{default_scheme}://{raw}"


def parse_proxy_line(line: str, proxy_type: str = "socks5") -> Optional[tuple]:
    raw = line.strip()
    if not raw:
        return None

    effective_type = proxy_type

    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.hostname or ""
        port = parsed.port or 0
        if not host or not port:
            return None
        scheme = (parsed.scheme or "").lower()
        if scheme in ("http", "https"):
            effective_type = "http"
        elif scheme in ("socks5", "socks"):
            effective_type = "socks5"
        elif scheme == "socks4":
            effective_type = "socks4"
        if parsed.username and parsed.password:
            return (
                effective_type,
                host,
                port,
                True,
                unquote(parsed.username),
                unquote(parsed.password),
            )
        return (effective_type, host, port)

    parts = raw.split(":")
    try:
        if len(parts) == 2:
            host, port = _parse_host_port(parts[0], parts[1])
            return (effective_type, host, port)
        if len(parts) == 4:
            host, port = _parse_host_port(parts[0], parts[1])
            return (effective_type, host, port, True, parts[2], parts[3])
    except ValueError:
        return None
    return None


def _tcp_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _env_proxy() -> Optional[str]:
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return _ensure_proxy_url(value, "http")
    return None


def _windows_inet_proxy() -> Optional[str]:
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
    except OSError:
        return None

    try:
        enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
    except OSError:
        enable = 0
    if not enable:
        return None

    try:
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except OSError:
        return None
    return _parse_windows_proxy_server(str(server or ""))


def _parse_windows_proxy_server(server: str) -> Optional[str]:
    raw = (server or "").strip()
    if not raw:
        return None
    if "=" in raw:
        mapped: dict[str, str] = {}
        for item in raw.split(";"):
            if "=" not in item:
                continue
            kind, value = item.split("=", 1)
            mapped[kind.strip().lower()] = value.strip()
        if mapped.get("https"):
            return _ensure_proxy_url(mapped["https"], "http")
        if mapped.get("http"):
            return _ensure_proxy_url(mapped["http"], "http")
        if mapped.get("socks"):
            return _ensure_proxy_url(mapped["socks"], "socks5")
        return None
    return _ensure_proxy_url(raw, "http")


def probe_local_proxy() -> Optional[str]:
    for port in _COMMON_HTTP_PORTS:
        if _tcp_open("127.0.0.1", port):
            return f"http://127.0.0.1:{port}"
    for port in _COMMON_SOCKS_PORTS:
        if _tcp_open("127.0.0.1", port):
            return f"socks5://127.0.0.1:{port}"
    return None


def detect_system_proxy() -> Optional[str]:
    found = _env_proxy()
    if found:
        return found

    proxies = getproxies()
    for key in ("https", "http", "all"):
        value = (proxies.get(key) or "").strip()
        if value:
            return _ensure_proxy_url(value, "http")

    found = _windows_inet_proxy()
    if found:
        return found

    return probe_local_proxy()


def format_proxy(proxy: Optional[tuple]) -> str:
    if not proxy:
        return "直连"
    kind, host, port = proxy[0], proxy[1], proxy[2]
    return f"{kind}://{host}:{port}"


def _parse_lines(text: str, proxy_type: str) -> list[tuple]:
    result: list[tuple] = []
    for line in (text or "").splitlines():
        parsed = parse_proxy_line(line, proxy_type)
        if parsed:
            result.append(parsed)
    return result


def resolve_proxy(
    proxy_state: bool | None = None,
    use_system_proxy: bool | None = None,
    proxy_type: str | None = None,
    proxy_list: str | None = None,
) -> Optional[tuple]:
    state = settings.proxy_state if proxy_state is None else proxy_state
    use_system = (
        getattr(settings, "use_system_proxy", False)
        if use_system_proxy is None
        else use_system_proxy
    )
    kind = (proxy_type if proxy_type is not None else getattr(settings, "proxy_type", "socks5")) or "socks5"
    text = proxy_list if proxy_list is not None else getattr(settings, "proxy_list", "") or ""
    manual = _parse_lines(text, kind)

    if not state and not use_system:
        return None

    if use_system:
        system_proxy = detect_system_proxy()
        if system_proxy:
            parsed = parse_proxy_line(system_proxy, "http")
            if parsed:
                return parsed
        if manual:
            return manual[0]
        return None

    if state:
        if manual:
            return manual[0]
        if settings.socks5_ip and settings.socks5_port:
            return parse_proxy_line(f"{settings.socks5_ip}:{settings.socks5_port}", kind)
    return None


def build_proxy_list() -> list[tuple]:
    proxy = resolve_proxy()
    if not proxy:
        return []

    extras: list[tuple] = []
    state = settings.proxy_state
    use_system = getattr(settings, "use_system_proxy", False)
    kind = getattr(settings, "proxy_type", "socks5") or "socks5"
    text = getattr(settings, "proxy_list", "") or ""
    manual = _parse_lines(text, kind)

    if use_system:
        extras.append(proxy)
        if state:
            extras.extend(item for item in manual if item != proxy)
        return extras or [proxy]

    return manual or ([proxy] if proxy else [])


def get_next_proxy() -> Optional[tuple]:
    proxies = build_proxy_list()
    if not proxies:
        return None
    with _PROXY_LOCK:
        index = next(_PROXY_COUNTER) % len(proxies)
    return proxies[index]


def get_proxy_for_account(account_id: str) -> Optional[tuple]:
    proxies = build_proxy_list()
    if not proxies:
        return None
    if len(proxies) == 1:
        return proxies[0]
    index = sum(ord(c) for c in account_id) % len(proxies)
    return proxies[index]


async def _probe_one(line: str, proxy_type: str) -> dict:
    parsed = parse_proxy_line(line, proxy_type)
    if not parsed:
        return {"line": line, "ok": False, "detail": "格式无法识别"}
    kind, host, port = parsed[0], parsed[1], int(parsed[2])
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=2.5,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {"line": line, "ok": True, "detail": f"{kind} 端口可达"}
    except Exception as exc:
        winerror = getattr(exc, "winerror", None)
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            detail = "连接超时"
        elif isinstance(exc, ConnectionRefusedError) or winerror == 1225:
            detail = "端口拒绝连接"
        elif isinstance(exc, OSError) and getattr(exc, "errno", None) in {8, 11001}:
            detail = "地址无法解析"
        else:
            detail = str(exc).strip() or exc.__class__.__name__
        return {"line": line, "ok": False, "detail": detail[:120]}


async def probe_proxy_list(text: str, proxy_type: str = "socks5", limit: int = 300) -> dict:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    truncated = len(lines) > limit
    lines = lines[:limit]
    if not lines:
        return {"total": 0, "alive": 0, "dead": 0, "truncated": False, "items": []}

    sem = asyncio.Semaphore(40)

    async def guarded(line: str) -> dict:
        async with sem:
            return await _probe_one(line, proxy_type)

    items = await asyncio.gather(*(guarded(line) for line in lines))
    alive = sum(1 for item in items if item["ok"])
    return {
        "total": len(items),
        "alive": alive,
        "dead": len(items) - alive,
        "truncated": truncated,
        "items": list(items),
    }
