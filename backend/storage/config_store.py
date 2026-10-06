import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _config_file() -> Path:
    data_dir = Path(
        os.environ.get("PAPERWING_DATA")
        or os.environ.get("TELEGRAM_TOOLS_DATA")
        or (PROJECT_ROOT / "data")
    )
    return data_dir / "config.json"


def load_app_config() -> dict:
    path = _config_file()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_app_config(data: dict) -> None:
    path = _config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
