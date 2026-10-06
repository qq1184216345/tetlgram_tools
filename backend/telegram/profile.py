from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError, UsernameInvalidError, UsernameOccupiedError
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest

from backend.config import PROFILE_DIR
from backend.telegram.task_utils import AccountIntervalGate


def _read_lines(filename: str) -> list[str]:
    path = PROFILE_DIR / filename
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _pick_random(filename: str, fallback: str = "") -> str:
    lines = _read_lines(filename)
    return random.choice(lines) if lines else fallback


def _pick_avatar() -> Path | None:
    avatars = list(PROFILE_DIR.glob("*.jpg")) + list(PROFILE_DIR.glob("*.png"))
    return random.choice(avatars) if avatars else None


async def update_account_profile(
    client: TelegramClient,
    first_name: str = "",
    last_name: str = "",
    about: str = "",
    username: str = "",
    avatar_path: Path | None = None,
    update_first_name: bool = False,
    update_last_name: bool = False,
    update_about: bool = False,
    update_username: bool = False,
    update_avatar: bool = False,
) -> None:
    profile_kwargs: dict[str, str | None] = {}
    if update_first_name:
        profile_kwargs["first_name"] = first_name or None
    if update_last_name:
        profile_kwargs["last_name"] = last_name or None
    if update_about:
        profile_kwargs["about"] = about or None

    if profile_kwargs:
        await client(UpdateProfileRequest(**profile_kwargs))

    if update_username and username:
        clean = username.lstrip("@")
        await client(UpdateUsernameRequest(clean))

    if update_avatar and avatar_path and avatar_path.exists():
        uploaded = await client.upload_file(str(avatar_path))
        await client(UploadProfilePhotoRequest(file=uploaded))


async def update_account_password(
    client: TelegramClient,
    old_password: str,
    new_password: str,
    remove_2fa: bool = False,
) -> None:
    if remove_2fa:
        if not old_password:
            raise ValueError("清除二级密码需要填写当前密码")
        await client.edit_2fa(
            current_password=old_password,
            new_password=None,
        )
        return
    await client.edit_2fa(
        current_password=old_password or None,
        new_password=new_password,
    )


async def run_profile_update_loop(
    account_ids: list[str],
    use_random_config: bool,
    update_first_name: bool,
    update_last_name: bool,
    update_about: bool,
    update_username: bool,
    update_avatar: bool,
    update_password: bool,
    first_name: str,
    last_name: str,
    about: str,
    username: str,
    old_password: str,
    new_password: str,
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    on_progress: Callable[[int, int, int], None],
    should_stop: Callable[[], bool],
    interval_min: int = 5,
    interval_max: int = 15,
    remove_2fa: bool = False,
) -> None:
    total = len(account_ids)
    success = 0
    failed = 0
    gate = AccountIntervalGate(interval_min, interval_max)

    for index, account_id in enumerate(account_ids):
        if should_stop():
            break
        if await gate.wait_turn(account_id, should_stop, on_log):
            break

        try:
            client = await get_client(account_id)

            fn = _pick_random("名字.txt", first_name) if use_random_config else first_name
            ln = _pick_random("姓氏.txt", last_name) if use_random_config else last_name
            bio = _pick_random("简介.txt", about) if use_random_config else about
            uname = _pick_random("用户名.txt", username) if use_random_config else username
            avatar = _pick_avatar() if (use_random_config and update_avatar) else None

            if not use_random_config and update_avatar:
                avatars = list(PROFILE_DIR.glob("*.jpg")) + list(PROFILE_DIR.glob("*.png"))
                avatar = avatars[0] if avatars else None

            has_profile_change = any(
                [
                    update_first_name,
                    update_last_name,
                    update_about,
                    update_username,
                    update_avatar,
                ]
            )
            if has_profile_change:
                await update_account_profile(
                    client,
                    first_name=fn,
                    last_name=ln,
                    about=bio,
                    username=uname,
                    avatar_path=avatar,
                    update_first_name=update_first_name,
                    update_last_name=update_last_name,
                    update_about=update_about,
                    update_username=update_username,
                    update_avatar=update_avatar,
                )

            if remove_2fa:
                await update_account_password(client, old_password, "", remove_2fa=True)
                on_log("success", f"[{account_id}] 已清除二级密码")
            elif update_password and new_password:
                await update_account_password(client, old_password, new_password)
                on_log("success", f"[{account_id}] 二级密码已更新")

            if has_profile_change:
                parts = []
                if update_first_name and fn:
                    parts.append(fn)
                if update_last_name and ln:
                    parts.append(ln)
                if update_username and uname:
                    parts.append(f"@{uname.lstrip('@')}")
                on_log(
                    "success",
                    f"[{account_id}] 资料已更新"
                    + (f": {' '.join(parts)}" if parts else ""),
                )
            elif not update_password and not remove_2fa:
                on_log("warn", f"[{account_id}] 未勾选任何修改项")

            success += 1
        except UsernameOccupiedError:
            failed += 1
            on_log("error", f"[{account_id}] 用户名已被占用")
            gate.arm(account_id)
        except UsernameInvalidError:
            failed += 1
            on_log("error", f"[{account_id}] 用户名格式无效")
            gate.arm(account_id)
        except FloodWaitError as exc:
            failed += 1
            on_log("warn", f"[{account_id}] 频繁限制 {exc.seconds}s，其它号继续")
            gate.block_for(account_id, exc.seconds)
        except Exception as exc:
            failed += 1
            on_log("error", f"[{account_id}] 更新失败: {exc}")
            gate.arm(account_id)
        else:
            gate.arm(account_id)

        on_progress(index + 1, success, failed)
