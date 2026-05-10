"""
统计概览。

GET /api/stats/overview     总数 / 各平台 / 各音质 / 总时长 / 总大小 / 最近 14 天
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DownloadTask, Song, SongSource
from app.db.session import get_session

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def overview(session: AsyncSession = Depends(get_session)):
    total_songs = await session.scalar(select(func.count(Song.id))) or 0
    total_size = await session.scalar(select(func.coalesce(func.sum(Song.file_size), 0))) or 0
    total_duration_ms = (
        await session.scalar(select(func.coalesce(func.sum(Song.duration_ms), 0))) or 0
    )
    has_lyric = await session.scalar(
        select(func.count(Song.id)).where(Song.has_lyric == True)
    ) or 0
    has_cover = await session.scalar(
        select(func.count(Song.id)).where(Song.has_cover == True)
    ) or 0

    by_format = (
        await session.execute(
            select(Song.audio_format, func.count(Song.id))
            .group_by(Song.audio_format)
        )
    ).all()
    by_platform = (
        await session.execute(
            select(SongSource.platform, func.count(SongSource.id.distinct()))
            .group_by(SongSource.platform)
        )
    ).all()
    by_quality = (
        await session.execute(
            select(SongSource.max_quality, func.count(SongSource.id))
            .group_by(SongSource.max_quality)
        )
    ).all()

    # 最近 14 天每天的下载数
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=14)
    daily_rows = (
        await session.execute(
            select(
                func.date(Song.created_at),
                func.count(Song.id),
            )
            .where(Song.created_at >= since)
            .group_by(func.date(Song.created_at))
            .order_by(func.date(Song.created_at))
        )
    ).all()
    daily = [{"date": str(r[0]), "count": int(r[1])} for r in daily_rows]

    # 任务最近状态分布
    task_status = (
        await session.execute(
            select(DownloadTask.status, func.count(DownloadTask.id))
            .group_by(DownloadTask.status)
        )
    ).all()

    return {
        "total_songs": int(total_songs),
        "total_size_bytes": int(total_size),
        "total_duration_ms": int(total_duration_ms),
        "has_lyric": int(has_lyric),
        "has_cover": int(has_cover),
        "by_format": {(r[0] or "未知"): int(r[1]) for r in by_format},
        "by_platform": {r[0]: int(r[1]) for r in by_platform},
        "by_quality": {(r[0] or "未知"): int(r[1]) for r in by_quality},
        "by_task_status": {r[0]: int(r[1]) for r in task_status},
        "daily_recent": daily,
    }
