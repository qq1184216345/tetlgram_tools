from __future__ import annotations

from telethon import TelegramClient
from telethon.tl.functions.channels import EditAdminRequest
from telethon.tl.functions.messages import EditChatAdminRequest
from telethon.tl.types import Channel, Chat, ChatAdminRights

from backend.telegram.utils import resolve_entity


def _invite_rights() -> ChatAdminRights:
    return ChatAdminRights(
        change_info=False,
        post_messages=False,
        edit_messages=False,
        delete_messages=False,
        ban_users=False,
        invite_users=True,
        pin_messages=False,
        add_admins=False,
        anonymous=False,
        manage_call=False,
        other=False,
        manage_topics=False,
    )


def _empty_rights() -> ChatAdminRights:
    return ChatAdminRights(
        change_info=False,
        post_messages=False,
        edit_messages=False,
        delete_messages=False,
        ban_users=False,
        invite_users=False,
        pin_messages=False,
        add_admins=False,
        anonymous=False,
        manage_call=False,
        other=False,
        manage_topics=False,
    )


async def set_account_admin(
    admin_client: TelegramClient,
    group_link: str,
    target_user,
    *,
    promote: bool,
    rank: str = "拉人",
) -> None:
    group = await resolve_entity(admin_client, group_link)
    if isinstance(group, Channel):
        rights = _invite_rights() if promote else _empty_rights()
        await admin_client(
            EditAdminRequest(
                channel=group,
                user_id=target_user,
                admin_rights=rights,
                rank=rank if promote else "",
            )
        )
        return

    if isinstance(group, Chat):
        await admin_client(
            EditChatAdminRequest(
                chat_id=group.id,
                user_id=target_user,
                is_admin=promote,
            )
        )
        return

    raise ValueError("目标不是可用的群组/超级群")


async def batch_set_invite_admins(
    admin_client: TelegramClient,
    group_link: str,
    member_clients: list[tuple[str, TelegramClient]],
    *,
    promote: bool,
) -> list[dict]:
    """Promote/demote logged-in accounts. Returns per-account results."""
    results: list[dict] = []
    me_cache: dict[str, object] = {}

    for account_id, client in member_clients:
        try:
            if account_id not in me_cache:
                me_cache[account_id] = await client.get_me()
            user = me_cache[account_id]
            await set_account_admin(admin_client, group_link, user, promote=promote)
            results.append(
                {
                    "account_id": account_id,
                    "ok": True,
                    "message": "已设为管理员（可拉人）" if promote else "已取消管理员",
                }
            )
        except Exception as exc:
            results.append(
                {"account_id": account_id, "ok": False, "message": str(exc)[:200]}
            )
    return results
