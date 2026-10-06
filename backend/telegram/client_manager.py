from __future__ import annotations

import asyncio
import base64
import io
import re
import shutil
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import qrcode
from telethon import TelegramClient
from telethon.errors import RPCError, SessionPasswordNeededError
from telethon.tl.functions.updates import GetStateRequest

from backend.config import IMPORT_ERROR_DIR, IMPORT_OK_DIR, SESSIONS_DIR, settings
from backend.models.schemas import AccountInfo, AccountStatus
from backend.storage.account_meta import enrich_account, get_proxy as get_account_proxy
from backend.storage.session_json import (
    apply_session_init,
    enrich_account_from_json,
    read_session_json,
    session_api_credentials,
    session_device_kwargs,
    session_string_from_meta,
)
from backend.telegram.api_presets import API_PRESETS
from backend.telegram.device_profiles import client_device_kwargs
from backend.telegram.proxy import get_next_proxy, get_proxy_for_account, parse_proxy_line


def _safe_phone_name(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return digits or "unknown"


def _make_client(session: str | Path, api_id: int, api_hash: str, **extra) -> TelegramClient:
    session_device = extra.pop("session_device", None) or {}
    kwargs = {
        "proxy": extra.pop("proxy", None),
        "use_ipv6": extra.pop("use_ipv6", False),
        "timeout": extra.pop("timeout", 15),
        "connection_retries": extra.pop("connection_retries", 2),
        "request_retries": extra.pop("request_retries", 3),
        **extra,
    }
    if session_device.get("device_model"):
        kwargs.update(session_device)
    else:
        kwargs.update({**client_device_kwargs(), **session_device})
    return TelegramClient(str(session), api_id, api_hash, **kwargs)


class QrLoginStatus(str, Enum):
    WAITING = "waiting"
    NEED_PASSWORD = "need_password"
    SUCCESS = "success"
    EXPIRED = "expired"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class PendingLogin:
    client: TelegramClient
    phone: str
    phone_code_hash: str = ""


@dataclass
class PendingQrLogin:
    client: TelegramClient
    qr_login: Any
    session_name: str
    status: QrLoginStatus = QrLoginStatus.WAITING
    error: str = ""
    account: Optional[AccountInfo] = None
    wait_task: Optional[asyncio.Task] = field(default=None, repr=False)


class ClientManager:
    def __init__(self) -> None:
        self._clients: Dict[str, TelegramClient] = {}
        self._pending: Dict[str, PendingLogin] = {}
        self._pending_qr: Dict[str, PendingQrLogin] = {}
        self._accounts: Dict[str, AccountInfo] = {}
        self._load_existing_sessions()

    def _make_qr_image(self, url: str) -> str:
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def _proxy(self, account_id: str | None = None) -> Optional[tuple]:
        if account_id:
            account_proxy = get_account_proxy(account_id)
            if account_proxy.strip():
                proxy_type = getattr(settings, "proxy_type", "socks5") or "socks5"
                parsed = parse_proxy_line(account_proxy, proxy_type)
                if parsed:
                    return parsed
            return get_proxy_for_account(account_id)
        return get_next_proxy()

    def _api_credentials(self, api_id: Optional[int], api_hash: Optional[str]) -> tuple[int, str]:
        resolved_id = api_id or settings.api_id
        resolved_hash = api_hash or settings.api_hash
        if not resolved_id or not resolved_hash:
            preset = API_PRESETS["telegram_desktop"]
            resolved_id = int(preset["api_id"])
            resolved_hash = str(preset["api_hash"])
        return resolved_id, resolved_hash

    def is_api_configured(self) -> bool:
        return bool(settings.api_id and settings.api_hash)

    def _session_path(self, name: str) -> Path:
        return SESSIONS_DIR / f"{name}.session"

    def _load_existing_sessions(self) -> None:
        for session_file in SESSIONS_DIR.glob("*.session"):
            account_id = session_file.stem
            self._accounts[account_id] = AccountInfo(
                id=account_id,
                phone=account_id,
                session_file=str(session_file),
                status=AccountStatus.OFFLINE,
            )

    def register_session_file(self, account_id: str) -> None:
        """确保磁盘上的 session 已登记到内存账号表。"""
        if account_id in self._accounts:
            return
        session = self._session_path(account_id)
        if not session.exists():
            return
        self._accounts[account_id] = AccountInfo(
            id=account_id,
            phone=account_id,
            session_file=str(session),
            status=AccountStatus.OFFLINE,
        )

    def list_accounts(self) -> list[AccountInfo]:
        return [
            AccountInfo(
                **enrich_account_from_json(
                    a.id, enrich_account(a.id, a.model_dump())
                )
            )
            for a in self._accounts.values()
        ]

    def _build_account_client(
        self,
        account_id: str,
        api_id: int,
        api_hash: str,
        meta: dict,
    ) -> TelegramClient:
        ipv6 = meta.get("ipv6")
        client = _make_client(
            self._session_path(account_id),
            api_id,
            api_hash,
            proxy=self._proxy(account_id),
            session_device=session_device_kwargs(meta),
            use_ipv6=bool(ipv6) if ipv6 is not None else False,
        )
        apply_session_init(client, meta, api_id)
        return client

    async def _check_authorized(self, client: TelegramClient) -> tuple[bool, str]:
        try:
            await client(GetStateRequest())
            return True, ""
        except RPCError as exc:
            name = exc.__class__.__name__
            return False, f"{name}: {exc}"
        except Exception as exc:
            return False, str(exc)[:200]

    @staticmethod
    def _is_unregistered(error: str) -> bool:
        text = (error or "").upper().replace(" ", "")
        return "AUTHKEYUNREGISTERED" in text or "AUTH_KEY_UNREGISTERED" in text

    @staticmethod
    def _is_duplicated_ip(error: str) -> bool:
        text = (error or "").upper().replace(" ", "")
        return "TWODIFFERENTIP" in text or "AUTHKEYDUPLICATED" in text or "AUTH_KEY_DUPLICATED" in text

    @staticmethod
    def _is_session_corrupt(error: str) -> bool:
        text = error or ""
        return "Constructor ID" in text or "matching Constructor" in text or "database is locked" in text.lower()

    def _needs_tdata_recover(self, error: str) -> bool:
        return (
            self._is_unregistered(error)
            or self._is_duplicated_ip(error)
            or self._is_session_corrupt(error)
        )

    def _format_connect_error(self, last_error: str, tried_tdata: bool) -> str:
        if self._is_duplicated_ip(last_error):
            return "同一把 Session 被两个 IP 同时使用，密钥已作废。请关掉另一处客户端后扫码，或从 tdata 新建会话"
        unauthorized = (
            self._is_unregistered(last_error)
            or "TDesktopUnauthorized" in last_error
            or "unauthorized" in last_error.lower()
        )
        if unauthorized:
            if tried_tdata:
                return "旧 Session 密钥已失效。tdata 里是同一把密钥，复用重转无效，已尝试新建会话仍失败。请扫码重新登录"
            return "授权密钥未注册（AUTH_KEY_UNREGISTERED）"
        if "没有对应的 tdata" in last_error:
            return "Session 连不上，当前数据目录里没有对应 tdata。请把账号包放到 data/tdata/手机号/ 或扫码登录"
        if last_error.startswith("连接失败"):
            return last_error
        return last_error or "Session 未授权，请重新登录"

    async def _close_client(self, account_id: str) -> None:
        existing = self._clients.pop(account_id, None)
        if not existing:
            return
        try:
            await existing.disconnect()
        except Exception:
            pass
        try:
            existing.session.close()
        except Exception:
            pass

    async def _handshake(
        self,
        account: AccountInfo,
        api_id: int,
        api_hash: str,
        meta: dict,
    ) -> tuple[bool, str]:
        account_id = account.id
        await self._close_client(account_id)
        client = self._build_account_client(account_id, api_id, api_hash, meta)
        try:
            await client.connect()
        except Exception as exc:
            try:
                await client.disconnect()
            except Exception:
                pass
            return False, f"连接失败: {exc}"[:200]

        authorized, err = await self._check_authorized(client)
        if not authorized:
            try:
                await client.disconnect()
            except Exception:
                pass
            return False, err or "Session 未授权"

        me = await client.get_me()
        account.phone = me.phone or account_id
        account.username = me.username or ""
        account.first_name = me.first_name or ""
        account.last_name = me.last_name or ""
        account.status = AccountStatus.ONLINE
        account.error = ""
        self._clients[account_id] = client
        self._move_session_file(account_id, failed=False)
        return True, ""

    async def _accept_live_client(self, account: AccountInfo, client: TelegramClient) -> bool:
        try:
            authorized, _err = await self._check_authorized(client)
            if not authorized:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                return False
            me = await client.get_me()
            account.phone = me.phone or account.id
            account.username = me.username or ""
            account.first_name = me.first_name or ""
            account.last_name = me.last_name or ""
            account.status = AccountStatus.ONLINE
            account.error = ""
            self._clients[account.id] = client
            self._move_session_file(account.id, failed=False)
            return True
        except Exception:
            try:
                await client.disconnect()
            except Exception:
                pass
            return False

    async def _recover_from_tdata(
        self,
        account: AccountInfo,
        *,
        create_new: bool,
    ):
        from backend.telegram.tdata_convert import convert_tdata_for_account

        await self._close_client(account.id)
        return await convert_tdata_for_account(
            account.id,
            self._session_path(account.id),
            create_new=create_new,
            proxy=self._proxy(account.id),
        )

    async def connect_account(self, account_id: str) -> AccountInfo:
        account = self._accounts.get(account_id)
        if not account:
            raise ValueError("账号不存在")

        meta = read_session_json(account_id)
        json_creds = session_api_credentials(meta)
        if json_creds:
            api_id, api_hash = json_creds
        else:
            api_id, api_hash = self._api_credentials(None, None)

        account.status = AccountStatus.CONNECTING
        account.error = ""
        last_error = ""
        tried_tdata = False

        ok, last_error = await self._handshake(account, api_id, api_hash, meta)
        if ok:
            return account

        session_string = session_string_from_meta(meta)
        if session_string and (self._is_session_corrupt(last_error) or not ok):
            try:
                from backend.telegram.tdata_convert import _write_session_from_string

                await self._close_client(account_id)
                _write_session_from_string(session_string, self._session_path(account_id))
                ok, last_error = await self._handshake(account, api_id, api_hash, meta)
                if ok:
                    return account
            except Exception as exc:
                last_error = f"{last_error}; session_string 重建失败: {exc}"[:240]

        if self._needs_tdata_recover(last_error):
            from backend.telegram.tdata_convert import restore_packaged_session

            if restore_packaged_session(account_id, self._session_path(account_id)):
                meta = read_session_json(account_id)
                json_creds = session_api_credentials(meta) or (api_id, api_hash)
                api_id, api_hash = json_creds
                ok, last_error = await self._handshake(account, api_id, api_hash, meta)
                if ok:
                    return account

            try:
                account.error = "正在从 tdata 重转 Session…"
                live = await self._recover_from_tdata(account, create_new=False)
                tried_tdata = True
                if live is not None and await self._accept_live_client(account, live):
                    return account
                meta = read_session_json(account_id)
                json_creds = session_api_credentials(meta) or (api_id, api_hash)
                api_id, api_hash = json_creds
                ok, last_error = await self._handshake(account, api_id, api_hash, meta)
                if ok:
                    return account
            except Exception as exc:
                tried_tdata = True
                last_error = f"tdata 重转失败: {exc}"[:200]

            if self._needs_tdata_recover(last_error):
                try:
                    account.error = "正在从 tdata 新建会话…"
                    live = await self._recover_from_tdata(account, create_new=True)
                    tried_tdata = True
                    if live is not None and await self._accept_live_client(account, live):
                        return account
                except Exception as exc:
                    last_error = f"tdata 新建会话失败: {exc}"[:200]

        account.status = AccountStatus.ERROR
        account.error = self._format_connect_error(last_error, tried_tdata)
        self._move_session_file(account_id, failed=True)
        return account

    def _move_session_file(self, account_id: str, failed: bool) -> None:
        path_key = "failed_account_path" if failed else "success_account_path"
        target_dir = getattr(settings, path_key, "") or ""
        if not target_dir.strip():
            return
        session = self._session_path(account_id)
        if not session.exists():
            return
        dest_dir = Path(target_dir.strip())
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(session, dest_dir / session.name)
            json_file = session.with_suffix(".json")
            if json_file.exists():
                shutil.copy2(json_file, dest_dir / json_file.name)
        except Exception:
            pass

    async def ensure_connected(self, account_id: str) -> TelegramClient:
        """确保账号在线；掉线时最多重试 3 次。"""
        last_error = ""
        for attempt in range(1, 4):
            try:
                if account_id in self._clients:
                    client = self._clients[account_id]
                    if client.is_connected():
                        return client

                account = await self.connect_account(account_id)
                if account.status == AccountStatus.ONLINE:
                    return self._clients[account_id]
                last_error = account.error or f"账号 {account_id} 连接失败"
            except Exception as exc:
                last_error = str(exc)

            await asyncio.sleep(min(2 * attempt, 8))

        raise ValueError(last_error or f"账号 {account_id} 重连失败")

    def is_connected(self, account_id: str) -> bool:
        client = self._clients.get(account_id)
        return bool(client and client.is_connected())

    def account_display(self, account_id: str) -> str:
        account = self._accounts.get(account_id)
        if not account:
            return account_id
        parts = [account_id]
        if account.phone:
            parts.append(account.phone)
        if account.username:
            parts.append(f"@{account.username}")
        return " · ".join(parts)

    async def disconnect_account(self, account_id: str) -> None:
        client = self._clients.pop(account_id, None)
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
        account = self._accounts.get(account_id)
        if account:
            account.status = AccountStatus.OFFLINE

    async def start_login(self, phone: str, api_id: Optional[int], api_hash: Optional[str]) -> dict:
        resolved_id, resolved_hash = self._api_credentials(api_id, api_hash)
        session_name = _safe_phone_name(phone)
        client = _make_client(
            self._session_path(session_name),
            resolved_id,
            resolved_hash,
            proxy=self._proxy(),
        )
        await client.connect()
        sent = await client.send_code_request(phone)
        self._pending[session_name] = PendingLogin(
            client=client,
            phone=phone,
            phone_code_hash=sent.phone_code_hash,
        )
        return {"phone": phone, "session_name": session_name}

    async def verify_login(self, phone: str, code: str, password: Optional[str]) -> AccountInfo:
        session_name = _safe_phone_name(phone)
        pending = self._pending.get(session_name)
        if not pending:
            raise ValueError("请先发送验证码")

        try:
            await pending.client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=pending.phone_code_hash,
            )
        except SessionPasswordNeededError:
            if not password:
                raise ValueError("该账号需要二级密码")
            await pending.client.sign_in(password=password)

        me = await pending.client.get_me()
        account = AccountInfo(
            id=session_name,
            phone=me.phone or phone,
            username=me.username or "",
            first_name=me.first_name or "",
            last_name=me.last_name or "",
            status=AccountStatus.ONLINE,
            session_file=str(self._session_path(session_name)),
        )
        self._accounts[session_name] = account
        self._clients[session_name] = pending.client
        self._pending.pop(session_name, None)
        return account

    async def start_qr_login(
        self, api_id: Optional[int] = None, api_hash: Optional[str] = None
    ) -> dict:
        resolved_id, resolved_hash = self._api_credentials(api_id, api_hash)
        login_id = uuid.uuid4().hex
        session_name = f"qr_{login_id[:12]}"
        client = _make_client(
            self._session_path(session_name),
            resolved_id,
            resolved_hash,
            proxy=self._proxy(),
            connection_retries=2,
            timeout=10,
        )
        try:
            await client.connect()
            if not client.is_connected():
                raise ValueError("无法连接 Telegram 服务器")
            qr_login = await client.qr_login()
        except ValueError:
            await client.disconnect()
            session_path = self._session_path(session_name)
            if session_path.exists():
                session_path.unlink()
            raise
        except Exception as exc:
            await client.disconnect()
            session_path = self._session_path(session_name)
            if session_path.exists():
                session_path.unlink()
            hint = "连接 Telegram 失败，请在「设置」中启用代理（如 Clash: 127.0.0.1:7890）"
            if "timeout" in str(exc).lower():
                raise ValueError(hint) from exc
            raise ValueError(f"{hint}（{exc}）") from exc

        pending = PendingQrLogin(
            client=client,
            qr_login=qr_login,
            session_name=session_name,
        )
        self._pending_qr[login_id] = pending
        pending.wait_task = asyncio.create_task(self._wait_qr_login(login_id))

        return {
            "login_id": login_id,
            "qr_url": qr_login.url,
            "qr_image": self._make_qr_image(qr_login.url),
        }

    async def _wait_qr_login(self, login_id: str) -> None:
        pending = self._pending_qr.get(login_id)
        if not pending:
            return

        try:
            await pending.qr_login.wait(timeout=120)
            pending.account = await self._finalize_qr_account(pending)
            pending.status = QrLoginStatus.SUCCESS
        except SessionPasswordNeededError:
            pending.status = QrLoginStatus.NEED_PASSWORD
        except asyncio.TimeoutError:
            pending.status = QrLoginStatus.EXPIRED
        except asyncio.CancelledError:
            pending.status = QrLoginStatus.CANCELLED
        except Exception as exc:
            pending.status = QrLoginStatus.ERROR
            pending.error = str(exc)

    async def _finalize_qr_account(self, pending: PendingQrLogin) -> AccountInfo:
        me = await pending.client.get_me()
        session_name = pending.session_name
        if me.phone:
            target_name = _safe_phone_name(me.phone)
            if target_name != session_name:
                old_path = self._session_path(session_name)
                new_path = self._session_path(target_name)
                await pending.client.disconnect()
                if old_path.exists():
                    shutil.move(str(old_path), str(new_path))
                old_json = old_path.with_suffix(".json")
                if old_json.exists():
                    shutil.move(str(old_json), str(new_path.with_suffix(".json")))
                session_name = target_name
                pending.client = _make_client(
                    new_path,
                    pending.client.api_id,
                    pending.client.api_hash,
                    proxy=self._proxy(session_name),
                )
                await pending.client.connect()

        account = AccountInfo(
            id=session_name,
            phone=me.phone or session_name,
            username=me.username or "",
            first_name=me.first_name or "",
            last_name=me.last_name or "",
            status=AccountStatus.ONLINE,
            session_file=str(self._session_path(session_name)),
        )
        self._accounts[session_name] = account
        self._clients[session_name] = pending.client
        return account

    def get_qr_login_status(self, login_id: str) -> dict:
        pending = self._pending_qr.get(login_id)
        if not pending:
            raise ValueError("扫码登录会话不存在或已过期")

        result = {
            "login_id": login_id,
            "status": pending.status.value,
            "qr_url": pending.qr_login.url,
            "error": pending.error,
            "account": pending.account,
        }
        if pending.status in (QrLoginStatus.WAITING, QrLoginStatus.EXPIRED):
            result["qr_image"] = self._make_qr_image(pending.qr_login.url)
        return result

    async def refresh_qr_login(self, login_id: str) -> dict:
        pending = self._pending_qr.get(login_id)
        if not pending:
            raise ValueError("扫码登录会话不存在或已过期")
        if pending.status not in (QrLoginStatus.WAITING, QrLoginStatus.EXPIRED):
            raise ValueError("当前状态无法刷新二维码")

        if pending.wait_task and not pending.wait_task.done():
            pending.wait_task.cancel()
            try:
                await pending.wait_task
            except asyncio.CancelledError:
                pass

        await pending.qr_login.recreate()
        pending.status = QrLoginStatus.WAITING
        pending.error = ""
        pending.wait_task = asyncio.create_task(self._wait_qr_login(login_id))

        return {
            "login_id": login_id,
            "qr_url": pending.qr_login.url,
            "qr_image": self._make_qr_image(pending.qr_login.url),
        }

    async def complete_qr_login(self, login_id: str, password: str) -> AccountInfo:
        pending = self._pending_qr.get(login_id)
        if not pending:
            raise ValueError("扫码登录会话不存在或已过期")
        if pending.status != QrLoginStatus.NEED_PASSWORD:
            raise ValueError("当前不需要二级密码")
        if not password:
            raise ValueError("请输入二级密码")

        await pending.client.sign_in(password=password)
        pending.account = await self._finalize_qr_account(pending)
        pending.status = QrLoginStatus.SUCCESS
        self._pending_qr.pop(login_id, None)
        return pending.account

    async def cancel_qr_login(self, login_id: str) -> None:
        pending = self._pending_qr.pop(login_id, None)
        if not pending:
            return
        if pending.wait_task and not pending.wait_task.done():
            pending.wait_task.cancel()
            try:
                await pending.wait_task
            except asyncio.CancelledError:
                pass
        pending.status = QrLoginStatus.CANCELLED
        await pending.client.disconnect()
        session = self._session_path(pending.session_name)
        if session.exists():
            session.unlink()
        json_file = session.with_suffix(".json")
        if json_file.exists():
            json_file.unlink()

    async def import_session(self, source_path: Path) -> AccountInfo:
        if not source_path.exists():
            raise ValueError("文件不存在")

        target_name = source_path.stem
        target = self._session_path(target_name)
        shutil.copy2(source_path, target)

        json_source = source_path.with_suffix(".json")
        json_copied = False
        if json_source.exists():
            shutil.copy2(json_source, target.with_suffix(".json"))
            json_copied = True

        account = AccountInfo(
            id=target_name,
            phone=target_name,
            session_file=str(target),
            status=AccountStatus.OFFLINE,
        )
        enriched = enrich_account_from_json(
            target_name, enrich_account(target_name, account.model_dump())
        )
        account = AccountInfo(**enriched)
        self._accounts[target_name] = account
        shutil.copy2(source_path, IMPORT_OK_DIR / source_path.name)
        if json_copied:
            try:
                shutil.copy2(json_source, IMPORT_OK_DIR / json_source.name)
            except Exception:
                pass
        return account

    async def delete_account(self, account_id: str) -> None:
        await self.disconnect_account(account_id)
        self._accounts.pop(account_id, None)
        session = self._session_path(account_id)
        if session.exists():
            session.unlink()
        json_file = session.with_suffix(".json")
        if json_file.exists():
            json_file.unlink()

    async def shutdown(self) -> None:
        for login_id in list(self._pending_qr.keys()):
            await self.cancel_qr_login(login_id)
        for account_id in list(self._clients.keys()):
            await self.disconnect_account(account_id)
        for pending in self._pending.values():
            await pending.client.disconnect()
        self._pending.clear()


client_manager = ClientManager()
