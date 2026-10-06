from __future__ import annotations

import random
import string


def pick_message_variant(message: str, multi_line_mode: bool) -> str:
    parts = [part.strip() for part in message.split("***") if part.strip()]
    if len(parts) <= 1:
        return message.strip()

    if multi_line_mode:
        return random.choice(parts)

    lines: list[str] = []
    for part in parts:
        lines.extend(line.strip() for line in part.splitlines() if line.strip())
    return random.choice(lines) if lines else message.strip()


def add_random_padding(message: str, prefix_len: int, suffix_len: int) -> str:
    alphabet = string.ascii_letters + string.digits
    prefix = "".join(random.choices(alphabet, k=prefix_len)) if prefix_len > 0 else ""
    suffix = "".join(random.choices(alphabet, k=suffix_len)) if suffix_len > 0 else ""
    if not prefix and not suffix:
        return message
    return f"{prefix}{message}{suffix}"
