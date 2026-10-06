from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR
from backend.license_crypto import decrypt_text, encrypt_text

LICENSE_CACHE_FILE = DATA_DIR / "license_cache.enc"
LEGACY_CACHE_FILE = DATA_DIR / "license_cache.json"
OFFLINE_GRACE = timedelta(hours=24)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        raw = value.replace("Z", "")
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def save_license_cache(payload: dict[str, Any]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "token": (payload.get("token") or "")[:200],
        "email": payload.get("email") or "",
        "expires_at": payload.get("expires_at"),
        "licensed": bool(payload.get("licensed")),
        "checked_at": payload.get("checked_at") or (_utcnow().isoformat() + "Z"),
    }
    plain = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    LICENSE_CACHE_FILE.write_text(encrypt_text(plain), encoding="utf-8")
    if LEGACY_CACHE_FILE.exists():
        LEGACY_CACHE_FILE.unlink(missing_ok=True)
    return LICENSE_CACHE_FILE


def load_license_cache() -> dict[str, Any] | None:
    if LICENSE_CACHE_FILE.exists():
        try:
            plain = decrypt_text(LICENSE_CACHE_FILE.read_text(encoding="utf-8").strip())
            return json.loads(plain)
        except Exception:
            return None

    # 兼容旧版明文缓存，读后立即加密落盘
    if LEGACY_CACHE_FILE.exists():
        try:
            data = json.loads(LEGACY_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                save_license_cache(data)
                return data
        except Exception:
            return None
    return None


def clear_license_cache() -> None:
    for path in (LICENSE_CACHE_FILE, LEGACY_CACHE_FILE):
        if path.exists():
            path.unlink(missing_ok=True)


def evaluate_license(cache: dict[str, Any] | None = None) -> dict[str, Any]:
    """返回 {allowed, reason, offline, expires_at, email}。"""
    data = cache if cache is not None else load_license_cache()
    if not data or not data.get("token"):
        return {
            "allowed": False,
            "reason": "未登录授权账号",
            "offline": False,
            "expires_at": None,
            "email": "",
        }

    now = _utcnow()
    expires_at = _parse_iso(data.get("expires_at"))
    checked_at = _parse_iso(data.get("checked_at")) or now
    licensed_flag = bool(data.get("licensed"))

    if expires_at and expires_at <= now:
        return {
            "allowed": False,
            "reason": "授权已过期",
            "offline": False,
            "expires_at": data.get("expires_at"),
            "email": data.get("email") or "",
        }

    if not licensed_flag and not expires_at:
        return {
            "allowed": False,
            "reason": "未激活卡密",
            "offline": False,
            "expires_at": None,
            "email": data.get("email") or "",
        }

    if now - checked_at > OFFLINE_GRACE:
        return {
            "allowed": False,
            "reason": "离线超过 24 小时，请联网重新校验授权",
            "offline": True,
            "expires_at": data.get("expires_at"),
            "email": data.get("email") or "",
        }

    return {
        "allowed": True,
        "reason": "ok",
        "offline": now - checked_at > timedelta(minutes=15),
        "expires_at": data.get("expires_at"),
        "email": data.get("email") or "",
    }


def assert_licensed() -> None:
    result = evaluate_license()
    if not result["allowed"]:
        raise PermissionError(result["reason"])
