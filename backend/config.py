from pathlib import Path
import json
import os
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.storage.config_store import load_app_config, save_app_config


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal = exe_dir / "_internal"
        if (internal / "config" / "ports.json").exists():
            return internal
        return exe_dir
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _resolve_project_root()
PORTS_FILE = PROJECT_ROOT / "config" / "ports.json"
PORTS = json.loads(PORTS_FILE.read_text(encoding="utf-8"))

DATA_DIR = Path(
    os.environ.get("PAPERWING_DATA")
    or os.environ.get("TELEGRAM_TOOLS_DATA")
    or (PROJECT_ROOT / "data")
)
SESSIONS_DIR = DATA_DIR / "sessions"
IMPORT_OK_DIR = DATA_DIR / "导入账号" / "ok"
IMPORT_ERROR_DIR = DATA_DIR / "导入账号" / "error"
PROFILE_DIR = DATA_DIR / "配置"
SCRAPE_DIR = DATA_DIR / "采集"
LOG_DIR = DATA_DIR / "日志"

for directory in (
    SESSIONS_DIR,
    IMPORT_OK_DIR,
    IMPORT_ERROR_DIR,
    PROFILE_DIR,
    SCRAPE_DIR,
    LOG_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

_saved = load_app_config()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = PORTS["backend"]["host"]
    port: int = PORTS["backend"]["port"]
    api_id: int = _saved.get("api_id", 0)
    api_hash: str = _saved.get("api_hash", "")
    socks5_ip: str = _saved.get("socks5_ip", "")
    socks5_port: int = _saved.get("socks5_port", 0)
    proxy_state: bool = _saved.get("proxy_state", False)
    proxy_type: str = _saved.get("proxy_type", "socks5")
    proxy_list: str = _saved.get("proxy_list", "")
    use_system_proxy: bool = _saved.get("use_system_proxy", False)
    success_account_path: str = _saved.get("success_account_path", "")
    failed_account_path: str = _saved.get("failed_account_path", "")
    ai_api_url: str = _saved.get("ai_api_url", "")
    ai_api_key: str = _saved.get("ai_api_key", "")
    ai_model: str = _saved.get("ai_model", "gpt-4o-mini")
    ai_verify_enabled: bool = _saved.get("ai_verify_enabled", False)
    device_profile: str = _saved.get("device_profile", "apple_desktop")

    def persist(self) -> None:
        save_app_config(
            {
                "api_id": self.api_id,
                "api_hash": self.api_hash,
                "socks5_ip": self.socks5_ip,
                "socks5_port": self.socks5_port,
                "proxy_state": self.proxy_state,
                "proxy_type": self.proxy_type,
                "proxy_list": self.proxy_list,
                "use_system_proxy": self.use_system_proxy,
                "success_account_path": self.success_account_path,
                "failed_account_path": self.failed_account_path,
                "ai_api_url": self.ai_api_url,
                "ai_api_key": self.ai_api_key,
                "ai_model": self.ai_model,
                "ai_verify_enabled": self.ai_verify_enabled,
                "device_profile": self.device_profile,
            }
        )


settings = Settings()