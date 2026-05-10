"""
任务路由（M3）。

GET    /api/tasks               列表（按状态/类型筛选 + 分页）
GET    /api/tasks/summary       统计概览
GET    /api/tasks/{id}          详情（含子任务）
DELETE /api/tasks/{id}          取消（仅未开始）
POST   /api/tasks/cancel-waiting 取消全部未开始任务
POST   /api/tasks/pause         暂停队列
POST   /api/tasks/resume        继续队列
DELETE /api/tasks/clear?status= 批量清理（如已完成/已失败）
WS     /ws/tasks                实时推送
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DownloadTask, Song
from app.db.session import get_session
from app.services.local_file_service import delete_local_song_file
from app.services.task_manager import TaskManager, _serialize_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskIdsPayload(BaseModel):
    ids: list[int] = Field(default_factory=list)


class DeleteTasksPayload(TaskIdsPayload):
    delete_local_files: bool = False


@router.get("")
async def list_tasks(
    status: Optional[str] = Query(default=None),
    target_type: Optional[str] = Query(default=None),
    parent_only: bool = Query(default=False, description="只看父任务（不返回子任务）"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(DownloadTask).order_by(DownloadTask.created_at.desc())
    conds = []
    if status:
        conds.append(DownloadTask.status == status)
    if target_type:
        conds.append(DownloadTask.target_type == target_type)
    if parent_only:
        conds.append(DownloadTask.parent_task_id.is_(None))
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.scalars(stmt)).all()

    # 同时给一个总计数
    count_stmt = select(func.count(DownloadTask.id))
    if conds:
        count_stmt = count_stmt.where(and_(*conds))
    total = await session.scalar(count_stmt) or 0

    return {
        "items": [_serialize_task(t) for t in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


@router.get("/summary")
async def summary(session: AsyncSession = Depends(get_session)):
    """各状态计数（用于顶部角标）。"""
    rows = (
        await session.execute(
            select(DownloadTask.status, func.count(DownloadTask.id)).group_by(
                DownloadTask.status
            )
        )
    ).all()
    return {status: int(cnt) for status, cnt in rows}


@router.post("/cancel-waiting")
async def cancel_waiting_tasks():
    cancelled = await TaskManager.get().cancel_waiting()
    return {"cancelled": cancelled}


@router.post("/cancel")
async def cancel_selected_tasks(payload: TaskIdsPayload):
    cancelled = await TaskManager.get().cancel_many(payload.ids)
    return {"requested": len(payload.ids), "cancelled": cancelled}


@router.post("/retry")
async def retry_selected_tasks(payload: TaskIdsPayload):
    retried = await TaskManager.get().retry_many(payload.ids)
    return {"requested": len(payload.ids), "retried": retried}


@router.post("/delete")
async def delete_selected_tasks(
    payload: DeleteTasksPayload,
    session: AsyncSession = Depends(get_session),
):
    """删除勾选的任务记录；可选同时删除已下载本地歌曲。"""
    if not payload.ids:
        return {
            "requested": 0,
            "deleted": 0,
            "files_deleted": 0,
            "songs_deleted": 0,
            "file_errors": [],
        }

    rows = (
        await session.scalars(
            select(DownloadTask).where(
                DownloadTask.id.in_(payload.ids),
                DownloadTask.status.not_in(("queued", "pending", "running")),
            )
        )
    ).all()

    task_ids = [t.id for t in rows]
    file_paths = [t.file_path for t in rows if t.file_path]
    files_deleted = 0
    songs_deleted = 0
    file_errors: list[dict[str, str]] = []
    failed_file_paths: set[str] = set()
    removable_song_paths: set[str] = set()

    if payload.delete_local_files:
        # End the read transaction before touching the filesystem. Slow or stuck
        # file IO should not hold SQLite locks used by Sync and the queue.
        await session.commit()

        seen_paths: set[str] = set()
        for file_path in file_paths:
            if file_path in seen_paths:
                continue
            seen_paths.add(file_path)
            result = delete_local_song_file(file_path)
            if result.ok_for_db_delete:
                files_deleted += 1
                removable_song_paths.add(file_path)
            elif result.error:
                file_errors.append({"file_path": file_path, "error": result.error})
                failed_file_paths.add(file_path)

    if removable_song_paths:
        songs = (
            await session.scalars(select(Song).where(Song.file_path.in_(removable_song_paths)))
        ).all()
        for song in songs:
            await session.delete(song)
            songs_deleted += 1

    rows_to_delete = (
        await session.scalars(
            select(DownloadTask).where(
                DownloadTask.id.in_(task_ids),
                DownloadTask.status.not_in(("queued", "pending", "running")),
            )
        )
    ).all()
    kept_for_file_errors = 0
    for t in rows_to_delete:
        if payload.delete_local_files and t.file_path in failed_file_paths:
            kept_for_file_errors += 1
            continue
        await session.delete(t)
    await session.commit()

    return {
        "requested": len(payload.ids),
        "deleted": len(rows_to_delete) - kept_for_file_errors,
        "files_deleted": files_deleted,
        "songs_deleted": songs_deleted,
        "kept_for_file_errors": kept_for_file_errors,
        "file_errors": file_errors,
    }


@router.post("/pause")
async def pause_tasks():
    mgr = TaskManager.get()
    await mgr.pause()
    return mgr.control_state()


@router.post("/resume")
async def resume_tasks():
    mgr = TaskManager.get()
    await mgr.resume()
    return mgr.control_state()


@router.get("/control")
async def task_control_state():
    return TaskManager.get().control_state()


@router.get("/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    t = await session.get(DownloadTask, task_id)
    if not t:
        raise HTTPException(status_code=404)
    children = (
        await session.scalars(
            select(DownloadTask).where(DownloadTask.parent_task_id == task_id)
            .order_by(DownloadTask.id)
        )
    ).all()
    return {
        "task": _serialize_task(t),
        "children": [_serialize_task(c) for c in children],
    }


@router.delete("/{task_id}")
async def cancel_task(task_id: int):
    ok = await TaskManager.get().cancel(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="无法取消（不存在或已运行/已结束）")
    return {"task_id": task_id, "status": "cancelled"}


@router.delete("")
async def clear_tasks(
    status: str = Query(..., description="要清理的状态：success / skipped_dup / failed / cancelled"),
    session: AsyncSession = Depends(get_session),
):
    """清理指定状态的历史任务记录。"""
    if status not in ("success", "skipped_dup", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="不允许清理 running/queued 任务")
    result = await session.execute(
        delete(DownloadTask).where(DownloadTask.status == status)
    )
    await session.commit()
    return {"status": status, "deleted": int(result.rowcount or 0)}


# ==================================================================
# WebSocket 实时推送
# ==================================================================
@router.websocket("/ws")
async def ws_tasks(ws: WebSocket):
    await ws.accept()
    mgr = TaskManager.get()
    try:
        async with mgr.subscribe() as q:
            while True:
                msg = await q.get()
                await ws.send_text(json.dumps(msg, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"ws task channel error: {e}")
        try:
            await ws.close()
        except Exception:
            pass
