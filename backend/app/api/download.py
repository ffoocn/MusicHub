"""
下载路由（M3：基于任务系统的异步下载）。

POST /api/download/song          单首入队
POST /api/download/songs         批量入队（多首）
POST /api/download/playlist      整个歌单入队（自动展开）
POST /api/download/album         整个专辑入队（自动展开）

兼容旧路径：单首支持 `?sync=true` 同步执行（M2 默认行为，无任务记录）。
"""

from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account
from app.db.session import get_session
from app.platforms.base import Platform, PlatformID, SongInfo
from app.platforms.netease import NeteaseClient
from app.platforms.qq import QQClient
from app.services.download_service import download_song
from app.services.task_manager import TaskManager

router = APIRouter(prefix="/api/download", tags=["download"])


class SongDownloadRequest(BaseModel):
    platform: Literal["netease", "qq"]
    id: str


class SongsDownloadRequest(BaseModel):
    platform: Literal["netease", "qq"]
    ids: list[str]


class PlaylistDownloadRequest(BaseModel):
    platform: Literal["netease", "qq"]
    id: str


async def _make_platform(session: AsyncSession, pid: PlatformID) -> Platform:
    acc = await session.scalar(select(Account).where(Account.platform == pid.value))
    cookie = acc.cookie_json if acc and acc.is_valid else {}
    if pid is PlatformID.NETEASE:
        return NeteaseClient(cookie=cookie)
    if pid is PlatformID.QQ:
        return QQClient(cookie=cookie)
    raise HTTPException(status_code=400, detail=f"unknown platform: {pid}")


# ==================================================================
# 单曲（默认走任务系统；支持 ?sync=true 同步直接下载）
# ==================================================================
@router.post("/song")
async def post_song(
    body: SongDownloadRequest,
    sync: bool = Query(default=False, description="同步等待完成（默认 false 走异步任务）"),
    session: AsyncSession = Depends(get_session),
):
    pid = PlatformID(body.platform)
    cli = await _make_platform(session, pid)
    song = await cli.get_song(body.id)

    if sync:
        outcome = await download_song(cli, song)
        return {
            "success": outcome.success,
            "skipped_dup": outcome.skipped_dup,
            "error": outcome.error,
            "file_path": str(outcome.file_path) if outcome.file_path else None,
            "audio_format": outcome.audio_format,
            "bitrate": outcome.bitrate,
            "quality": outcome.quality.value if outcome.quality else None,
            "file_size": outcome.file_size,
            "has_cover": outcome.has_cover,
            "has_lyric": outcome.has_lyric,
            "song": {
                "name": song.name,
                "artists": song.artists,
                "album": song.album,
                "duration_ms": song.duration_ms,
                "cover_url": song.cover_url,
            },
        }

    task_id = await TaskManager.get().enqueue_song(pid, song)
    return {"task_id": task_id, "song_name": song.name}


@router.post("/songs")
async def post_songs(
    body: SongsDownloadRequest,
    session: AsyncSession = Depends(get_session),
):
    """批量入队多首歌（任意 ID 来自同一平台）。"""
    pid = PlatformID(body.platform)
    cli = await _make_platform(session, pid)

    # 并发取详情
    sem = asyncio.Semaphore(5)

    async def _one(sid: str) -> SongInfo | None:
        async with sem:
            try:
                return await cli.get_song(sid)
            except Exception:
                return None

    results = await asyncio.gather(*[_one(s) for s in body.ids])
    songs = [s for s in results if s is not None]

    task_ids: list[int] = []
    for s in songs:
        tid = await TaskManager.get().enqueue_song(pid, s)
        task_ids.append(tid)
    return {"task_ids": task_ids, "enqueued": len(task_ids), "skipped_lookup": len(body.ids) - len(songs)}


# ==================================================================
# 歌单 / 专辑批量下载
# ==================================================================
@router.post("/playlist")
async def post_playlist(
    body: PlaylistDownloadRequest,
    session: AsyncSession = Depends(get_session),
):
    pid = PlatformID(body.platform)
    cli = await _make_platform(session, pid)
    info, songs = await cli.get_playlist(body.id)
    parent_id, child_ids = await TaskManager.get().enqueue_playlist(
        pid,
        playlist_id=info.platform_playlist_id,
        playlist_name=info.name,
        cover_url=info.cover_url,
        songs=songs,
        source_type="playlist_download",
    )
    return {
        "parent_task_id": parent_id,
        "child_task_ids": child_ids,
        "playlist_name": info.name,
        "song_count": len(songs),
    }


@router.post("/album")
async def post_album(
    body: PlaylistDownloadRequest,
    session: AsyncSession = Depends(get_session),
):
    pid = PlatformID(body.platform)
    cli = await _make_platform(session, pid)
    info, songs = await cli.get_album(body.id)
    parent_id, child_ids = await TaskManager.get().enqueue_playlist(
        pid,
        playlist_id=info.platform_album_id,
        playlist_name=info.name,
        cover_url=info.cover_url,
        songs=songs,
        source_type="album_download",
    )
    return {
        "parent_task_id": parent_id,
        "child_task_ids": child_ids,
        "album_name": info.name,
        "song_count": len(songs),
    }
