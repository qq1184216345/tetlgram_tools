from __future__ import annotations

import json
from pathlib import Path

from backend.config import DATA_DIR
from backend.storage.account_ads import has_account_ad

META_FILE = DATA_DIR / "accounts_meta.json"


def _load() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    META_FILE.parent.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_meta(account_id: str) -> dict:
    return _load().get(account_id, {})


def set_meta(account_id: str, **fields) -> dict:
    data = _load()
    entry = data.get(account_id, {})
    entry.update(fields)
    data[account_id] = entry
    _save(data)
    return entry


def get_proxy(account_id: str) -> str:
    return get_meta(account_id).get("proxy", "")


def set_proxy(account_id: str, proxy: str) -> None:
    set_meta(account_id, proxy=proxy)


def increment_broadcast_success(account_id: str, count: int = 1) -> int:
    entry = get_meta(account_id)
    total = int(entry.get("broadcast_success", 0)) + count
    set_meta(account_id, broadcast_success=total, broadcast_status="running")
    return total


def set_join_status(account_id: str, status: str) -> None:
    set_meta(account_id, join_status=status)


def set_broadcast_status(account_id: str, status: str) -> None:
    set_meta(account_id, broadcast_status=status)


def enrich_account(account_id: str, account_dict: dict) -> dict:
    meta = get_meta(account_id)
    account_dict["proxy"] = meta.get("proxy", account_dict.get("proxy", ""))
    account_dict["join_status"] = meta.get("join_status", "")
    account_dict["broadcast_status"] = meta.get("broadcast_status", "")
    account_dict["broadcast_success_count"] = int(meta.get("broadcast_success", 0))
    account_dict["has_custom_ad"] = has_account_ad(account_id)
    return account_dict
