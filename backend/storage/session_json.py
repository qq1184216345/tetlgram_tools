from __future__ import annotations

import json
from pathlib import Path

from backend.config import SESSIONS_DIR

_TWO_FA_KEYS = ("twoFA", "two_fa", "twofa", "password", "2fa")


def read_session_json(account_id: str) -> dict:
    path = SESSIONS_DIR / f"{account_id}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def session_two_fa(meta: dict) -> str:
    for key in _TWO_FA_KEYS:
        value = str(meta.get(key) or "").strip()
        if value:
            return value
    return ""


def session_string_from_meta(meta: dict) -> str:
    for key in ("session_string", "sessionString", "string_session"):
        value = str(meta.get(key) or "").strip()
        if len(value) >= 40:
            return value
    return ""


def session_device_kwargs(meta: dict) -> dict[str, str]:
    mapping = {
        "device_model": ("device_model", "device"),
        "system_version": ("system_version", "sdk", "SDK"),
        "app_version": ("app_version",),
        "lang_code": ("lang_code",),
        "system_lang_code": ("system_lang_code", "system_lang_pack"),
    }
    out: dict[str, str] = {}
    for dest, keys in mapping.items():
        for key in keys:
            value = str(meta.get(key) or "").strip()
            if value:
                out[dest] = value
                break
    return out


def session_api_credentials(meta: dict) -> tuple[int, str] | None:
    json_api_id = meta.get("api_id") or meta.get("app_id")
    json_api_hash = meta.get("api_hash") or meta.get("app_hash")
    lang_pack = str(meta.get("lang_pack") or "").strip().lower()
    if json_api_id:
        api_id = int(json_api_id)
        api_hash = str(json_api_hash or "").strip()
        if api_id == 2040 and not api_hash:
            from backend.telegram.api_presets import API_PRESETS

            api_hash = str(API_PRESETS["telegram_desktop"]["api_hash"])
        if api_id and api_hash:
            return api_id, api_hash
    if lang_pack == "tdesktop":
        from backend.telegram.api_presets import API_PRESETS

        preset = API_PRESETS["telegram_desktop"]
        return int(preset["api_id"]), str(preset["api_hash"])
    return None


def apply_session_init(client, meta: dict, api_id: int) -> None:
    req = getattr(client, "_init_request", None)
    if req is None:
        return
    lang_pack = str(meta.get("lang_pack") or "").strip()
    if not lang_pack and int(api_id or 0) == 2040:
        lang_pack = "tdesktop"
    if lang_pack:
        req.lang_pack = lang_pack
    tz = meta.get("tz_offset")
    if tz is None or tz == "":
        return
    try:
        tz_val = float(tz)
    except (TypeError, ValueError):
        return
    from telethon.tl.types import JsonNumber, JsonObject, JsonObjectValue

    req.params = JsonObject([JsonObjectValue("tz_offset", JsonNumber(tz_val))])


def enrich_account_from_json(account_id: str, account_dict: dict) -> dict:
    meta = read_session_json(account_id)
    if not meta:
        account_dict["has_session_json"] = False
        return account_dict

    account_dict["has_session_json"] = True
    phone = meta.get("phone") or meta.get("phoneNumber") or ""
    if phone and not account_dict.get("phone"):
        account_dict["phone"] = str(phone).lstrip("+")
    account_dict["has_two_fa_hint"] = bool(session_two_fa(meta))
    return account_dict
