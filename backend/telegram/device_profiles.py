from __future__ import annotations

"""登录端设备指纹预设（影响 TelegramClient 上报的 device/system/app 信息）。"""

DEVICE_PROFILES: dict[str, dict[str, str]] = {
    "default": {
        "label": "默认（Telethon）",
        "device_model": "PC 64bit",
        "system_version": "Windows 10",
        "app_version": "1.0",
        "lang_code": "en",
        "system_lang_code": "en",
    },
    "apple_desktop": {
        "label": "苹果桌面（推荐）",
        "device_model": "MacBook Pro",
        "system_version": "macOS 14.5",
        "app_version": "5.3.1 x64",
        "lang_code": "en",
        "system_lang_code": "en-US",
    },
    "windows_desktop": {
        "label": "Windows 桌面",
        "device_model": "Desktop",
        "system_version": "Windows 11",
        "app_version": "5.3.1 x64",
        "lang_code": "en",
        "system_lang_code": "en-US",
    },
    "android": {
        "label": "Android 手机",
        "device_model": "Samsung SM-S911B",
        "system_version": "SDK 34",
        "app_version": "10.14.5",
        "lang_code": "en",
        "system_lang_code": "en-US",
    },
    "ios": {
        "label": "iPhone",
        "device_model": "iPhone 15 Pro",
        "system_version": "17.5.1",
        "app_version": "10.14.5",
        "lang_code": "en",
        "system_lang_code": "en-US",
    },
}


def list_device_profiles() -> list[dict[str, object]]:
    return [
        {
            "id": key,
            "label": value["label"],
            "device_model": value["device_model"],
            "system_version": value["system_version"],
            "app_version": value["app_version"],
        }
        for key, value in DEVICE_PROFILES.items()
    ]


def resolve_device_profile(profile_id: str | None = None) -> dict[str, str]:
    from backend.config import settings

    key = (profile_id or getattr(settings, "device_profile", "") or "apple_desktop").strip()
    if key not in DEVICE_PROFILES:
        key = "apple_desktop"
    profile = DEVICE_PROFILES[key]
    return {
        "device_model": profile["device_model"],
        "system_version": profile["system_version"],
        "app_version": profile["app_version"],
        "lang_code": profile["lang_code"],
        "system_lang_code": profile["system_lang_code"],
    }


def client_device_kwargs(profile_id: str | None = None) -> dict[str, str]:
    """kwargs 可直接传给 TelegramClient(...)."""
    return resolve_device_profile(profile_id)
