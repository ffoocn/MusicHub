"""
异步任务管理器。

设计：
    - 单进程内存队列（asyncio.Queue），由 N 个 worker 协程消费
    - worker 数量来自 settings.download.concurrency（启动时读取）
    - 任务状态 + 进度持久化到 download_tasks 表（前端刷新页面也能看到历史）
    - 状态变化 broadcast 给所有 WS 订阅者，做到秒级实时进度

只做单首下载子任务，"歌单整体"是逻辑上的父任务，
父任务负责拆分成多个子任务入队 + 汇总进度，不直接下载。
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, DownloadTask, PlaylistSubscription
from app.db.session import session_factory
from app.platforms.base import Platform, PlatformID, SongInfo
from app.platforms.netease import NeteaseClient
from app.platforms.qq import QQClient
from app.services import settings_service
from app.services.download_service import DownloadOutcome, download_song
from app.services.m3u_service import generate_m3u_for_subscription
from app.utils.logger import logger


# ==================================================================
# 通用工具
# ==================================================================
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_TASK_SOURCE_LOCKS: dict[str, asyncio.Lock] = {}


def _task_source_lock(platform: PlatformID, song_id: str) -> asyncio.Lock:
    key = f"{platform.value}:song:{song_id}"
    lock = _TASK_SOURCE_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _TASK_SOURCE_LOCKS[key] = lock
    return lock


def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_int_list(value: Any) -> list[int]:
    """把旧库里可能存在的 JSON / 标量来源字段规整成 int 列表。"""
    if value is None:
        return []
    raw = value if isinstance(value, list) else [value]
    result: list[int] = []
    for item in raw:
        try:
            num = int(item)
        except (TypeError, ValueError):
            continue
        if num not in result:
            result.append(num)
    return result


def _json_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _task_subscription_ids(t: DownloadTask) -> list[int]:
    result = _json_int_list(t.source_subscription_ids_json)
    if t.source_subscription_id and t.source_subscription_id not in result:
        result.insert(0, t.source_subscription_id)
    return result


def _task_sync_run_ids(t: DownloadTask) -> list[int]:
    result = _json_int_list(t.sync_run_ids_json)
    if t.sync_run_id and t.sync_run_id not in result:
        result.insert(0, t.sync_run_id)
    return result


def _task_source_types(t: DownloadTask) -> list[str]:
    result = _json_str_list(t.source_types_json)
    if t.source_type and t.source_type not in result:
        result.insert(0, t.source_type)
    return result


def _non_subscription_source_types(t: DownloadTask) -> list[str]:
    """返回 manual / playlist_download / album_download 等非订阅来源。"""
    return [source_type for source_type in _task_source_types(t) if source_type != "subscription_sync"]


def _merge_task_sources(
    t: DownloadTask,
    *,
    source_subscription_id: Optional[int],
    sync_run_id: Optional[int],
    source_type: Optional[str],
) -> bool:
    """
    记录任务的所有来源。

    旧字段保留第一个来源供历史 UI 使用；JSON 字段保存完整列表，避免同一首歌
    被多个订阅复用同一个 queued/running 任务时只刷新其中一个订阅。
    """
    changed = False

    sub_ids = _task_subscription_ids(t)
    if source_subscription_id and source_subscription_id not in sub_ids:
        sub_ids.append(source_subscription_id)
        changed = True
    if sub_ids != _json_int_list(t.source_subscription_ids_json):
        t.source_subscription_ids_json = sub_ids
        changed = True
    if source_subscription_id and not t.source_subscription_id:
        t.source_subscription_id = source_subscription_id
        changed = True

    run_ids = _task_sync_run_ids(t)
    if sync_run_id and sync_run_id not in run_ids:
        run_ids.append(sync_run_id)
        changed = True
    if run_ids != _json_int_list(t.sync_run_ids_json):
        t.sync_run_ids_json = run_ids
        changed = True
    if sync_run_id and not t.sync_run_id:
        t.sync_run_id = sync_run_id
        changed = True

    source_types = _task_source_types(t)
    if source_type and source_type not in source_types:
        source_types.append(source_type)
        changed = True
    if source_types != _json_str_list(t.source_types_json):
        t.source_types_json = source_types
        changed = True
    if source_type and (not t.source_type or t.source_type == "manual"):
        t.source_type = source_type
        changed = True

    return changed


def _remove_task_subscription_source(
    t: DownloadTask, subscription_id: int
) -> tuple[bool, bool]:
    """
    从等待中的任务移除一个订阅来源。

    返回：(changed, should_cancel)。如果任务仍被其他订阅引用，只更新来源列表；
    只有没有任何剩余订阅来源时，调用方才应该取消任务。
    """
    sub_ids = _task_subscription_ids(t)
    if subscription_id not in sub_ids:
        return False, False

    remaining = [sid for sid in sub_ids if sid != subscription_id]
    non_subscription_types = _non_subscription_source_types(t)
    if not remaining:
        if not non_subscription_types:
            return False, True
        t.source_subscription_ids_json = []
        t.source_subscription_id = None
        t.sync_run_ids_json = []
        t.sync_run_id = None
        t.source_types_json = non_subscription_types
        t.source_type = non_subscription_types[0]
        return True, False

    t.source_subscription_ids_json = remaining
    t.source_subscription_id = remaining[0]
    return True, False


def _serialize_task(t: DownloadTask) -> dict[str, Any]:
    """转 dict 给前端 / WS。"""
    return {
        "id": t.id,
        "parent_task_id": t.parent_task_id,
        "target_type": t.target_type,
        "target_id": t.target_id,
        "platform": t.platform,
        "source_subscription_id": t.source_subscription_id,
        "sync_run_id": t.sync_run_id,
        "source_type": t.source_type,
        "source_subscription_ids": _task_subscription_ids(t),
        "sync_run_ids": _task_sync_run_ids(t),
        "source_types": _task_source_types(t),
        "title": t.title,
        "sub_title": t.sub_title,
        "cover_url": t.cover_url,
        "status": t.status,
        "priority": t.priority,
        "progress": t.progress,
        "total_count": t.total_count,
        "success_count": t.success_count,
        "fail_count": t.fail_count,
        "skip_count": t.skip_count,
        "error_msg": t.error_msg,
        "file_path": t.file_path,
        "audio_format": t.audio_format,
        "bitrate": t.bitrate,
        "quality": t.quality,
        "file_size": t.file_size,
        "started_at": _iso_utc(t.started_at),
        "finished_at": _iso_utc(t.finished_at),
        "created_at": _iso_utc(t.created_at),
        "updated_at": _iso_utc(t.updated_at),
    }


# ==================================================================
# Broadcast 中心（WebSocket 订阅）
# ==================================================================
class _Broadcaster:
    """
    简易广播：每个订阅者一个 asyncio.Queue。
    任务状态变化时 publish 一条消息，所有订阅者都能拿到。
    """

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1024)
        async with self._lock:
            self._subs.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subs.discard(q)

    def publish_nowait(self, msg: dict[str, Any]) -> None:
        """同步发布，溢出的订阅者直接丢一条最旧消息。"""
        for q in list(self._subs):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass


# ==================================================================
# TaskManager
# ==================================================================
@dataclass
class _QueueItem:
    """队列里的任务条目。只装 task_id，真正取数据从 DB 读最新版。"""

    task_id: int
    priority: int = 10
    enqueued_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class EnqueueSongResult:
    """单曲入队结果，created=False 表示复用了已有 queued/running 任务。"""

    task_id: int
    created: bool


class TaskManager:
    """
    全局任务管理器（单例）。

    生命周期：
        - 应用 lifespan 启动时调用 start()，启动 N 个 worker
        - 应用关闭时调用 stop()，等待 worker 退出
    """

    _instance: Optional["TaskManager"] = None

    def __init__(self, concurrency: int = 3) -> None:
        self._queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._broadcaster = _Broadcaster()
        self._stopping = False
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._concurrency = concurrency

    # ---------- 单例访问 ----------
    @classmethod
    def get(cls) -> "TaskManager":
        if cls._instance is None:
            cls._instance = TaskManager()
        return cls._instance

    # ---------- 生命周期 ----------
    async def start(self) -> None:
        """启动 worker pool。从 settings 读并发数。"""
        async with session_factory() as session:
            cfg = await settings_service.get_all(session)
            self._concurrency = max(1, int(cfg.get("download.concurrency", 3)))
            self._paused = bool(cfg.get("queue.paused", False))
            if self._paused:
                self._pause_event.clear()
            else:
                self._pause_event.set()
        self._stopping = False
        self._workers = [
            asyncio.create_task(self._worker(i + 1), name=f"dl-worker-{i + 1}")
            for i in range(self._concurrency)
        ]
        logger.info(f"TaskManager started with {self._concurrency} workers")

        # 服务重启时，把上次未完成的 running 任务重置为 queued 重新跑
        await self._recover_dangling()

    async def stop(self) -> None:
        self._stopping = True
        for w in self._workers:
            w.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("TaskManager stop timeout, forcing shutdown")
        self._workers.clear()
        logger.info("TaskManager stopped")

    async def _recover_dangling(self) -> None:
        """重启后把上次中断的任务重新入队。"""
        async with session_factory() as session:
            rows = (
                await session.scalars(
                    select(DownloadTask).where(
                        DownloadTask.status.in_(("queued", "running"))
                    )
                )
            ).all()
            for t in rows:
                t.status = "queued"
                t.progress = 0.0
                self._queue.put_nowait(_QueueItem(t.id, t.priority))
            await session.commit()
            if rows:
                logger.info(f"recovered {len(rows)} dangling tasks")

    # ---------- 入队 ----------
    async def enqueue_song(
        self,
        platform: PlatformID,
        song: SongInfo,
        *,
        parent_task_id: Optional[int] = None,
        source_subscription_id: Optional[int] = None,
        sync_run_id: Optional[int] = None,
        source_type: str = "manual",
        priority: int = 10,
    ) -> int:
        """提交一首歌的下载任务。返回 task_id。"""
        result = await self.enqueue_song_with_result(
            platform,
            song,
            parent_task_id=parent_task_id,
            source_subscription_id=source_subscription_id,
            sync_run_id=sync_run_id,
            source_type=source_type,
            priority=priority,
        )
        return result.task_id

    async def enqueue_song_with_result(
        self,
        platform: PlatformID,
        song: SongInfo,
        *,
        parent_task_id: Optional[int] = None,
        source_subscription_id: Optional[int] = None,
        sync_run_id: Optional[int] = None,
        source_type: str = "manual",
        priority: int = 10,
    ) -> EnqueueSongResult:
        """提交一首歌的下载任务，并返回是新建还是复用已有任务。"""
        async with _task_source_lock(platform, song.platform_song_id):
            async with session_factory() as session:
                existing = await session.scalar(
                    select(DownloadTask).where(
                        DownloadTask.platform == platform.value,
                        DownloadTask.target_type == "song",
                        DownloadTask.target_id == song.platform_song_id,
                        DownloadTask.status.in_(("queued", "pending", "running")),
                    )
                )
                if existing:
                    changed = _merge_task_sources(
                        existing,
                        source_subscription_id=source_subscription_id,
                        sync_run_id=sync_run_id,
                        source_type=source_type,
                    )
                    if changed:
                        await session.commit()
                        await session.refresh(existing)
                        self._broadcaster.publish_nowait(
                            {"event": "task.updated", "task": _serialize_task(existing)}
                        )
                    return EnqueueSongResult(task_id=existing.id, created=False)

                t = DownloadTask(
                    parent_task_id=parent_task_id,
                    source_subscription_id=source_subscription_id,
                    sync_run_id=sync_run_id,
                    source_type=source_type,
                    source_subscription_ids_json=(
                        [source_subscription_id] if source_subscription_id else []
                    ),
                    sync_run_ids_json=[sync_run_id] if sync_run_id else [],
                    source_types_json=[source_type] if source_type else [],
                    target_type="song",
                    target_id=song.platform_song_id,
                    platform=platform.value,
                    title=song.name,
                    sub_title=song.primary_artist,
                    cover_url=song.cover_url,
                    status="queued",
                    priority=priority,
                    payload_json={
                        "name": song.name,
                        "artists": song.artists,
                        "album": song.album,
                        "album_id": song.album_id,
                        "duration_ms": song.duration_ms,
                        "cover_url": song.cover_url,
                    },
                )
                session.add(t)
                await session.commit()
                await session.refresh(t)
                self._queue.put_nowait(_QueueItem(t.id, priority))
                self._broadcaster.publish_nowait(
                    {"event": "task.created", "task": _serialize_task(t)}
                )
                return EnqueueSongResult(task_id=t.id, created=True)

    async def enqueue_playlist(
        self,
        platform: PlatformID,
        playlist_id: str,
        playlist_name: str,
        cover_url: Optional[str],
        songs: list[SongInfo],
        *,
        source_type: str = "playlist_download",
        priority: int = 10,
    ) -> tuple[int, list[int]]:
        """
        建一个父任务（target_type=playlist），并把每首歌作为子任务入队。

        返回：(parent_task_id, child_task_ids)
        """
        async with session_factory() as session:
            parent = DownloadTask(
                target_type="playlist",
                target_id=playlist_id,
                platform=platform.value,
                source_type=source_type,
                title=playlist_name,
                cover_url=cover_url,
                status="queued",
                priority=priority,
                total_count=len(songs),
                payload_json={"playlist_name": playlist_name, "song_count": len(songs)},
            )
            session.add(parent)
            await session.commit()
            await session.refresh(parent)
            parent_id = parent.id

        child_ids: list[int] = []
        seen_song_ids: set[str] = set()
        for s in songs:
            if s.platform_song_id in seen_song_ids:
                continue
            seen_song_ids.add(s.platform_song_id)
            result = await self.enqueue_song_with_result(
                platform,
                s,
                parent_task_id=parent_id,
                source_type=source_type,
                priority=priority,
            )
            if result.task_id not in child_ids:
                child_ids.append(result.task_id)

        async with session_factory() as session:
            parent = await session.get(DownloadTask, parent_id)
            if not parent:
                return parent_id, child_ids
            parent.total_count = len(child_ids)
            parent.payload_json = {
                **(parent.payload_json or {}),
                "song_count": len(songs),
                "child_task_ids": child_ids,
            }
            await session.commit()
            await session.refresh(parent)
            self._broadcaster.publish_nowait(
                {"event": "task.created", "task": _serialize_task(parent)}
            )
            return parent.id, child_ids

    async def cancel(self, task_id: int) -> bool:
        """取消未开始的任务（已 running 的不可取消）。"""
        async with session_factory() as session:
            t = await session.get(DownloadTask, task_id)
            if not t:
                return False
            if t.status not in ("queued", "pending"):
                return False
            t.status = "cancelled"
            t.finished_at = utcnow()
            await session.commit()
            self._broadcaster.publish_nowait(
                {"event": "task.updated", "task": _serialize_task(t)}
            )
            return True

    async def cancel_waiting(self) -> int:
        """取消所有尚未开始的任务。运行中的下载不会被中断。"""
        async with session_factory() as session:
            rows = (
                await session.scalars(
                    select(DownloadTask).where(DownloadTask.status.in_(("queued", "pending")))
                )
            ).all()
            for t in rows:
                t.status = "cancelled"
                t.finished_at = utcnow()
            await session.commit()
            for t in rows:
                await session.refresh(t)
                self._broadcaster.publish_nowait(
                    {"event": "task.updated", "task": _serialize_task(t)}
                )
            return len(rows)

    async def cancel_many(self, task_ids: list[int]) -> int:
        """取消一组尚未开始的任务。运行中的任务不会被中断。"""
        if not task_ids:
            return 0
        async with session_factory() as session:
            rows = (
                await session.scalars(
                    select(DownloadTask).where(
                        DownloadTask.id.in_(task_ids),
                        DownloadTask.status.in_(("queued", "pending")),
                    )
                )
            ).all()
            for t in rows:
                t.status = "cancelled"
                t.finished_at = utcnow()
            await session.commit()
            for t in rows:
                await session.refresh(t)
                self._broadcaster.publish_nowait(
                    {"event": "task.updated", "task": _serialize_task(t)}
                )
            return len(rows)

    async def cancel_waiting_for_subscription(self, subscription_id: int) -> int:
        """取消某个订阅独占的等待任务；共享任务只移除该订阅来源。"""
        async with session_factory() as session:
            rows = (
                await session.scalars(
                    select(DownloadTask).where(
                        DownloadTask.status.in_(("queued", "pending")),
                    )
                )
            ).all()
            rows = [t for t in rows if subscription_id in _task_subscription_ids(t)]
            cancelled = 0
            for t in rows:
                changed, should_cancel = _remove_task_subscription_source(t, subscription_id)
                if should_cancel:
                    t.status = "cancelled"
                    t.finished_at = utcnow()
                    cancelled += 1
                elif changed:
                    logger.info(
                        f"removed subscription source sub#{subscription_id} from shared task#{t.id}"
                    )
            await session.commit()
            for t in rows:
                await session.refresh(t)
                self._broadcaster.publish_nowait(
                    {"event": "task.updated", "task": _serialize_task(t)}
                )
            return cancelled

    async def retry_many(self, task_ids: list[int]) -> int:
        """把失败/已取消的单曲任务重新排队。"""
        if not task_ids:
            return 0
        async with session_factory() as session:
            rows = (
                await session.scalars(
                    select(DownloadTask).where(
                        DownloadTask.id.in_(task_ids),
                        DownloadTask.target_type == "song",
                        DownloadTask.status.in_(("failed", "cancelled")),
                    )
                )
            ).all()
            for t in rows:
                t.status = "queued"
                t.progress = 0.0
                t.error_msg = None
                t.started_at = None
                t.finished_at = None
            await session.commit()
            for t in rows:
                await session.refresh(t)
                self._queue.put_nowait(_QueueItem(t.id, t.priority))
                self._broadcaster.publish_nowait(
                    {"event": "task.updated", "task": _serialize_task(t)}
                )
            return len(rows)

    async def pause(self) -> None:
        """暂停 worker 获取新任务；已 running 的任务会自然完成。"""
        self._paused = True
        self._pause_event.clear()
        async with session_factory() as session:
            await settings_service.set_value(session, "queue.paused", True)
            await session.commit()

    async def resume(self) -> None:
        self._paused = False
        self._pause_event.set()
        async with session_factory() as session:
            await settings_service.set_value(session, "queue.paused", False)
            await session.commit()

    def control_state(self) -> dict[str, Any]:
        return {
            "paused": self._paused,
            "concurrency": self._concurrency,
            "queue_size": self._queue.qsize(),
        }

    # ---------- WS 订阅 ----------
    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        q = await self._broadcaster.subscribe()
        try:
            yield q
        finally:
            await self._broadcaster.unsubscribe(q)

    # ---------- worker ----------
    async def _worker(self, worker_id: int) -> None:
        logger.debug(f"worker {worker_id} started")
        while not self._stopping:
            try:
                await self._pause_event.wait()
                item = await self._queue.get()
                if self._paused:
                    self._queue.put_nowait(item)
                    self._queue.task_done()
                    continue
            except asyncio.CancelledError:
                break

            try:
                await self._run_task(item.task_id, worker_id)
            except asyncio.CancelledError:
                # 被 stop() 取消时，把任务状态置回 queued
                async with session_factory() as session:
                    t = await session.get(DownloadTask, item.task_id)
                    if t and t.status == "running":
                        t.status = "queued"
                        await session.commit()
                raise
            except Exception as e:
                logger.exception(f"worker {worker_id} unhandled: {e}")
            finally:
                self._queue.task_done()
        logger.debug(f"worker {worker_id} stopped")

    async def _run_task(self, task_id: int, worker_id: int) -> None:
        """
        执行单首歌曲的下载任务。

        **关键设计：短事务化（避免 SQLite "database is locked"）**

            旧版本把整段下载流程包在一个 ``async with session_factory()`` 里，
            导致几十秒到几分钟的 HTTP / 文件 IO 期间持有 SQLite 连接和事务。
            多 worker 并发或用户管理请求并发时，会因 SQLite 写锁互斥导致
            ``database is locked`` 频繁 500。

            现在拆成 3 段：

              1. 短事务：标记 running、加载所需上下文（song / platform 客户端），
                 commit 立即关 session；
              2. 完全无 session：只跑 ``download_song`` 的纯 IO（download_song
                 内部的每次 db 访问也是各自独立短事务）；
              3. 短事务：写最终状态 + commit + 聚合父任务进度。

            这样 SQLite 写锁的占用窗口从「整个下载时长」缩到「单条 UPDATE 时长」，
            不会再阻塞用户的 PUT/DELETE 等管理请求。
        """
        # ============ 1. 短事务：标记 running，预加载上下文 ============
        async with session_factory() as session:
            t = await session.get(DownloadTask, task_id)
            if not t:
                return
            if t.status == "cancelled":
                return
            if t.status not in ("queued", "pending"):
                return
            if t.target_type != "song":
                return  # playlist/album 父任务不直接下，由进度聚合处理

            t.status = "running"
            t.started_at = utcnow()
            t.progress = 0.0
            await session.commit()
            await session.refresh(t)

            running_snapshot = _serialize_task(t)
            platform_id = PlatformID(t.platform)
            parent_id = t.parent_task_id

            # 在 session 还活着时把 song / platform client 准备好
            song = await self._reload_song(session, t)
            cli = await self._make_platform(session, platform_id)

        self._broadcaster.publish_nowait(
            {"event": "task.updated", "task": running_snapshot}
        )

        # ============ 2. 无 session：纯 IO 下载（几秒 ~ 几分钟）============
        outcome: DownloadOutcome | None = None
        run_error: str | None = None
        last_progress_write = 0.0

        async def _progress(downloaded: int, total: int | None) -> None:
            nonlocal last_progress_write
            now = time.time()
            if now - last_progress_write < 0.8 and not (total and downloaded >= total):
                return
            last_progress_write = now
            progress = 0.0
            if total and total > 0:
                progress = min(0.99, max(0.0, downloaded / total))
            async with session_factory() as progress_session:
                current = await progress_session.get(DownloadTask, task_id)
                if not current or current.status != "running":
                    return
                current.file_size = downloaded
                if progress > current.progress:
                    current.progress = progress
                await progress_session.commit()
                await progress_session.refresh(current)
                self._broadcaster.publish_nowait(
                    {"event": "task.updated", "task": _serialize_task(current)}
                )

        try:
            outcome = await download_song(cli, song, progress_callback=_progress)
        except Exception as e:
            logger.exception(f"task {task_id} failed: {e}")
            run_error = str(e)[:500]

        # ============ 3. 短事务：写最终状态 + 聚合父任务 ============
        async with session_factory() as session:
            t = await session.get(DownloadTask, task_id)
            if not t:
                return

            if outcome is not None:
                t.progress = 1.0
                t.audio_format = outcome.audio_format
                t.bitrate = outcome.bitrate
                t.quality = outcome.quality.value if outcome.quality else None
                t.file_size = outcome.file_size
                t.file_path = str(outcome.file_path) if outcome.file_path else None
                if outcome.skipped_dup:
                    t.status = "skipped_dup"
                elif outcome.success:
                    t.status = "success"
                else:
                    t.status = "failed"
                    t.error_msg = outcome.error
            else:
                t.status = "failed"
                t.error_msg = run_error or "unknown error"
            t.finished_at = utcnow()
            await session.commit()
            await session.refresh(t)

            done_snapshot = _serialize_task(t)
            source_subscription_ids = _task_subscription_ids(t)

            # 聚合父任务进度（仍在同一短事务内，因为 _aggregate_parent
            # 内部会 commit；进入这里时主任务的 commit 已完成，互斥窗口很小）
            for aggregate_parent_id in await self._parent_ids_for_child(
                session, task_id, parent_id
            ):
                await self._aggregate_parent(session, aggregate_parent_id)

            for source_subscription_id in source_subscription_ids:
                await self._refresh_subscription_m3u(session, source_subscription_id)

        self._broadcaster.publish_nowait(
            {"event": "task.updated", "task": done_snapshot}
        )

    async def _refresh_subscription_m3u(
        self, session: AsyncSession, subscription_id: int
    ) -> None:
        sub = await session.get(PlaylistSubscription, subscription_id)
        if not sub or sub.generate_m3u is False:
            return
        try:
            p = await generate_m3u_for_subscription(session, sub)
            if p:
                sub.m3u_file_path = str(p)
                await session.commit()
        except Exception as e:
            logger.warning(f"refresh subscription m3u failed sub#{subscription_id}: {e}")

    async def _aggregate_parent(self, session: AsyncSession, parent_id: int) -> None:
        """根据子任务状态汇总父任务进度。"""
        parent = await session.get(DownloadTask, parent_id)
        if not parent:
            return
        children_by_id = {
            c.id: c
            for c in (
                await session.scalars(
                    select(DownloadTask).where(DownloadTask.parent_task_id == parent_id)
                )
            ).all()
        }
        payload_child_ids = _json_int_list((parent.payload_json or {}).get("child_task_ids"))
        if payload_child_ids:
            referenced = (
                await session.scalars(
                    select(DownloadTask).where(DownloadTask.id.in_(payload_child_ids))
                )
            ).all()
            for child in referenced:
                children_by_id[child.id] = child
        children = list(children_by_id.values())
        total = len(children) or 1
        finished = [c for c in children if c.status in ("success", "skipped_dup", "failed", "cancelled")]
        succ = sum(1 for c in children if c.status == "success")
        skip = sum(1 for c in children if c.status == "skipped_dup")
        fail = sum(1 for c in children if c.status in ("failed", "cancelled"))
        parent.total_count = total
        parent.success_count = succ
        parent.skip_count = skip
        parent.fail_count = fail
        parent.progress = round(len(finished) / total, 3)
        if len(finished) >= total:
            parent.status = "success" if fail == 0 else "failed"
            parent.finished_at = utcnow()
        else:
            parent.status = "running"
            if not parent.started_at:
                parent.started_at = utcnow()
        await session.commit()
        await session.refresh(parent)
        self._broadcaster.publish_nowait(
            {"event": "task.updated", "task": _serialize_task(parent)}
        )

    async def _parent_ids_for_child(
        self, session: AsyncSession, child_task_id: int, direct_parent_id: Optional[int]
    ) -> list[int]:
        """找出需要随某个子任务完成而聚合的所有父任务。"""
        parent_ids: list[int] = []
        if direct_parent_id:
            parent_ids.append(direct_parent_id)
        parents = (
            await session.scalars(
                select(DownloadTask).where(
                    DownloadTask.target_type.in_(("playlist", "album")),
                    DownloadTask.status.in_(("queued", "running")),
                )
            )
        ).all()
        for parent in parents:
            payload_child_ids = _json_int_list((parent.payload_json or {}).get("child_task_ids"))
            if child_task_id in payload_child_ids and parent.id not in parent_ids:
                parent_ids.append(parent.id)
        return parent_ids

    # ---------- 辅助 ----------
    async def _make_platform(
        self, session: AsyncSession, pid: PlatformID
    ) -> Platform:
        acc = await session.scalar(
            select(Account).where(Account.platform == pid.value)
        )
        cookie = acc.cookie_json if acc and acc.is_valid else {}
        if pid is PlatformID.NETEASE:
            return NeteaseClient(cookie=cookie)
        if pid is PlatformID.QQ:
            return QQClient(cookie=cookie)
        raise RuntimeError(f"unknown platform: {pid}")

    async def _reload_song(
        self, session: AsyncSession, t: DownloadTask
    ) -> SongInfo:
        """从 task.payload_json 还原 SongInfo（避免 worker 再调一次 API）。"""
        p = t.payload_json or {}
        return SongInfo(
            platform=PlatformID(t.platform),
            platform_song_id=t.target_id,
            name=p.get("name") or t.title or "",
            artists=list(p.get("artists") or []),
            album=p.get("album"),
            album_id=p.get("album_id"),
            duration_ms=int(p.get("duration_ms") or 0),
            cover_url=p.get("cover_url"),
        )
