from __future__ import annotations

API_PRESETS: dict[str, dict[str, object]] = {
    "custom": {
        "label": "自定义（my.telegram.org）",
        "api_id": 0,
        "api_hash": "",
    },
    "telegram_desktop": {
        "label": "Telegram Desktop",
        "api_id": 2040,
        "api_hash": "b18441a1ff607e10a989891a5462e627",
    },
    "telegram_android": {
        "label": "Telegram Android",
        "api_id": 6,
        "api_hash": "eb06d4abfb49dc3eeb1aeb98ae0f581e",
    },
    "telegram_ios": {
        "label": "Telegram iOS",
        "api_id": 10840,
        "api_hash": "33c45224029d59cb3ad0c16134215aeb",
    },
}


def list_api_presets() -> list[dict[str, object]]:
    return [
        {"id": key, **value}
        for key, value in API_PRESETS.items()
    ]
