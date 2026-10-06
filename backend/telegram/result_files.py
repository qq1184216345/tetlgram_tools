from __future__ import annotations
from datetime import datetime
from pathlib import Path
from backend.config import LOG_DIR
def format_caihong_timestamp(dt: datetime | None = None) -> str:
    """竞品格式：2026年8月30日20时21分45秒"""
    now = dt or datetime.now()
    return f"{now.year}年{now.month}月{now.day}日{now.hour}时{now.minute}分{now.second}秒"
def normalize_result_target(target: str) -> str:
    """用户名尽量写成 @xxx，链接/手机号原样保留。"""
    raw = (target or "").strip()
    if not raw:
        return raw
    if raw.startswith(("@", "+", "http://", "https://", "t.me/")):
        return raw
    if raw.isdigit() or (raw.startswith("+") and raw[1:].isdigit()):
        return raw
    # 纯用户名补 @
    if "/" not in raw and " " not in raw:
        return f"@{raw}"
    return raw
def append_result_line(
    filename: str,
    target: str,
    *,
    with_timestamp: bool = False,
    extra: str = "",
) -> Path:
    """Append one target to LOG_DIR/<filename>.
    竞品默认行格式：
      2026年8月30日20时21分45秒:@user
    无时间戳时仅写目标；失败文件不写原因（extra 忽略，与竞品一致）。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / filename
    target_text = normalize_result_target(target)
    if with_timestamp:
        line = f"{format_caihong_timestamp()}:{target_text}\n"
    else:
        # 兼容旧调用：无时间戳时可附带 extra（制表符分隔）
        if extra.strip():
            line = f"{target_text}\t{extra.strip()}\n"
        else:
            line = f"{target_text}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return path
