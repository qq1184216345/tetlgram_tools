from __future__ import annotations

from backend.config import PROFILE_DIR

ACCOUNT_ADS_DIR = PROFILE_DIR / "账号独立广告语"


def _ad_path(account_id: str) -> str:
    ACCOUNT_ADS_DIR.mkdir(parents=True, exist_ok=True)
    return str(ACCOUNT_ADS_DIR / f"{account_id}.txt")


def has_account_ad(account_id: str) -> bool:
    path = ACCOUNT_ADS_DIR / f"{account_id}.txt"
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def get_account_ad(account_id: str) -> str | None:
    path = ACCOUNT_ADS_DIR / f"{account_id}.txt"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def set_account_ad(account_id: str, message: str) -> None:
    ACCOUNT_ADS_DIR.mkdir(parents=True, exist_ok=True)
    path = ACCOUNT_ADS_DIR / f"{account_id}.txt"
    content = message.strip()
    if content:
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def delete_account_ad(account_id: str) -> None:
    path = ACCOUNT_ADS_DIR / f"{account_id}.txt"
    if path.exists():
        path.unlink()
