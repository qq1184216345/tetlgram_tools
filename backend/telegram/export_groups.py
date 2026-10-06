from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable
from telethon import TelegramClient
from telethon.tl.functions.chatlists import ExportChatlistInviteRequest
from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
from telethon.tl.types import (
    Channel,
    Chat,
    DialogFilterChatlist,
    InputChatlistDialogFilter,
    TextWithEntities,
)
from backend.config import SCRAPE_DIR
def _account_tag(account_id: str) -> str:
    return "".join(ch for ch in account_id if ch.isalnum() or ch in "-_") or "account"
def dialog_is_group(entity) -> bool:
    """普通群 / 超级群，不含广播频道。"""
    if isinstance(entity, Chat):
        return True
    return isinstance(entity, Channel) and bool(getattr(entity, "megagroup", False))


async def iter_joined_group_targets(client: TelegramClient):
    """边扫会话边产出已加入群组目标，扫到第一个群就能立刻发。"""
    from telethon.utils import get_peer_id

    seen: set[str] = set()
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not dialog_is_group(entity):
            continue
        username = (getattr(entity, "username", "") or "").strip()
        ref = f"@{username}" if username else str(get_peer_id(entity))
        if ref in seen:
            continue
        seen.add(ref)
        yield ref


async def list_joined_group_targets(client: TelegramClient) -> list[str]:
    """账号已加入群组的发送目标：有用户名用 @name，否则用 Telethon peer id。"""
    return [ref async for ref in iter_joined_group_targets(client)]


async def collect_account_groups(client: TelegramClient) -> list[dict]:
    """收集账号已加入的群/超级群/频道（含无公开用户名的）。"""
    rows: list[dict] = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not isinstance(entity, (Channel, Chat)):
            continue
        title = dialog.title or getattr(entity, "title", "") or ""
        username = getattr(entity, "username", "") or ""
        link = f"https://t.me/{username}" if username else ""
        rows.append(
            {
                "title": title,
                "link": link,
                "username": username,
                "id": entity.id,
                "entity": entity,
            }
        )
    return rows
def write_all_groups_file(account_id: str, rows: list[dict]) -> Path:
    """竞品格式：有公开链则写链接，否则只写标题；标题与链接分行。"""
    SCRAPE_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRAPE_DIR / f"导出{_account_tag(account_id)}.txt"
    lines: list[str] = []
    for row in rows:
        title = (row.get("title") or "").strip()
        link = (row.get("link") or "").strip()
        if title:
            lines.append(title)
        if link:
            lines.append(link)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path
async def create_addlist_invite(
    client: TelegramClient,
    peers_entities: list,
    *,
    title: str = "一键加群",
) -> str:
    """创建聊天文件夹并导出 https://t.me/addlist/xxx 邀请链。"""
    if not peers_entities:
        raise ValueError("没有可导出的公开群/频道（需要有 username）")
    input_peers = []
    for entity in peers_entities:
        try:
            input_peers.append(await client.get_input_entity(entity))
        except Exception:
            continue
    if not input_peers:
        raise ValueError("无法解析群实体")
    filters_raw = await client(GetDialogFiltersRequest())
    items = getattr(filters_raw, "filters", filters_raw)
    if not isinstance(items, (list, tuple)):
        items = []
    used_ids = set()
    for item in items:
        fid = getattr(item, "id", None)
        if isinstance(fid, int):
            used_ids.add(fid)
    filter_id = 2
    while filter_id in used_ids:
        filter_id += 1
    chatlist = DialogFilterChatlist(
        id=filter_id,
        title=TextWithEntities(text=title[:12] or "一键加群", entities=[]),
        pinned_peers=[],
        include_peers=input_peers[:100],
    )
    await client(UpdateDialogFilterRequest(id=filter_id, filter=chatlist))
    exported = await client(
        ExportChatlistInviteRequest(
            chatlist=InputChatlistDialogFilter(filter_id=filter_id),
            title=title[:12] or "一键加群",
            peers=input_peers[:100],
        )
    )
    invite = getattr(exported, "invite", None) or exported
    url = getattr(invite, "url", "") or ""
    if not url:
        raise ValueError("导出 addlist 失败：未返回邀请链接")
    return url
async def export_account_groups(
    account_ids: list[str],
    get_client: Callable[[str], Awaitable[TelegramClient]],
    on_log: Callable[[str, str], None],
    *,
    mode: str = "all",
) -> dict:
    """mode=all|addlist|both。返回各账号产物路径。"""
    outputs: dict[str, dict] = {}
    for account_id in account_ids:
        client = await get_client(account_id)
        rows = await collect_account_groups(client)
        on_log("info", f"[{account_id}] 已加入对话 {len(rows)} 个（群/频道）")
        result: dict = {"count": len(rows)}
        if mode in ("all", "both"):
            all_path = write_all_groups_file(account_id, rows)
            result["all_file"] = str(all_path)
            on_log("success", f"[{account_id}] 全部群链接已保存: {all_path}")
        if mode in ("addlist", "both"):
            public_entities = [r["entity"] for r in rows if r.get("username")]
            if not public_entities:
                on_log("warn", f"[{account_id}] 无公开用户名群，无法生成 addlist")
                result["addlist_error"] = "无公开用户名群"
            else:
                try:
                    url = await create_addlist_invite(
                        client,
                        public_entities,
                        title=f"导出{datetime.now().strftime('%m%d')}",
                    )
                    group_path = SCRAPE_DIR / f"导出{_account_tag(account_id)}_分组.txt"
                    group_path.write_text(url + "\n", encoding="utf-8")
                    result["addlist_url"] = url
                    result["addlist_file"] = str(group_path)
                    on_log("success", f"[{account_id}] 一键加群链接: {url}")
                    on_log("info", f"[{account_id}] 已保存: {group_path}")
                except Exception as exc:
                    result["addlist_error"] = str(exc)
                    on_log("error", f"[{account_id}] 导出 addlist 失败: {exc}")
        outputs[account_id] = result
    return outputs
