from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional

from backend.models.schemas import (
    BroadcastTaskRequest,
    ChannelCommentTaskRequest,
    CloneChannelTaskRequest,
    DmTaskRequest,
    FilterGroupsTaskRequest,
    InviteTaskRequest,
    JoinGroupTaskRequest,
    LeaveGroupsTaskRequest,
    MonitorTaskRequest,
    ProfileUpdateTaskRequest,
    ScrapeGroupsTaskRequest,
    ScrapeMembersTaskRequest,
    ExtractLinksTaskRequest,
    ScrapeProfilesTaskRequest,
    WarmGroupTaskRequest,
    TaskInfo,
    TaskLogEntry,
    TaskProgress,
    TaskStatus,
    TaskType,
)
from backend.telegram.broadcast import run_broadcast_loop
from backend.telegram.task_utils import account_target_key
from backend.telegram.client_manager import client_manager
from backend.telegram.dm import run_dm_loop
from backend.telegram.extract_links import run_extract_links_loop
from backend.telegram.filter_groups import run_filter_groups_loop
from backend.telegram.invite import run_invite_loop
from backend.telegram.join_group import run_join_group_loop
from backend.telegram.leave_groups import run_leave_groups_loop
from backend.telegram.monitor import run_monitor_loop
from backend.telegram.profile import run_profile_update_loop
from backend.telegram.scrape import run_scrape_groups_loop, run_scrape_members_loop
from backend.telegram.scrape_profiles import run_scrape_profiles_loop
from backend.telegram.warm_group import run_warm_group_loop


@dataclass
class TaskCheckpoint:
    task_type: TaskType
    done: set[str] = field(default_factory=set)
    success: int = 0
    failed: int = 0


