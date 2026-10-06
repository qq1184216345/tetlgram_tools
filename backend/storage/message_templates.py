from __future__ import annotations

import json
from pathlib import Path

from backend.config import DATA_DIR

TEMPLATE_FILE = DATA_DIR / "message_templates.json"


def load_templates() -> dict:
    if TEMPLATE_FILE.exists():
        return json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
    return {"broadcast": "", "dm": ""}


def save_templates(data: dict) -> None:
    TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
