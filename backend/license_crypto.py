"""本机授权缓存加密：机器绑定密钥 + 应用盐，防明文篡改。"""
from __future__ import annotations

import base64
import hashlib
import os
import platform
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

# 应用内盐（发行版可再混淆；配合机器指纹，非绝对防破解）
_APP_SALT = b"paperwing-license-cache-v1-zhiyin"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    machine = "|".join(
        [
            platform.node(),
            platform.system(),
            platform.machine(),
            os.environ.get("USERNAME") or os.environ.get("USER") or "user",
            os.environ.get("COMPUTERNAME") or "",
        ]
    )
    digest = hashlib.sha256(_APP_SALT + machine.encode("utf-8", errors="ignore")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_text(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise ValueError("授权缓存解密失败") from exc
