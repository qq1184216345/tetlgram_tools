from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import DATA_DIR, PROFILE_DIR, PROJECT_ROOT, SESSIONS_DIR, settings
from backend.models.schemas import (
    AccountCustomAdRequest,
    AccountInfo,
    AccountProxyRequest,
    AssignProxiesRequest,
    AccountStatusCheckRequest,
    ApiResponse,
    AppConfig,
    ChatHistoryRequest,
    ConnectAccountsRequest,
    ExportAccountGroupsRequest,
    HealthResponse,
    ImportSessionPathsRequest,
    InviteAdminsRequest,
    KeepOnlineRequest,
    KickDevicesRequest,
    LicenseStatusReport,
    LoginStartRequest,
    LoginVerifyRequest,
    MessageTemplateRequest,
    PrivacyBatchRequest,
    ProxyTestRequest,
    QrLoginPasswordRequest,
    QrLoginStatusResponse,
    TaskInfo,
    TdataConvertRequest,
    VoiceCallRequest,
)
from backend.storage.account_ads import get_account_ad, set_account_ad
from backend.storage.account_meta import set_proxy
from backend.storage.message_templates import load_templates, save_templates
from backend.telegram.api_presets import list_api_presets
from backend.telegram.client_manager import client_manager
from backend.tasks.task_manager import task_manager
from backend.telegram.chat_history import fetch_chat_history
from backend.telegram.device_profiles import list_device_profiles
from backend.telegram.tdata_convert import (
    TDATA_DIR,
    attach_package_meta,
    discover_account_packages,
    import_tdata_path,
)
from backend.version import APP_VERSION, DEFAULT_UPDATE_MANIFEST_URL

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        accounts=len(client_manager.list_accounts()),
    )


@router.post("/api/license/report", response_model=ApiResponse)
async def report_license(payload: LicenseStatusReport) -> ApiResponse:
    from backend.license_gate import evaluate_license, save_license_cache

    save_license_cache(payload.model_dump())
    status = evaluate_license()
    return ApiResponse(success=True, message=status["reason"], data=status)


@router.get("/api/license/status", response_model=ApiResponse)
async def license_status() -> ApiResponse:
    from backend.license_gate import evaluate_license, load_license_cache

    status = evaluate_license()
    cache = load_license_cache() or {}
    return ApiResponse(
        success=bool(status["allowed"]),
        message=status["reason"],
        data={**status, "cache_email": cache.get("email")},
    )


@router.get("/api/app-info")
async def app_info() -> dict:
    suggested = DATA_DIR.parent / "PaperWing-data-2"
    return {
        "version": APP_VERSION,
        "data_dir": str(DATA_DIR.resolve()),
        "project_root": str(PROJECT_ROOT.resolve()),
        "backend_host": settings.host,
        "backend_port": settings.port,
        "suggested_data_dir": str(suggested.resolve()),
        "update_manifest_url": DEFAULT_UPDATE_MANIFEST_URL,
    }


@router.get("/api/accounts", response_model=list[AccountInfo])
async def list_accounts() -> list[AccountInfo]:
    return client_manager.list_accounts()


