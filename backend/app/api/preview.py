"""
在线试听 URL 转发。

GET /api/preview/song/{platform}/{song_id}
    返回该曲目可直接 stream 的 URL（外链 mp3/flac），前端 audio 标签直接 src 这个 URL 播放。
    注意：URL 通常带平台签名 + 有时效（10~30 分钟）；前端不要长期缓存。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account
from app.db.session import get_session
from app.platforms.base import Platform, PlatformID, QualityLevel
from app.platforms.netease import NeteaseClient
from app.platforms.qq import QQClient

router = APIRouter(prefix="/api/preview", tags=["preview"])


async def _make_platform(session: AsyncSession, pid: PlatformID) -> Platform:
    acc = await session.scalar(select(Account).where(Account.platform == pid.value))
    cookie = acc.cookie_json if acc and acc.is_valid else {}
    if pid is PlatformID.NETEASE:
        return NeteaseClient(cookie=cookie)
    if pid is PlatformID.QQ:
        return QQClient(cookie=cookie)
    raise HTTPException(status_code=400, detail=f"unknown platform: {pid}")


@router.get("/song/{platform}/{song_id}")
async def get_preview_url(
    platform: Literal["netease", "qq"],
    song_id: str,
    quality: str = "standard",
    session: AsyncSession = Depends(get_session),
):
    """返回试听用的直链。默认 standard 音质，省流量；前端可传 quality=lossless 听高音质。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)

    try:
        q = QualityLevel(quality)
    except ValueError:
        q = QualityLevel.STANDARD

    song = await cli.get_song(song_id)
    result = await cli.get_download_url(song, q)
    if not result or not result.success or not result.source or not result.source.url:
        raise HTTPException(
            status_code=404,
            detail=result.error if result and result.error else "无可播放 URL（可能版权受限或未登录）",
        )
    src = result.source
    return {
        "url": src.url,
        "audio_format": src.audio_format,
        "bitrate": src.bitrate,
        "quality": src.quality.value if src.quality else None,
        "name": song.name,
        "artists": song.artists,
        "primary_artist": song.primary_artist,
        "album": song.album,
        "duration_ms": song.duration_ms,
        "cover_url": song.cover_url,
    }
