from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from backend.models.schemas import (
    ApiResponse,
    BroadcastTaskRequest,
    ChannelCommentTaskRequest,
    CloneChannelTaskRequest,
    DmTaskRequest,
    ExtractLinksTaskRequest,
    FilterGroupsTaskRequest,
    InviteTaskRequest,
    JoinGroupTaskRequest,
    LeaveGroupsTaskRequest,
    MonitorTaskRequest,
    ProfileUpdateTaskRequest,
    ScrapeGroupsTaskRequest,
    ScrapeMembersTaskRequest,
    ScrapeProfilesTaskRequest,
    WarmGroupTaskRequest,
    TaskInfo,
)
from backend.tasks.task_manager import task_manager


def _require_license() -> None:
    from backend.license_gate import evaluate_license

    status = evaluate_license()
    if not status["allowed"]:
        raise HTTPException(status_code=403, detail=f"授权校验失败: {status['reason']}")


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskInfo])
async def list_tasks() -> list[TaskInfo]:
    return task_manager.list_tasks()


@router.get("/{task_id}", response_model=TaskInfo)
async def get_task(task_id: str) -> TaskInfo:
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/broadcast", response_model=TaskInfo)
async def start_broadcast(payload: BroadcastTaskRequest) -> TaskInfo:
    _require_license()
    try:
        targets = [t.strip() for t in payload.targets if t.strip()]
        return task_manager.start_broadcast(
            payload.model_copy(update={"targets": targets})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/join-group", response_model=TaskInfo)
async def start_join_group(payload: JoinGroupTaskRequest) -> TaskInfo:
    _require_license()
    try:
        targets = [t.strip() for t in payload.targets if t.strip()]
        return task_manager.start_join_group(
            payload.model_copy(update={"targets": targets})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/dm", response_model=TaskInfo)
async def start_dm(payload: DmTaskRequest) -> TaskInfo:
    _require_license()
    try:
        targets = [t.strip() for t in payload.targets if t.strip()]
        return task_manager.start_dm(payload.model_copy(update={"targets": targets}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scrape-members", response_model=TaskInfo)
async def start_scrape_members(payload: ScrapeMembersTaskRequest) -> TaskInfo:
    _require_license()
    try:
        links = [t.strip() for t in payload.group_links if t.strip()]
        return task_manager.start_scrape_members(
            payload.model_copy(update={"group_links": links})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scrape-groups", response_model=TaskInfo)
async def start_scrape_groups(payload: ScrapeGroupsTaskRequest) -> TaskInfo:
    _require_license()
    try:
        keywords = [t.strip() for t in payload.keywords if t.strip()]
        return task_manager.start_scrape_groups(
            payload.model_copy(update={"keywords": keywords})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/invite", response_model=TaskInfo)
async def start_invite(payload: InviteTaskRequest) -> TaskInfo:
    _require_license()
    try:
        users = [t.strip() for t in payload.user_targets if t.strip()]
        return task_manager.start_invite(
            payload.model_copy(update={"user_targets": users})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/warm-group", response_model=TaskInfo)
async def start_warm_group(payload: WarmGroupTaskRequest) -> TaskInfo:
    _require_license()
    try:
        messages = [t.strip() for t in payload.messages if t.strip()]
        return task_manager.start_warm_group(
            payload.model_copy(update={"messages": messages})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/monitor", response_model=TaskInfo)
async def start_monitor(payload: MonitorTaskRequest) -> TaskInfo:
    _require_license()
    try:
        keywords = [t.strip() for t in payload.keywords if t.strip()]
        return task_manager.start_monitor(
            payload.model_copy(update={"keywords": keywords})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/extract-links", response_model=TaskInfo)
async def start_extract_links(payload: ExtractLinksTaskRequest) -> TaskInfo:
    _require_license()
    try:
        links = [t.strip() for t in payload.source_links if t.strip()]
        return task_manager.start_extract_links(
            payload.model_copy(update={"source_links": links})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/leave-groups", response_model=TaskInfo)
async def start_leave_groups(payload: LeaveGroupsTaskRequest) -> TaskInfo:
    _require_license()
    try:
        return task_manager.start_leave_groups(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/filter-groups", response_model=TaskInfo)
async def start_filter_groups(payload: FilterGroupsTaskRequest) -> TaskInfo:
    _require_license()
    try:
        return task_manager.start_filter_groups(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scrape-profiles", response_model=TaskInfo)
async def start_scrape_profiles(payload: ScrapeProfilesTaskRequest) -> TaskInfo:
    _require_license()
    try:
        targets = [t.strip() for t in payload.targets if t.strip()]
        return task_manager.start_scrape_profiles(
            payload.model_copy(update={"targets": targets})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/update-profile", response_model=TaskInfo)
async def start_profile_update(payload: ProfileUpdateTaskRequest) -> TaskInfo:
    _require_license()
    try:
        return task_manager.start_profile_update(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/channel-comment", response_model=TaskInfo)
async def start_channel_comment(payload: ChannelCommentTaskRequest) -> TaskInfo:
    _require_license()
    try:
        return task_manager.start_channel_comment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/clone-channel", response_model=TaskInfo)
async def start_clone_channel(payload: CloneChannelTaskRequest) -> TaskInfo:
    _require_license()
    try:
        return task_manager.start_clone_channel(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/pause", response_model=TaskInfo)
async def pause_task(task_id: str) -> TaskInfo:
    try:
        return await task_manager.pause_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/resume", response_model=TaskInfo)
async def resume_task(task_id: str) -> TaskInfo:
    try:
        return await task_manager.resume_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}/export")
async def export_task_log(task_id: str) -> PlainTextResponse:
    try:
        content = task_manager.export_task_log(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(
        content,
        headers={"Content-Disposition": f'attachment; filename="task_{task_id}.txt"'},
    )


@router.post("/{task_id}/export", response_model=ApiResponse)
async def save_task_log(task_id: str) -> ApiResponse:
    try:
        path = task_manager.save_task_log(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(success=True, message=f"日志已保存到: {path}", data={"path": path})


@router.post("/{task_id}/stop", response_model=TaskInfo)
async def stop_task(task_id: str) -> TaskInfo:
    try:
        return await task_manager.stop_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