@dataclass
class RunningTask:
    info: TaskInfo
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    asyncio_task: Optional[asyncio.Task] = None
    done: set[str] = field(default_factory=set)
    stop_as_pause: bool = False

    def __post_init__(self) -> None:
        self.pause_event.set()


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, RunningTask] = {}
        self._checkpoints: dict[TaskType, TaskCheckpoint] = {}

    def list_tasks(self) -> list[TaskInfo]:
        items = []
        for task in self._tasks.values():
            task.info.resumable = task.info.type in self._checkpoints
            items.append(task.info)
        return items

    def get_task(self, task_id: str) -> TaskInfo | None:
        running = self._tasks.get(task_id)
        if not running:
            return None
        running.info.resumable = running.info.type in self._checkpoints
        return running.info

    def _now(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _log(self, running: RunningTask, level: str, message: str) -> None:
        entry = TaskLogEntry(time=self._now(), level=level, message=message)
        running.info.logs.append(entry)
        if len(running.info.logs) > 500:
            running.info.logs = running.info.logs[-500:]

    async def _get_client(self, account_id: str):
        return await client_manager.ensure_connected(account_id)

    def _logged_client(self, running: RunningTask):
        seen: set[str] = set()

        async def get_client(account_id: str):
            first = account_id not in seen
            already = client_manager.is_connected(account_id)
            if first:
                if already:
                    self._log(
                        running,
                        "info",
                        f"[{account_id}] 已在线，复用连接 · {client_manager.account_display(account_id)}",
                    )
                else:
                    self._log(running, "info", f"[{account_id}] 正在连接 Telegram…")
            try:
                client = await client_manager.ensure_connected(account_id)
                if first:
                    seen.add(account_id)
                    if not already:
                        self._log(
                            running,
                            "success",
                            f"[{account_id}] 连接成功 · {client_manager.account_display(account_id)}",
                        )
                return client
            except Exception as exc:
                self._log(running, "error", f"[{account_id}] 连接失败: {exc}")
                raise

        return get_client

    def _save_checkpoint(self, running: RunningTask) -> None:
        self._checkpoints[running.info.type] = TaskCheckpoint(
            task_type=running.info.type,
            done=set(running.done),
            success=running.info.progress.success,
            failed=running.info.progress.failed,
        )
        running.info.resumable = True

    def _clear_checkpoint(self, task_type: TaskType) -> None:
        self._checkpoints.pop(task_type, None)

    def _apply_checkpoint(self, running: RunningTask) -> set[str]:
        ckpt = self._checkpoints.get(running.info.type)
        if not ckpt:
            return set()
        running.done = set(ckpt.done)
        running.info.progress.success = ckpt.success
        running.info.progress.failed = ckpt.failed
        running.info.progress.current = ckpt.success + ckpt.failed
        running.info.resumable = True
        if ckpt.done:
            self._log(
                running,
                "info",
                f"从暂停处继续，已跳过 {len(ckpt.done)} 项，本次按最新配置接着跑",
            )
        return set(ckpt.done)

    def _mark_job_done(self, running: RunningTask, key: str) -> None:
        if not key:
            return
        running.done.add(key)
        self._save_checkpoint(running)

    def _create_task(
        self, task_type: TaskType, account_ids: list[str] | None = None
    ) -> RunningTask:
        task_id = uuid.uuid4().hex[:12]
        info = TaskInfo(
            id=task_id,
            type=task_type,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            account_ids=list(account_ids or []),
        )
        running = RunningTask(info=info)
        self._tasks[task_id] = running
        return running

    async def _run_task(
        self,
        running: RunningTask,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        running.info.status = TaskStatus.RUNNING
        ids = running.info.account_ids or []
        if ids:
            preview = ", ".join(ids[:8])
            extra = f" 等 {len(ids)} 个" if len(ids) > 8 else f" · {len(ids)} 个"
            self._log(running, "info", f"任务开始{extra}：{preview}")
        else:
            self._log(running, "info", "任务开始")
        try:
            await coro_factory()
            if running.stop_as_pause:
                running.info.status = TaskStatus.PAUSED
                running.info.resumable = True
                self._save_checkpoint(running)
                self._log(running, "info", "任务已暂停，进度已保留")
            elif running.stop_event.is_set():
                running.info.status = TaskStatus.STOPPED
                self._clear_checkpoint(running.info.type)
                running.info.resumable = False
                self._log(running, "info", "任务已停止，进度已重置")
            else:
                running.info.status = TaskStatus.COMPLETED
                self._clear_checkpoint(running.info.type)
                running.info.resumable = False
                self._log(running, "success", "任务已完成")
        except Exception as exc:
            running.info.status = TaskStatus.ERROR
            running.info.error = str(exc)
            self._log(running, "error", f"任务异常: {exc}")

    def start_connect_accounts(self, account_ids: list[str]) -> TaskInfo:
        ids = [item.strip() for item in account_ids if str(item).strip()]
        if not ids:
            raise ValueError("请至少选择一个账号")

        running = self._create_task(TaskType.CONNECT_ACCOUNTS, ids)
        running.info.progress.total = len(ids)

        async def runner() -> None:
            from backend.models.schemas import AccountStatus

            self._log(running, "info", f"开始并行连接 {len(ids)} 个账号")
            success = 0
            failed = 0
            done = 0
            lock = asyncio.Lock()

            async def connect_one(account_id: str) -> None:
                nonlocal success, failed, done
                if running.stop_event.is_set():
                    return
                self._log(running, "info", f"[{account_id}] 正在连接…")
                try:
                    account = await client_manager.connect_account(account_id)
                    async with lock:
                        if account.status == AccountStatus.ONLINE:
                            success += 1
                            level, msg = (
                                "success",
                                f"[{account_id}] 连接成功 · {client_manager.account_display(account_id)}",
                            )
                        else:
                            failed += 1
                            level, msg = (
                                "error",
                                f"[{account_id}] 连接失败: {account.error or '未知错误'}",
                            )
                    self._log(running, level, msg)
                except Exception as exc:
                    async with lock:
                        failed += 1
                    self._log(running, "error", f"[{account_id}] 连接失败: {exc}")
                async with lock:
                    done += 1
                    self._update_progress(running, done, success, failed)

            await asyncio.gather(*[connect_one(account_id) for account_id in ids])
            self._log(
                running,
                "info",
                f"批量连接结束：成功 {success}，失败 {failed}，共 {len(ids)}",
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_broadcast(self, config: BroadcastTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.use_joined_groups and not config.targets:
            raise ValueError("请至少填写一个目标群组")
        if config.use_postbot and not config.postbot_code.strip():
            raise ValueError("已启用 PostBot，请填写 PostBot 代码")
        if not config.message.strip() and not (config.use_postbot and config.postbot_code.strip()):
            if config.send_mode == "contact":
                if not config.contact_target.strip():
                    raise ValueError("请填写联系人目标")
            elif config.send_mode == "forward":
                if not config.forward_message_id and not config.forward_message_links and not config.forward_channel.strip():
                    raise ValueError("请提供频道消息链接")
            else:
                raise ValueError("消息内容不能为空")

        running = self._create_task(TaskType.BROADCAST, config.account_ids)
        skip_keys = self._apply_checkpoint(running)
        init_ok = running.info.progress.success
        init_fail = running.info.progress.failed
        # 每个勾选账号都对全部目标发送；全部已加入群时总数在任务内统计
        if config.use_joined_groups:
            running.info.progress.total = 0
        else:
            running.info.progress.total = len(config.account_ids) * len(config.targets)

        async def runner() -> None:
            await run_broadcast_loop(
                account_ids=config.account_ids,
                targets=config.targets,
                use_joined_groups=config.use_joined_groups,
                message=config.message,
                parse_mode=config.parse_mode,
                interval_min=config.interval_min,
                interval_max=config.interval_max,
                auto_join=config.auto_join,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                on_set_total=lambda total: self._set_progress_total(running, total),
                should_stop=running.stop_event.is_set,
                use_rich_tags=config.use_rich_tags and not config.use_postbot,
                use_postbot=config.use_postbot,
                postbot_code=config.postbot_code,
                send_mode=config.send_mode,
                media_path=config.media_path,
                forward_channel=config.forward_channel,
                forward_message_id=config.forward_message_id,
                forward_message_links=config.forward_message_links,
                forward_hide_source=config.forward_hide_source,
                multi_line_mode=config.multi_line_mode,
                random_prefix_len=config.random_prefix_len,
                random_suffix_len=config.random_suffix_len,
                thread_count=config.thread_count,
                pause_event=running.pause_event,
                start_hour=config.start_hour,
                end_hour=config.end_hour,
                auto_spambot_unban=config.auto_spambot_unban,
                no_duplicate_join=config.no_duplicate_join,
                random_order=config.random_order,
                round_rest_min=config.round_rest_min,
                round_rest_max=config.round_rest_max,
                exit_muted_groups=config.exit_muted_groups,
                combined_send=config.combined_send,
                contact_target=config.contact_target,
                contact_first_name=config.contact_first_name,
                contact_last_name=config.contact_last_name,
                auto_delete_after_sec=config.auto_delete_after_sec,
                remove_muted_accounts=config.remove_muted_accounts,
                on_remove_account=client_manager.delete_account if config.remove_muted_accounts else None,
                guest_mode=config.guest_mode,
                schedule_start_at=config.schedule_start_at,
                schedule_end_at=config.schedule_end_at,
                skip_keys=skip_keys,
                initial_success=init_ok,
                initial_failed=init_fail,
                on_job_done=lambda aid, target: self._mark_job_done(
                    running, account_target_key(aid, target)
                ),
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_join_group(self, config: JoinGroupTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.targets:
            raise ValueError("请至少填写一个群组链接")

        running = self._create_task(TaskType.JOIN_GROUP, config.account_ids)
        skip_keys = self._apply_checkpoint(running)
        init_ok = running.info.progress.success
        init_fail = running.info.progress.failed
        if config.no_duplicate_join:
            running.info.progress.total = len(config.targets)
        else:
            running.info.progress.total = len(config.account_ids) * len(config.targets)

        async def runner() -> None:
            await run_join_group_loop(
                account_ids=config.account_ids,
                targets=config.targets,
                interval_min=config.interval_min,
                interval_max=config.interval_max,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                pause_event=running.pause_event,
                start_hour=config.start_hour,
                end_hour=config.end_hour,
                no_duplicate_join=config.no_duplicate_join,
                request_join=config.request_join,
                auto_pass_verify=config.auto_pass_verify,
                schedule_start_at=config.schedule_start_at,
                schedule_end_at=config.schedule_end_at,
                thread_count=config.thread_count,
                skip_keys=skip_keys,
                initial_success=init_ok,
                initial_failed=init_fail,
                on_job_done=lambda key: self._mark_job_done(running, key),
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_dm(self, config: DmTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.targets:
            raise ValueError("请至少填写一个目标用户")
        if config.use_postbot and not config.postbot_code.strip():
            raise ValueError("已启用 PostBot，请填写 PostBot 代码")
        if not config.message.strip() and not (config.use_postbot and config.postbot_code.strip()):
            if config.send_mode == "contact":
                if not config.contact_target.strip():
                    raise ValueError("请填写联系人目标")
            elif config.send_mode == "forward":
                if not config.forward_message_id and not config.forward_message_links and not config.forward_channel.strip():
                    raise ValueError("请提供频道消息链接")
            else:
                raise ValueError("消息内容不能为空")

        running = self._create_task(TaskType.DM, config.account_ids)
        # 每个勾选账号都对全部目标发送
        running.info.progress.total = len(config.account_ids) * len(config.targets)

        async def runner() -> None:
            from backend.models.schemas import TaskFailedItem

            items = await run_dm_loop(
                account_ids=config.account_ids,
                targets=config.targets,
                message=config.message,
                parse_mode=config.parse_mode,
                interval_min=config.interval_min,
                interval_max=config.interval_max,
                use_rich_tags=config.use_rich_tags and not config.use_postbot,
                use_postbot=config.use_postbot,
                postbot_code=config.postbot_code,
                send_mode=config.send_mode,
                media_path=config.media_path,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                multi_line_mode=config.multi_line_mode,
                random_prefix_len=config.random_prefix_len,
                random_suffix_len=config.random_suffix_len,
                thread_count=config.thread_count,
                pause_event=running.pause_event,
                start_hour=config.start_hour,
                end_hour=config.end_hour,
                auto_spambot_unban=config.auto_spambot_unban,
                target_type=config.target_type,
                forward_channel=config.forward_channel,
                forward_message_id=config.forward_message_id,
                forward_message_links=config.forward_message_links,
                forward_hide_source=config.forward_hide_source,
                contact_target=config.contact_target,
                contact_first_name=config.contact_first_name,
                contact_last_name=config.contact_last_name,
                voice_call=config.voice_call,
                save_result_files=config.save_result_files,
                result_with_timestamp=config.result_with_timestamp,
                schedule_start_at=config.schedule_start_at,
                schedule_end_at=config.schedule_end_at,
            )
            running.info.failed_items = [
                TaskFailedItem(
                    target=str(i.get("target", "")),
                    reason=str(i.get("reason", "")),
                    account_id=str(i.get("account_id", "")),
                )
                for i in (items or [])
            ]
            if config.save_result_files:
                from backend.config import LOG_DIR
                from backend.telegram.dm import DM_FAIL_FILE, DM_SUCCESS_FILE

                running.info.result_file = str(LOG_DIR / DM_SUCCESS_FILE)
                self._log(
                    running,
                    "info",
                    f"结果已写入 {LOG_DIR / DM_SUCCESS_FILE} / {LOG_DIR / DM_FAIL_FILE}",
                )
            if running.info.failed_items:
                self._log(
                    running,
                    "warn",
                    f"失败明细 {len(running.info.failed_items)} 条，可在右侧列表查看并重试",
                )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_scrape_members(self, config: ScrapeMembersTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.group_links:
            raise ValueError("请至少填写一个群组链接")

        running = self._create_task(TaskType.SCRAPE_MEMBERS, config.account_ids)
        running.info.progress.total = len(config.group_links)

        async def runner() -> None:
            output = await run_scrape_members_loop(
                account_ids=config.account_ids,
                group_links=config.group_links,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                active_days=config.active_days,
                require_name=config.require_name,
                hidden_group_mode=config.hidden_group_mode,
                message_limit=config.message_limit,
                save_path=config.save_path,
            )
            running.info.result_file = output

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_scrape_groups(self, config: ScrapeGroupsTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.keywords:
            raise ValueError("请至少填写一个搜索关键词")

        running = self._create_task(TaskType.SCRAPE_GROUPS, config.account_ids)
        running.info.progress.total = len(config.keywords)

        async def runner() -> None:
            output = await run_scrape_groups_loop(
                account_ids=config.account_ids,
                keywords=config.keywords,
                bot_username=config.bot_username,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                min_members=config.min_members,
                filter_channels=config.filter_channels,
                save_path=config.save_path,
                thread_count=config.thread_count,
            )
            running.info.result_file = output

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_invite(self, config: InviteTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.group_link.strip():
            raise ValueError("请填写目标群组")
        if not config.user_targets:
            raise ValueError("请至少填写一个目标用户")

        running = self._create_task(TaskType.INVITE, config.account_ids)
        running.info.progress.total = len(config.user_targets)

        async def runner() -> None:
            await run_invite_loop(
                account_ids=config.account_ids,
                group_link=config.group_link,
                user_targets=config.user_targets,
                interval_min=config.interval_min,
                interval_max=config.interval_max,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                make_public=config.make_public,
                account_loop_count=config.account_loop_count,
                stop_after_n=config.stop_after_n,
                thread_count=config.thread_count,
                save_result_files=config.save_result_files,
                result_with_timestamp=config.result_with_timestamp,
            )
            if config.save_result_files:
                from backend.config import LOG_DIR
                from backend.telegram.invite import INVITE_FAIL_FILE, INVITE_SUCCESS_FILE

                running.info.result_file = str(LOG_DIR / INVITE_SUCCESS_FILE)
                self._log(
                    running,
                    "info",
                    f"结果已写入 {LOG_DIR / INVITE_SUCCESS_FILE} / {LOG_DIR / INVITE_FAIL_FILE}",
                )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_warm_group(self, config: WarmGroupTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        links = [l.strip() for l in config.group_links if l.strip()]
        if not links and config.group_link.strip():
            links = [config.group_link.strip()]
        if not links:
            raise ValueError("请填写目标群组")
        if not config.join_only and not config.messages:
            raise ValueError("请至少填写一条话术")

        running = self._create_task(TaskType.WARM_GROUP, config.account_ids)
        running.info.progress.total = max(len(links), 1) * max(len(config.messages), 1) * config.rounds

        async def runner() -> None:
            await run_warm_group_loop(
                account_ids=config.account_ids,
                group_links=links,
                messages=config.messages,
                interval_min=config.interval_min,
                interval_max=config.interval_max,
                rounds=config.rounds,
                join_only=config.join_only,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_leave_groups(self, config: LeaveGroupsTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")

        running = self._create_task(TaskType.LEAVE_GROUPS, config.account_ids)
        running.info.progress.total = len(config.account_ids)

        async def runner() -> None:
            await run_leave_groups_loop(
                account_ids=config.account_ids,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                pause_event=running.pause_event,
                targets=config.targets,
                include_channels=config.include_channels,
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_monitor(self, config: MonitorTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if config.mode == "dm_forward":
            if not config.reply_message.strip() and not config.forward_group_link.strip():
                raise ValueError("请填写转发群组链接或自动回复话术")
        elif config.mode == "keyword":
            if not config.keywords:
                raise ValueError("请填写监控关键词")
        else:
            raise ValueError("未知的监控模式")

        running = self._create_task(TaskType.MONITOR, config.account_ids)

        async def runner() -> None:
            await run_monitor_loop(
                account_ids=config.account_ids,
                mode=config.mode,
                reply_message=config.reply_message,
                parse_mode=config.parse_mode,
                forward_group_link=config.forward_group_link,
                monitor_group_posts=config.monitor_group_posts,
                keywords=config.keywords,
                notify_group_link=config.notify_group_link,
                dm_on_match=config.dm_on_match,
                global_match=config.global_match,
                auto_spambot_unban=config.auto_spambot_unban,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                should_stop=running.stop_event.is_set,
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_extract_links(self, config: ExtractLinksTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.source_links:
            raise ValueError("请至少填写一个频道/群组链接")
        if not config.extract_links and not config.extract_usernames:
            raise ValueError("请至少勾选一种提取类型")

        running = self._create_task(TaskType.EXTRACT_LINKS, config.account_ids)
        running.info.progress.total = len(config.source_links)

        async def runner() -> None:
            output = await run_extract_links_loop(
                account_ids=config.account_ids,
                source_links=config.source_links,
                message_limit=config.message_limit,
                extract_links=config.extract_links,
                extract_usernames=config.extract_usernames,
                save_path=config.save_path,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                validate_links=config.validate_links,
                min_members=config.min_members,
                max_members=config.max_members,
                only_groups=config.only_groups,
            )
            running.info.result_file = output

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_filter_groups(self, config: FilterGroupsTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")

        running = self._create_task(TaskType.FILTER_GROUPS, config.account_ids)
        running.info.progress.total = 1

        async def runner() -> None:
            output = await run_filter_groups_loop(
                account_ids=config.account_ids,
                title_keyword=config.title_keyword,
                min_members=config.min_members,
                max_members=config.max_members,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                require_sticker=config.require_sticker,
                require_forum=config.require_forum,
                require_send_text=config.require_send_text,
                require_send_links=config.require_send_links,
                require_send_photos=config.require_send_photos,
                require_send_videos=config.require_send_videos,
                exclude_bot_admins=config.exclude_bot_admins,
                group_links=config.group_links,
                mode=getattr(config, "mode", "caps") or "caps",
                ad_message_limit=getattr(config, "ad_message_limit", 10) or 10,
                max_ad_chars=getattr(config, "max_ad_chars", 150) or 150,
                interval_sec=float(getattr(config, "interval_sec", 0) or 0),
            )
            running.info.result_file = output

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_scrape_profiles(self, config: ScrapeProfilesTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.targets:
            raise ValueError("请填写用户名列表")

        running = self._create_task(TaskType.SCRAPE_PROFILES, config.account_ids)
        running.info.progress.total = len(config.targets)

        async def runner() -> None:
            output = await run_scrape_profiles_loop(
                account_ids=config.account_ids,
                targets=config.targets,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                interval_sec=float(config.interval_sec or 0),
            )
            running.info.result_file = output

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_profile_update(self, config: ProfileUpdateTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")

        running = self._create_task(TaskType.UPDATE_PROFILE, config.account_ids)
        running.info.progress.total = len(config.account_ids)

        async def runner() -> None:
            await run_profile_update_loop(
                account_ids=config.account_ids,
                use_random_config=config.use_random_config,
                update_first_name=config.update_first_name,
                update_last_name=config.update_last_name,
                update_about=config.update_about,
                update_username=config.update_username,
                update_avatar=config.update_avatar,
                update_password=config.update_password,
                first_name=config.first_name,
                last_name=config.last_name,
                about=config.about,
                username=config.username,
                old_password=config.old_password,
                new_password=config.new_password,
                interval_min=config.interval_min,
                interval_max=config.interval_max,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
                remove_2fa=config.remove_2fa,
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_channel_comment(self, config: ChannelCommentTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.posts:
            raise ValueError("请至少填写一个频道帖子")
        if not config.comment.strip() and not any(
            str(p.get("comment", "")).strip() for p in config.posts
        ):
            raise ValueError("请填写评论内容")

        running = self._create_task(TaskType.CHANNEL_COMMENT, config.account_ids)
        running.info.progress.total = len(config.posts)

        async def runner() -> None:
            from backend.telegram.channel_comment import run_channel_comment_loop

            await run_channel_comment_loop(
                account_ids=config.account_ids,
                posts=config.posts,
                comment=config.comment,
                interval_min=config.interval_min,
                interval_max=config.interval_max,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def start_clone_channel(self, config: CloneChannelTaskRequest) -> TaskInfo:
        if not config.account_ids:
            raise ValueError("请至少选择一个账号")
        if not config.source.strip():
            raise ValueError("请填写源频道")

        running = self._create_task(TaskType.CLONE_CHANNEL, config.account_ids)
        running.info.progress.total = len(config.account_ids)

        async def runner() -> None:
            from backend.telegram.clone_channel import run_clone_channel_loop

            await run_clone_channel_loop(
                account_ids=config.account_ids,
                source=config.source,
                title=config.title,
                about=config.about,
                message_limit=config.message_limit,
                bind_to_profile=config.bind_to_profile,
                get_client=self._logged_client(running),
                on_log=lambda level, msg: self._log(running, level, msg),
                on_progress=lambda cur, ok, fail: self._update_progress(
                    running, cur, ok, fail
                ),
                should_stop=running.stop_event.is_set,
            )

        running.asyncio_task = asyncio.create_task(self._run_task(running, runner))
        return running.info

    def _update_progress(
        self, running: RunningTask, current: int, success: int, failed: int
    ) -> None:
        running.info.progress.current = current
        running.info.progress.success = success
        running.info.progress.failed = failed

    def _set_progress_total(self, running: RunningTask, total: int) -> None:
        running.info.progress.total = total

    async def pause_task(self, task_id: str) -> TaskInfo:
        running = self._tasks.get(task_id)
        if not running:
            raise ValueError("任务不存在")
        if running.info.status != TaskStatus.RUNNING:
            return running.info
        running.stop_as_pause = True
        running.stop_event.set()
        running.pause_event.set()
        running.info.status = TaskStatus.PAUSED
        self._save_checkpoint(running)
        self._log(running, "info", "正在暂停，当前项完成后保留进度…")
        if running.asyncio_task and not running.asyncio_task.done():
            try:
                await asyncio.wait_for(running.asyncio_task, timeout=90)
            except asyncio.TimeoutError:
                running.asyncio_task.cancel()
        self._save_checkpoint(running)
        running.info.status = TaskStatus.PAUSED
        running.info.resumable = True
        self._log(
            running,
            "info",
            "已暂停。改配置后点「开始」或「继续」按最新设置接着跑；点「停止」则重置进度",
        )
        return running.info

    async def resume_task(self, task_id: str) -> TaskInfo:
        running = self._tasks.get(task_id)
        if not running:
            raise ValueError("任务不存在")
        if running.info.status != TaskStatus.PAUSED:
            return running.info
        if running.asyncio_task and not running.asyncio_task.done():
            running.pause_event.set()
            running.info.status = TaskStatus.RUNNING
            self._log(running, "info", "任务已恢复")
            return running.info
        raise ValueError("任务已暂停退出，请重新点击开始以最新配置继续")

    def export_task_log(self, task_id: str) -> str:
        running = self._tasks.get(task_id)
        if not running:
            raise ValueError("任务不存在")
        lines = [
            f"[{entry.time}] [{entry.level}] {entry.message}"
            for entry in running.info.logs
        ]
        if running.info.failed_items:
            lines.append("")
            lines.append("=== 失败明细 ===")
            for item in running.info.failed_items:
                lines.append(
                    f"{item.target}\t{item.reason}\t账号={item.account_id or '-'}"
                )
        return "\n".join(lines)

    def save_task_log(self, task_id: str) -> str:
        from datetime import datetime

        from backend.config import LOG_DIR

        content = self.export_task_log(task_id)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / (
            f"任务日志_{task_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        path.write_text(content, encoding="utf-8")
        return str(path.resolve())

    async def stop_task(self, task_id: str) -> TaskInfo:
        running = self._tasks.get(task_id)
        if not running:
            raise ValueError("任务不存在")
        if running.info.status not in {
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.STOPPING,
            TaskStatus.PENDING,
        }:
            self._clear_checkpoint(running.info.type)
            running.info.resumable = False
            return running.info

        running.stop_as_pause = False
        running.info.status = TaskStatus.STOPPING
        running.stop_event.set()
        running.pause_event.set()
        self._clear_checkpoint(running.info.type)
        running.info.resumable = False
        self._log(running, "info", "正在停止任务并重置进度...")

        if running.asyncio_task and not running.asyncio_task.done():
            try:
                await asyncio.wait_for(running.asyncio_task, timeout=30)
            except asyncio.TimeoutError:
                running.asyncio_task.cancel()

        running.info.status = TaskStatus.STOPPED
        running.info.resumable = False
        self._log(running, "info", "任务已停止，下次开始将从头执行")
        return running.info

    async def shutdown(self) -> None:
        for task_id in list(self._tasks.keys()):
            running = self._tasks[task_id]
            if running.info.status == TaskStatus.RUNNING:
                await self.stop_task(task_id)


task_manager = TaskManager()
