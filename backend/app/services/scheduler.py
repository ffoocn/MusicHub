"""
后台定时调度。

设计：
    - 单进程 AsyncIOScheduler
    - 应用 lifespan 启动时拉取所有启用订阅，按 sync_interval_hours 注册定时 job
    - 每次同步后会触发对应 m3u 重新生成
    - 启动后立即跑一次（misfire_grace_time=120s 容错）
    - 订阅增删改时，调用 reload() 重新装配 jobs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.db.models import PlaylistSubscription
from app.db.session import session_factory
from app.services import sync_service
from app.utils.logger import logger


_scheduler: Optional[AsyncIOScheduler] = None


def _job_id(sub_id: int) -> str:
    return f"sub-sync-{sub_id}"


async def _run_sync_job(sub_id: int) -> None:
    """APScheduler 入口：执行一次同步。"""
    async with session_factory() as session:
        sub = await session.get(PlaylistSubscription, sub_id)
        if not sub:
            return
        ok, reason = await sync_service.can_sync_subscription(session, sub)
        if not ok:
            return
        try:
            report = await sync_service.sync_subscription(session, sub)
            logger.info(
                f"sync sub#{sub_id} {sub.name}: "
                f"remote={report.remote_count} new={report.new_count} "
                f"enqueued={report.enqueued} skipped_local={report.skipped_local}"
            )
        except Exception as e:
            sub.last_error = str(e)
            sub.last_sync_at = datetime.now(timezone.utc)
            await session.commit()
            logger.exception(f"sync sub#{sub_id} failed: {e}")


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def start() -> None:
    sch = get_scheduler()
    if not sch.running:
        sch.start()
        logger.info("scheduler started")
    await reload()


async def stop() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler stopped")


async def reload() -> None:
    """重新加载所有启用订阅的定时 job。"""
    sch = get_scheduler()
    # 清掉所有 sub-sync- 开头的 job
    for job in list(sch.get_jobs()):
        if job.id.startswith("sub-sync-"):
            try:
                sch.remove_job(job.id)
            except Exception:
                pass

    async with session_factory() as session:
        subs = (await session.execute(select(PlaylistSubscription))).scalars().all()

    by_id = {sub.id: sub for sub in subs}
    for sub in subs:
        if not sub.enabled:
            continue
        if sub.parent_subscription_id:
            parent = by_id.get(sub.parent_subscription_id)
            if not parent or not parent.enabled:
                continue
        register_subscription(sub)


def register_subscription(sub: PlaylistSubscription) -> None:
    """注册/更新单个订阅的 job。"""
    if not sub.enabled:
        return
    sch = get_scheduler()
    interval_hours = max(1, int(sub.sync_interval_hours or 24))
    # 距离上次同步还差多少小时；新订阅直接 1 分钟后跑一次
    next_run: datetime
    if sub.last_sync_at:
        last = sub.last_sync_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        nr = last + timedelta(hours=interval_hours)
        now = datetime.now(timezone.utc)
        next_run = nr if nr > now else now + timedelta(seconds=10)
    else:
        next_run = datetime.now(timezone.utc) + timedelta(seconds=30)

    sch.add_job(
        _run_sync_job,
        trigger=IntervalTrigger(hours=interval_hours, start_date=next_run),
        id=_job_id(sub.id),
        args=[sub.id],
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
    )
    logger.info(
        f"scheduler registered sub#{sub.id} {sub.name}: "
        f"every {interval_hours}h, next={next_run.isoformat()}"
    )


def unregister_subscription(sub_id: int) -> None:
    sch = get_scheduler()
    try:
        sch.remove_job(_job_id(sub_id))
        logger.info(f"scheduler unregistered sub#{sub_id}")
    except Exception:
        pass


async def trigger_now(sub_id: int) -> None:
    """立即跑一次（不影响下次定时）。"""
    await _run_sync_job(sub_id)
