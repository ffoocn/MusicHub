"""
去重 + 入库服务。

核心：以 (name_norm, artist_norm, album_norm) 三元组判断"同一首歌"。
辅助：时长容忍 ±5 秒（不同录音版本通常时长差异较大）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Song, SongSource
from app.platforms.base import PlatformID, QualityLevel, SongInfo
from app.services.local_file_service import delete_local_song_file
from app.services.normalize import (
    make_dedupe_key,
    normalize_album_name,
    normalize_artists,
    normalize_song_name,
)
from app.utils.logger import logger


async def find_existing(session: AsyncSession, song: SongInfo) -> Optional[Song]:
    """
    查询是否已下载过同一首歌（跨平台合并）。

    匹配条件：name_norm + artist_norm + album_norm 三元组完全一致。
    时长辅助：若设置开启，且差异超过 5 秒，则认为是不同录音版本，不视为重复。
    """
    name_n, artist_n, album_n = make_dedupe_key(song.name, song.artists, song.album)
    stmt = select(Song).where(
        and_(
            Song.name_norm == name_n,
            Song.artist_norm == artist_n,
            Song.album_norm == album_n,
        )
    )
    existing = await session.scalar(stmt)
    if existing is None:
        return None

    # 时长辅助判断（如果两边都有时长）
    if existing.duration_ms and song.duration_ms:
        diff = abs(existing.duration_ms - song.duration_ms) / 1000.0
        if diff > 5.0:
            # 视为不同录音版本，不算重复
            return None
    return existing


async def upsert_song_and_source(
    session: AsyncSession,
    song: SongInfo,
    *,
    file_path: Optional[Path],
    file_size: Optional[int],
    audio_format: Optional[str],
    bitrate: Optional[int],
    quality: Optional[QualityLevel],
    has_cover: bool = False,
    has_lyric: bool = False,
    additional_sources: Optional[list[tuple[PlatformID, str]]] = None,
) -> Song:
    """
    入库逻辑：
        1. 查询是否已存在 → 存在则更新平台来源 + 返回
        2. 不存在则插入 Song + SongSource
    """
    name_n, artist_n, album_n = make_dedupe_key(song.name, song.artists, song.album)
    primary_artist = song.primary_artist

    existing = await find_existing(session, song)
    if existing:
        new_path = str(file_path) if file_path else None
        update_file_metadata = new_path is None
        if new_path:
            old_path = existing.file_path
            if not old_path or old_path == new_path or not Path(old_path).exists():
                existing.file_path = new_path
                update_file_metadata = True
            elif Path(new_path).exists():
                # 已有可播放文件时，不用新下载路径覆盖库记录，避免旧文件变成孤儿。
                cleanup = delete_local_song_file(new_path)
                if cleanup.error:
                    logger.warning(f"cleanup duplicate downloaded file failed: {new_path}: {cleanup.error}")
        if update_file_metadata:
            existing.file_size = file_size if file_size is not None else existing.file_size
            existing.audio_format = audio_format or existing.audio_format
            existing.bitrate = bitrate if bitrate is not None else existing.bitrate
        existing.has_cover = has_cover or existing.has_cover
        existing.has_lyric = has_lyric or existing.has_lyric
        # 追加平台来源（若该平台还没有）
        await _ensure_source(session, existing.id, song.platform, song.platform_song_id, quality)
        for platform, platform_song_id in additional_sources or []:
            await _ensure_source(session, existing.id, platform, platform_song_id, quality)
        return existing

    new_song = Song(
        name=song.name,
        artist=primary_artist,
        album=song.album,
        name_norm=name_n,
        artist_norm=artist_n,
        album_norm=album_n,
        duration_ms=song.duration_ms,
        file_path=str(file_path) if file_path else None,
        file_size=file_size,
        audio_format=audio_format,
        bitrate=bitrate,
        has_cover=has_cover,
        has_lyric=has_lyric,
    )
    session.add(new_song)
    await session.flush()  # 拿 id

    session.add(
        SongSource(
            song_id=new_song.id,
            platform=song.platform.value,
            platform_song_id=song.platform_song_id,
            max_quality=quality.value if quality else None,
        )
    )
    for platform, platform_song_id in additional_sources or []:
        await _ensure_source(session, new_song.id, platform, platform_song_id, quality)
    await session.commit()
    return new_song


async def _ensure_source(
    session: AsyncSession,
    song_id: int,
    platform: PlatformID,
    platform_song_id: str,
    quality: Optional[QualityLevel],
) -> None:
    """添加平台来源记录（若已存在则更新音质上限）。"""
    existing = await session.scalar(
        select(SongSource).where(
            and_(
                SongSource.platform == platform.value,
                SongSource.platform_song_id == platform_song_id,
            )
        )
    )
    if existing:
        if quality and (
            existing.max_quality is None
            or _quality_rank(quality.value) > _quality_rank(existing.max_quality)
        ):
            existing.max_quality = quality.value
        await session.commit()
        return
    session.add(
        SongSource(
            song_id=song_id,
            platform=platform.value,
            platform_song_id=platform_song_id,
            max_quality=quality.value if quality else None,
        )
    )
    await session.commit()


def _quality_rank(q: str) -> int:
    """音质排序：值越大越好。"""
    return {"lossless": 3, "exhigh": 2, "standard": 1}.get(q, 0)