@router.post("/api/accounts/connect-batch", response_model=TaskInfo)
async def connect_accounts_batch(payload: ConnectAccountsRequest) -> TaskInfo:
    try:
        return task_manager.start_connect_accounts(payload.account_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/accounts/{account_id}/connect", response_model=AccountInfo)
async def connect_account(account_id: str) -> AccountInfo:
    try:
        return await client_manager.connect_account(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/accounts/{account_id}/disconnect", response_model=ApiResponse)
async def disconnect_account(account_id: str) -> ApiResponse:
    await client_manager.disconnect_account(account_id)
    return ApiResponse(success=True, message="已断开连接")


@router.delete("/api/accounts/{account_id}", response_model=ApiResponse)
async def delete_account(account_id: str) -> ApiResponse:
    await client_manager.delete_account(account_id)
    return ApiResponse(success=True, message="账号已删除")


@router.post("/api/accounts/{account_id}/check-status", response_model=ApiResponse)
async def check_account_status(account_id: str) -> ApiResponse:
    from backend.telegram.spambot import check_spambot_status

    try:
        client = await client_manager.ensure_connected(account_id)
        result = await check_spambot_status(client)
        return ApiResponse(
            success=True,
            message=result.summary,
            data={
                "status": result.status,
                "summary": result.summary,
                "full_text": result.full_text,
                "verify_links": result.verify_links,
                "limited": result.limited,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/accounts/check-status", response_model=ApiResponse)
async def check_accounts_status(payload: AccountStatusCheckRequest) -> ApiResponse:
    from backend.telegram.spambot import check_spambot_status

    ids = payload.account_ids or [a.id for a in client_manager.list_accounts()]
    results: list[dict] = []
    for account_id in ids:
        try:
            client = await client_manager.ensure_connected(account_id)
            result = await check_spambot_status(client)
            results.append(
                {
                    "account_id": account_id,
                    "status": result.status,
                    "summary": result.summary,
                    "full_text": result.full_text,
                    "verify_links": result.verify_links,
                    "limited": result.limited,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "account_id": account_id,
                    "status": "error",
                    "summary": str(exc),
                    "full_text": "",
                    "verify_links": [],
                    "limited": False,
                }
            )
    limited = sum(1 for r in results if r.get("limited"))
    return ApiResponse(
        success=True,
        message=f"已检测 {len(results)} 个账号，其中 {limited} 个疑似受限",
        data={"results": results},
    )


@router.get("/api/accounts/{account_id}/devices", response_model=ApiResponse)
async def list_account_devices(account_id: str) -> ApiResponse:
    from backend.telegram.devices import list_authorizations

    try:
        client = await client_manager.ensure_connected(account_id)
        devices = await list_authorizations(client)
        return ApiResponse(success=True, message=f"共 {len(devices)} 个在线设备", data={"devices": devices})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/accounts/{account_id}/kick-devices", response_model=ApiResponse)
async def kick_account_devices(
    account_id: str, payload: KickDevicesRequest | None = None
) -> ApiResponse:
    from backend.telegram.devices import kick_other_sessions, kick_sessions_by_hashes

    try:
        client = await client_manager.ensure_connected(account_id)
        hashes = list(payload.hashes) if payload else []
        if hashes:
            kicked = await kick_sessions_by_hashes(client, hashes)
            return ApiResponse(success=True, message=f"已踢掉 {kicked} 个选中设备")
        kicked = await kick_other_sessions(client)
        return ApiResponse(success=True, message=f"已踢掉 {kicked} 个其他设备")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/accounts/privacy-batch", response_model=ApiResponse)
async def privacy_batch(payload: PrivacyBatchRequest) -> ApiResponse:
    from backend.telegram.devices import set_privacy_batch

    ok = 0
    errors: list[str] = []
    for account_id in payload.account_ids:
        try:
            client = await client_manager.ensure_connected(account_id)
            await set_privacy_batch(
                client,
                {
                    "phone": payload.phone,
                    "last_seen": payload.last_seen,
                    "profile_photo": payload.profile_photo,
                    "invite": payload.invite,
                },
            )
            ok += 1
        except Exception as exc:
            errors.append(f"{account_id}: {exc}")
    msg = f"已更新 {ok} 个账号隐私设置"
    if errors:
        msg += f"；失败 {len(errors)} 个"
    return ApiResponse(success=ok > 0, message=msg, data={"ok": ok, "errors": errors})


@router.post("/api/accounts/export-groups", response_model=ApiResponse)
async def export_account_groups(payload: ExportAccountGroupsRequest) -> ApiResponse:
    from backend.telegram.export_groups import export_account_groups as do_export

    if not payload.account_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个账号")
    logs: list[str] = []

    def on_log(level: str, msg: str) -> None:
        logs.append(f"[{level}] {msg}")

    try:
        outputs = await do_export(
            payload.account_ids,
            client_manager.ensure_connected,
            on_log,
            mode=payload.mode or "both",
        )
        return ApiResponse(
            success=True,
            message=f"导出完成（{len(outputs)} 个账号）",
            data={"outputs": outputs, "logs": logs},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/accounts/keep-online")
async def get_keep_online() -> dict:
    from backend.telegram.keep_online import list_keep_online_accounts

    return {"accounts": list_keep_online_accounts()}


@router.post("/api/accounts/keep-online", response_model=ApiResponse)
async def set_keep_online(payload: KeepOnlineRequest) -> ApiResponse:
    from backend.telegram.keep_online import start_keep_online, stop_keep_online

    if payload.enable:
        if not payload.account_ids:
            raise HTTPException(status_code=400, detail="请至少选择一个账号")
        started = await start_keep_online(
            payload.account_ids,
            client_manager.ensure_connected,
            interval_sec=float(payload.interval_sec or 60),
        )
        return ApiResponse(
            success=True,
            message=f"已启用保持在线：{len(started)} 个账号",
            data={"accounts": started},
        )
    stopped = await stop_keep_online(payload.account_ids or None)
    return ApiResponse(
        success=True,
        message=f"已停止保持在线：{len(stopped)} 个账号",
        data={"accounts": stopped},
    )


@router.post("/api/accounts/voice-call", response_model=ApiResponse)
async def voice_call(payload: VoiceCallRequest) -> ApiResponse:
    from backend.telegram.voice_call import start_voice_call

    try:
        client = await client_manager.ensure_connected(payload.account_id)
        message = await start_voice_call(client, payload.target)
        return ApiResponse(success=True, message=message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _drop_live_connection(account_id: str) -> bool:
    if not client_manager.is_connected(account_id):
        return False
    await client_manager.disconnect_account(account_id)
    return True


@router.put("/api/accounts/{account_id}/proxy", response_model=ApiResponse)
async def update_account_proxy(account_id: str, payload: AccountProxyRequest) -> ApiResponse:
    set_proxy(account_id, payload.proxy.strip())
    dropped = await _drop_live_connection(account_id)
    message = "账号代理已更新"
    if dropped:
        message += "，旧连接已断开，请重新连接后生效"
    return ApiResponse(success=True, message=message)


@router.post("/api/accounts/assign-proxies", response_model=ApiResponse)
async def assign_account_proxies(payload: AssignProxiesRequest) -> ApiResponse:
    lines = [
        line.strip()
        for line in (getattr(settings, "proxy_list", "") or "").splitlines()
        if line.strip()
    ]
    if not lines:
        raise HTTPException(status_code=400, detail="设置里还没有 HTTP/SOCKS 代理列表。请在设置中手动填写，或填本机 Clash 端口（常见 127.0.0.1:7890）。")

    accounts = client_manager.list_accounts()
    known = {item.id for item in accounts}
    target_ids = [aid for aid in payload.account_ids if aid in known] if payload.account_ids else [item.id for item in accounts]
    if not target_ids:
        raise HTTPException(status_code=400, detail="请先勾选要分配的账号")

    assigned: list[dict] = []
    dropped = 0
    for index, account_id in enumerate(target_ids):
        proxy = lines[index % len(lines)]
        set_proxy(account_id, proxy)
        if await _drop_live_connection(account_id):
            dropped += 1
        assigned.append({"id": account_id, "proxy": proxy})

    extra = ""
    if len(target_ids) > len(lines):
        extra = f"；代理只有 {len(lines)} 条，已循环分配"
    if dropped:
        extra += f"；已断开 {dropped} 个在线连接，请重新批量连接"
    return ApiResponse(
        success=True,
        message=f"已为 {len(assigned)} 个账号分配不同节点{extra}",
        data={"assigned": assigned},
    )


@router.get("/api/accounts/{account_id}/custom-ad")
async def get_account_custom_ad(account_id: str) -> dict:
    return {"message": get_account_ad(account_id) or ""}


@router.put("/api/accounts/{account_id}/custom-ad", response_model=ApiResponse)
async def update_account_custom_ad(
    account_id: str, payload: AccountCustomAdRequest
) -> ApiResponse:
    set_account_ad(account_id, payload.message)
    return ApiResponse(success=True, message="独立广告语已保存")


@router.post("/api/accounts/{account_id}/chat-history")
async def get_chat_history(account_id: str, payload: ChatHistoryRequest) -> list[dict]:
    try:
        client = await client_manager.ensure_connected(account_id)
        return await fetch_chat_history(client, payload.target, payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/message-templates")
async def get_message_templates() -> dict:
    return load_templates()


@router.put("/api/message-templates", response_model=ApiResponse)
async def put_message_templates(payload: MessageTemplateRequest) -> ApiResponse:
    save_templates({"broadcast": payload.broadcast, "dm": payload.dm})
    return ApiResponse(success=True, message="消息模板已保存")


@router.post("/api/accounts/login/start", response_model=ApiResponse)
async def login_start(payload: LoginStartRequest) -> ApiResponse:
    try:
        data = await client_manager.start_login(
            payload.phone,
            payload.api_id,
            payload.api_hash,
        )
        return ApiResponse(success=True, message="验证码已发送", data=data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/accounts/login/verify", response_model=AccountInfo)
async def login_verify(payload: LoginVerifyRequest) -> AccountInfo:
    try:
        return await client_manager.verify_login(
            payload.phone,
            payload.code,
            payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/accounts/login/qr/start", response_model=ApiResponse)
async def qr_login_start() -> ApiResponse:
    try:
        data = await client_manager.start_qr_login()
        if client_manager.is_api_configured():
            message = "二维码已生成"
        else:
            message = "二维码已生成（当前使用 Telegram Desktop 公共 API，建议在设置中填写自己的 api_id/api_hash）"
        return ApiResponse(success=True, message=message, data=data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/accounts/login/qr/{login_id}/status", response_model=QrLoginStatusResponse)
async def qr_login_status(login_id: str) -> QrLoginStatusResponse:
    try:
        data = client_manager.get_qr_login_status(login_id)
        return QrLoginStatusResponse(**data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/accounts/login/qr/{login_id}/refresh", response_model=ApiResponse)
async def qr_login_refresh(login_id: str) -> ApiResponse:
    try:
        data = await client_manager.refresh_qr_login(login_id)
        return ApiResponse(success=True, message="二维码已刷新", data=data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/accounts/login/qr/{login_id}/password", response_model=AccountInfo)
async def qr_login_password(login_id: str, payload: QrLoginPasswordRequest) -> AccountInfo:
    try:
        return await client_manager.complete_qr_login(login_id, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/api/accounts/login/qr/{login_id}", response_model=ApiResponse)
async def qr_login_cancel(login_id: str) -> ApiResponse:
    await client_manager.cancel_qr_login(login_id)
    return ApiResponse(success=True, message="已取消扫码登录")


@router.post("/api/accounts/import-session", response_model=AccountInfo)
async def import_session(file: UploadFile = File(...)) -> AccountInfo:
    if not file.filename or not file.filename.endswith(".session"):
        raise HTTPException(status_code=400, detail="请上传 .session 文件")

    temp_path = SESSIONS_DIR / f"_import_{file.filename}"
    content = await file.read()
    temp_path.write_bytes(content)
    try:
        account = await client_manager.import_session(temp_path)
        return account
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _collect_session_files(paths: list[str]) -> tuple[list[Path], list[str]]:
    found: list[Path] = []
    errors: list[str] = []
    for raw in paths:
        path = Path((raw or "").strip().strip('"'))
        if not path.exists():
            errors.append(f"{raw}: 文件不存在")
            continue
        candidates: list[Path] = []
        if path.is_file():
            candidates.append(path)
        elif path.is_dir():
            candidates.extend(path.glob("*.session"))
            candidates.extend(path.glob("*.json"))
            for child in path.iterdir():
                if child.is_dir():
                    candidates.extend(child.glob("*.session"))
                    candidates.extend(child.glob("*.json"))
        for item in candidates:
            if item.suffix.lower() in {".session", ".json"}:
                found.append(item)
            elif path.is_file():
                errors.append(f"{item.name}: 仅支持 .session / .json")
    return found, errors


async def _import_sessions_from_staging(staging: Path, errors: list[str]) -> ApiResponse:
    import shutil

    imported = 0
    json_attached = 0
    try:
        session_files = sorted(staging.glob("*.session"))
        for session_file in session_files:
            try:
                await client_manager.import_session(session_file)
                imported += 1
                if session_file.with_suffix(".json").exists():
                    json_attached += 1
            except Exception as exc:
                errors.append(f"{session_file.name}: {exc}")

        for json_file in staging.glob("*.json"):
            if (staging / f"{json_file.stem}.session").exists():
                continue
            existing_session = SESSIONS_DIR / f"{json_file.stem}.session"
            if not existing_session.exists():
                errors.append(f"{json_file.name}: 找不到同名 .session，已跳过")
                continue
            try:
                shutil.copy2(json_file, SESSIONS_DIR / f"{json_file.stem}.json")
                json_attached += 1
                client_manager.register_session_file(json_file.stem)
            except Exception as exc:
                errors.append(f"{json_file.name}: {exc}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    if imported == 0 and json_attached == 0:
        msg = "未导入任何账号"
    else:
        msg = f"成功导入 {imported} 个 session"
        if json_attached:
            msg += f"，关联/补挂 {json_attached} 个 json"
    if errors:
        msg += f"，失败/跳过 {len(errors)} 个"
    return ApiResponse(
        success=imported > 0 or json_attached > 0,
        message=msg,
        data={"errors": errors, "imported": imported, "json_attached": json_attached},
    )


@router.post("/api/accounts/import-sessions", response_model=ApiResponse)
async def import_sessions(files: list[UploadFile] = File(...)) -> ApiResponse:
    import uuid

    if not files:
        raise HTTPException(status_code=400, detail="请选择要导入的文件")

    staging = SESSIONS_DIR / f"_import_batch_{uuid.uuid4().hex[:10]}"
    staging.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for file in files:
        raw_name = (file.filename or "").replace("\\", "/").split("/")[-1]
        if not raw_name:
            continue
        lower = raw_name.lower()
        if not (lower.endswith(".session") or lower.endswith(".json")):
            errors.append(f"{raw_name}: 仅支持 .session / .json")
            continue
        (staging / raw_name).write_bytes(await file.read())

    return await _import_sessions_from_staging(staging, errors)


@router.post("/api/accounts/import-session-paths", response_model=ApiResponse)
async def import_session_paths(payload: ImportSessionPathsRequest) -> ApiResponse:
    import shutil
    import uuid

    if not payload.paths:
        raise HTTPException(status_code=400, detail="请拖入 .session / .json 文件")

    files, errors = _collect_session_files(payload.paths)
    if not files:
        return ApiResponse(success=False, message="未找到可导入的 .session / .json", data={"errors": errors})

    staging = SESSIONS_DIR / f"_import_batch_{uuid.uuid4().hex[:10]}"
    staging.mkdir(parents=True, exist_ok=True)
    for item in files:
        try:
            shutil.copy2(item, staging / item.name)
        except Exception as exc:
            errors.append(f"{item.name}: {exc}")

    return await _import_sessions_from_staging(staging, errors)


@router.post("/api/accounts/convert-tdata", response_model=ApiResponse)
async def convert_tdata(payload: TdataConvertRequest) -> ApiResponse:
    raw_path = (payload.tdata_path or "").strip()
    tdata_path = Path(raw_path) if raw_path else TDATA_DIR
    try:
        packages = discover_account_packages(tdata_path)
        imported_items, failed_items = await import_tdata_path(
            tdata_path,
            payload.session_name or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc) or "导入失败") from exc

    imported: list[dict] = []
    errors: list[str] = []
    package_by_name = {item.name: item for item in packages}

    for item in imported_items:
        try:
            account = await client_manager.import_session(Path(item.session_file))
            package = package_by_name.get(item.name)
            if package:
                attach_package_meta(package, account.id)
                client_manager.register_session_file(account.id)
            imported.append(
                {
                    "account_id": account.id,
                    "phone": account.phone,
                    "method": item.method,
                }
            )
        except Exception as exc:
            errors.append(f"{item.name}: {exc}")

    errors.extend(f"{item.name}: {item.error}" for item in failed_items if item.error)

    if imported:
        msg = f"成功导入 {len(imported)} 个账号"
        if errors:
            msg += f"，失败 {len(errors)} 个"
    else:
        msg = "未导入任何账号"
        if errors:
            msg += f"：{errors[0]}"

    return ApiResponse(
        success=bool(imported),
        message=msg,
        data={
            "imported": imported,
            "errors": errors,
            "imported_count": len(imported),
            "error_count": len(errors),
        },
    )

    imported: list[dict] = []
    errors: list[str] = []
    package_by_name = {item.name: item for item in packages}

    for item in imported_items:
        try:
            account = await client_manager.import_session(Path(item.session_file))
            package = package_by_name.get(item.name)
            if package:
                attach_package_meta(package, account.id)
                client_manager.register_session_file(account.id)
            imported.append(
                {
                    "account_id": account.id,
                    "phone": account.phone,
                    "method": item.method,
                }
            )
        except Exception as exc:
            errors.append(f"{item.name}: {exc}")

    errors.extend(f"{item.name}: {item.error}" for item in failed_items if item.error)

    if imported:
        msg = f"成功导入 {len(imported)} 个账号"
        if errors:
            msg += f"，失败 {len(errors)} 个"
    else:
        msg = "未导入任何账号"
        if errors:
            msg += f"：{errors[0]}"

    return ApiResponse(
        success=bool(imported),
        message=msg,
        data={
            "imported": imported,
            "errors": errors,
            "imported_count": len(imported),
            "error_count": len(errors),
        },
    )


@router.get("/api/profile-config")
async def get_profile_config() -> dict:
    files = ["名字.txt", "姓氏.txt", "用户名.txt", "简介.txt"]
    status = {}
    for name in files:
        path = PROFILE_DIR / name
        if path.exists():
            lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            status[name] = {"exists": True, "count": len(lines)}
        else:
            status[name] = {"exists": False, "count": 0}
    avatars = list(PROFILE_DIR.glob("*.jpg")) + list(PROFILE_DIR.glob("*.png"))
    status["avatars"] = {"count": len(avatars)}
    return status


@router.get("/api/config", response_model=AppConfig)
async def get_config() -> AppConfig:
    return AppConfig(
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        socks5_ip=settings.socks5_ip,
        socks5_port=settings.socks5_port,
        proxy_state=settings.proxy_state,
        proxy_type=getattr(settings, "proxy_type", "socks5"),
        proxy_list=getattr(settings, "proxy_list", ""),
        use_system_proxy=getattr(settings, "use_system_proxy", False),
        success_account_path=getattr(settings, "success_account_path", ""),
        failed_account_path=getattr(settings, "failed_account_path", ""),
        ai_api_url=getattr(settings, "ai_api_url", ""),
        ai_api_key=getattr(settings, "ai_api_key", ""),
        ai_model=getattr(settings, "ai_model", "gpt-4o-mini"),
        ai_verify_enabled=getattr(settings, "ai_verify_enabled", False),
        device_profile=getattr(settings, "device_profile", "apple_desktop"),
    )


@router.get("/api/config/api-presets")
async def get_api_presets() -> list[dict]:
    return list_api_presets()


@router.get("/api/config/device-profiles")
async def get_device_profiles() -> list[dict]:
    return list_device_profiles()


@router.post("/api/proxy/test", response_model=ApiResponse)
async def test_proxy_connection(payload: ProxyTestRequest | None = None) -> ApiResponse:
    from backend.telegram.network_test import test_telegram_connection

    extra = payload or ProxyTestRequest()
    try:
        message = await test_telegram_connection(
            proxy_state=extra.proxy_state,
            use_system_proxy=extra.use_system_proxy,
            proxy_type=extra.proxy_type,
            proxy_list=extra.proxy_list,
        )
        return ApiResponse(success=True, message=message)
    except Exception as exc:
        return ApiResponse(success=False, message=str(exc))


@router.post("/api/proxy/probe", response_model=ApiResponse)
async def probe_proxies(payload: ProxyTestRequest | None = None) -> ApiResponse:
    from backend.telegram.proxy import probe_proxy_list

    extra = payload or ProxyTestRequest()
    text = extra.proxy_list if extra.proxy_list is not None else (settings.proxy_list or "")
    kind = extra.proxy_type or settings.proxy_type or "socks5"
    result = await probe_proxy_list(text, kind)
    if result["total"] == 0:
        return ApiResponse(success=False, message="代理列表是空的")
    note = "（仅检测了前 300 条）" if result["truncated"] else ""
    return ApiResponse(
        success=result["alive"] > 0,
        message=f"端口检测完成：{result['alive']} 个可达，{result['dead']} 个不通{note}",
        data=result,
    )


@router.get("/api/config/detect-proxy", response_model=ApiResponse)
async def detect_system_proxy() -> ApiResponse:
    from backend.telegram.proxy import detect_system_proxy

    proxy = detect_system_proxy()
    if proxy:
        return ApiResponse(success=True, message="已检测到系统代理", data={"proxy": proxy})
    return ApiResponse(
        success=False,
        message="未检测到系统代理。若开了 TUN 模式，请手动填 127.0.0.1:7890 并选 HTTP",
    )


@router.post("/api/invite/set-admins", response_model=ApiResponse)
async def set_invite_admins(payload: InviteAdminsRequest) -> ApiResponse:
    if not payload.admin_account_id.strip():
        raise HTTPException(status_code=400, detail="请填写主管理员账号")
    if not payload.group_link.strip():
        raise HTTPException(status_code=400, detail="请填写目标群组")
    if not payload.account_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个要设管的账号")

    try:
        admin_client = await client_manager.ensure_connected(payload.admin_account_id)
        members: list[tuple[str, object]] = []
        for aid in payload.account_ids:
            if aid == payload.admin_account_id:
                continue
            members.append((aid, await client_manager.ensure_connected(aid)))

        from backend.telegram.invite_admin import batch_set_invite_admins

        results = await batch_set_invite_admins(
            admin_client,
            payload.group_link.strip(),
            members,
            promote=payload.promote,
        )
        ok = sum(1 for r in results if r.get("ok"))
        fail = len(results) - ok
        action = "设管" if payload.promote else "取消管理"
        return ApiResponse(
            success=ok > 0 or fail == 0,
            message=f"{action}完成：成功 {ok}，失败 {fail}",
            data={"results": results},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/api/config", response_model=ApiResponse)
async def update_config(payload: AppConfig) -> ApiResponse:
    settings.api_id = payload.api_id
    settings.api_hash = payload.api_hash
    settings.socks5_ip = payload.socks5_ip
    settings.socks5_port = payload.socks5_port
    settings.proxy_state = payload.proxy_state
    settings.proxy_type = payload.proxy_type
    settings.proxy_list = payload.proxy_list
    settings.use_system_proxy = payload.use_system_proxy
    settings.success_account_path = payload.success_account_path
    settings.failed_account_path = payload.failed_account_path
    settings.ai_api_url = payload.ai_api_url
    settings.ai_api_key = payload.ai_api_key
    settings.ai_model = payload.ai_model
    settings.ai_verify_enabled = payload.ai_verify_enabled
    settings.device_profile = payload.device_profile or "apple_desktop"
    settings.persist()
    return ApiResponse(success=True, message="配置已保存")
