"""
单首歌曲下载主流程。

流程：
    1. 查重：已存在直接返回 skip
    2. 拿下载 URL（音质降级 + 重试）
    3. 流式下载到临时文件
    4. 写入元数据（封面、歌词、ID3）
    5. 移到目标路径（按目录布局生成）
    6. 入库（song + song_source）
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx

from app.db.session import session_factory
from app.platforms.base import (
    DownloadResult,
    Platform,
    PlatformID,
    QualityLevel,
    SongInfo,
)
from app.services import dedupe, organize, settings_service, tag_service
from app.services.local_file_service import delete_local_song_file
from app.utils.logger import logger

_DOWNLOAD_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

ProgressCallback = Callable[[int, Optional[int]], Awaitable[None]]

_PATH_LOCKS: dict[str, asyncio.Lock] = {}


@dataclass
class DownloadOutcome:
    """下载结果汇报。"""

    success: bool
    skipped_dup: bool = False
    file_path: Optional[Path] = None
    audio_format: Optional[str] = None
    bitrate: Optional[int] = None
    quality: Optional[QualityLevel] = None
    file_size: Optional[int] = None
    has_cover: bool = False
    has_lyric: bool = False
    error: Optional[str] = None


def _path_lock(path: Path) -> asyncio.Lock:
    key = str(path)
    lock = _PATH_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _PATH_LOCKS[key] = lock
    return lock


# ==================================================================
# 下载主入口
# ==================================================================
async def download_song(
    platform: Platform,
    song: SongInfo,
    progress_callback: Optional[ProgressCallback] = None,
) -> DownloadOutcome:
    """
    单首下载完整流程，支持热路径短路（已存在直接 skip）。

    **关键设计：短事务化**
        本函数中的每次数据库访问都用「独立短事务」包裹，避免在长时间的
        HTTP / 文件 IO 期间持有 SQLite 连接和事务。这是为了解决多 worker
        / 后台 sync / 用户管理请求并发时频繁出现的 ``database is locked``
        错误：SQLAlchemy + aiosqlite + DEFERRED 事务在第一次 SELECT 之后会
        持有 connection，遇到长 IO 会让其它写者 30s 内全部超时。
    """
    # 1) 去重 —— 短事务
    async with session_factory() as session:
        existing = await dedupe.find_existing(session, song)
    if existing and existing.file_path and Path(existing.file_path).exists():
        logger.info(f"skip dedup hit: {song.name} - {song.primary_artist}")
        async with session_factory() as session:
            await dedupe.upsert_song_and_source(
                session,
                song,
                file_path=Path(existing.file_path),
                file_size=existing.file_size,
                audio_format=existing.audio_format,
                bitrate=existing.bitrate,
                quality=None,
                has_cover=existing.has_cover,
                has_lyric=existing.has_lyric,
            )
        return DownloadOutcome(
            success=True,
            skipped_dup=True,
            file_path=Path(existing.file_path),
            audio_format=existing.audio_format,
            bitrate=existing.bitrate,
            has_cover=existing.has_cover,
            has_lyric=existing.has_lyric,
        )
    if existing and existing.file_path and not Path(existing.file_path).exists():
        logger.info(f"dedup record missing file, redownload: {song.name} - {song.primary_artist}")

    # 2) 读用户设置 —— 短事务
    async with session_factory() as session:
        cfg = await settings_service.get_all(session)
    max_quality_str = cfg.get("download.max_quality", "lossless")
    quality_target = _parse_quality(max_quality_str)
    embed_cover = bool(cfg.get("meta.embed_cover", True))
    embed_lyric = bool(cfg.get("meta.embed_lyric", True))
    save_lrc = bool(cfg.get("meta.save_lrc_sidecar", True))
    save_cover = bool(cfg.get("meta.save_jpg_sidecar", False))
    write_id3 = bool(cfg.get("meta.write_id3_tags", True))
    layout = cfg.get("organize.dir_layout", "artist-album-song")
    fmt = cfg.get("organize.filename_format", "name-artist")
    retry_times = int(cfg.get("download.retry_times", 3))
    retry_backoff = list(cfg.get("download.retry_backoff_secs", [2, 5, 10]))

    # 3) 取下载 URL（含音质降级）
    original_song = song
    additional_sources: list[tuple[PlatformID, str]] = []
    dl_result = await _get_url_with_retry(platform, song, quality_target, retry_times, retry_backoff)
    if not dl_result.success or not dl_result.source:
        # 搜索兜底：原 songmid 被服务端拒绝时，用歌名+歌手搜索找可用版本
        alt = await _search_fallback(platform, song)
        if alt:
            logger.info(f"search fallback: {song.name} {song.platform_song_id} → {alt.platform_song_id}")
            dl_result = await _get_url_with_retry(platform, alt, quality_target, retry_times, retry_backoff)
            if dl_result.success and dl_result.source:
                # 用可下载版本入库，同时保留原始 ID 到 SongSource，便于订阅 M3U 按 tracks_json 命中。
                additional_sources.append((original_song.platform, original_song.platform_song_id))
                song = alt
    if not dl_result.success or not dl_result.source:
        return DownloadOutcome(success=False, error=dl_result.error or "no url")
    src = dl_result.source

    # 4) 目标路径（不再使用语种作为目录顶层）
    target_path = organize.build_absolute_path(
        song,
        src.audio_format,
        layout=layout,  # type: ignore[arg-type]
        filename_fmt=fmt,  # type: ignore[arg-type]
    )

    async with _path_lock(target_path):
        # 已经下载过（文件还在）但库里没记录的情况：跳过
        if target_path.exists():
            logger.info(f"file already exists, skip: {target_path}")
            # 仍然走入库，避免下次又判定重复但库里没数据 —— 短事务
            try:
                async with session_factory() as session:
                    saved_song = await dedupe.upsert_song_and_source(
                        session,
                        song,
                        file_path=target_path,
                        file_size=target_path.stat().st_size,
                        audio_format=src.audio_format,
                        bitrate=src.bitrate,
                        quality=src.quality,
                        has_cover=False,
                        has_lyric=False,
                        additional_sources=additional_sources,
                    )
                    if saved_song.file_path:
                        target_path = Path(saved_song.file_path)
            except Exception as e:
                return DownloadOutcome(success=False, error=f"db upsert failed: {e}")
            return DownloadOutcome(
                success=True,
                skipped_dup=True,
                file_path=target_path,
                audio_format=src.audio_format,
                bitrate=src.bitrate,
                quality=src.quality,
            )

        # 6) 流式下载到临时文件，再移过去
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = target_path.parent
        fd, tmp_name = tempfile.mkstemp(prefix=".dl_", suffix=f".{src.audio_format}", dir=tmp_dir)
        import os
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            size = await _stream_download(src.url, tmp_path, progress_callback)
        except Exception as e:
            tmp_path.unlink(missing_ok=True)
            return DownloadOutcome(success=False, error=f"download failed: {e}")

        try:
            # 7) 拉封面 / 歌词
            cover_bytes: Optional[bytes] = None
            if embed_cover or save_cover:
                cover_url = song.cover_url
                # 兜底：QQ 部分歌曲在搜索结果里没有 album.mid，靠 get_song 详情接口能拿到
                if not cover_url:
                    try:
                        detail = await platform.get_song(song.platform_song_id)
                        if detail.cover_url:
                            cover_url = detail.cover_url
                            song.cover_url = detail.cover_url
                            if not song.album and detail.album:
                                song.album = detail.album
                            if not song.album_id and detail.album_id:
                                song.album_id = detail.album_id
                    except Exception as e:
                        logger.debug(f"refetch song detail for cover failed: {e}")
                if cover_url:
                    try:
                        cover_bytes = await _fetch_bytes(cover_url)
                    except Exception as e:
                        logger.warning(f"fetch cover failed: {e}")

            lyric_text: Optional[str] = None
            if embed_lyric or save_lrc:
                try:
                    lyric_text = await platform.get_lyric(song.platform_song_id)
                except Exception as e:
                    logger.warning(f"fetch lyric failed: {e}")

            # 8) 写入标签
            if write_id3:
                tag_service.write_tags(
                    tmp_path,
                    song,
                    cover_bytes=cover_bytes if embed_cover else None,
                    lyric_text=lyric_text if embed_lyric else None,
                )

            # 9) 旁存
            if save_cover and cover_bytes:
                tag_service.save_sidecar_cover(target_path, cover_bytes)

            if save_lrc and lyric_text:
                tag_service.save_sidecar_lrc(target_path, lyric_text)

            # 10) 移到目标路径
            shutil.move(str(tmp_path), str(target_path))

            # 11) 入库 —— 短事务
            try:
                async with session_factory() as session:
                    saved_song = await dedupe.upsert_song_and_source(
                        session,
                        song,
                        file_path=target_path,
                        file_size=size,
                        audio_format=src.audio_format,
                        bitrate=src.bitrate,
                        quality=src.quality,
                        has_cover=bool(cover_bytes) and embed_cover,
                        has_lyric=bool(lyric_text) and embed_lyric,
                        additional_sources=additional_sources,
                    )
                    if saved_song.file_path:
                        target_path = Path(saved_song.file_path)
            except Exception as e:
                delete_local_song_file(target_path)
                return DownloadOutcome(success=False, error=f"db upsert failed: {e}")
        except Exception as e:
            tmp_path.unlink(missing_ok=True)
            delete_local_song_file(target_path)
            return DownloadOutcome(success=False, error=f"finalize failed: {e}")

    logger.info(
        f"downloaded ok: {song.name} - {song.primary_artist} | {src.audio_format} {src.bitrate}bps "
        f"({size / 1024 / 1024:.2f} MB) → {target_path}"
    )
    return DownloadOutcome(
        success=True,
        file_path=target_path,
        audio_format=src.audio_format,
        bitrate=src.bitrate,
        quality=src.quality,
        file_size=size,
        has_cover=bool(cover_bytes) and embed_cover,
        has_lyric=bool(lyric_text) and embed_lyric,
    )


# ==================================================================
# 工具
# ==================================================================
def _parse_quality(s: str) -> QualityLevel:
    try:
        return QualityLevel(s)
    except ValueError:
        return QualityLevel.LOSSLESS


async def _get_url_with_retry(
    platform: Platform,
    song: SongInfo,
    quality: QualityLevel,
    retry_times: int,
    backoff: list[int],
) -> DownloadResult:
    """带重试的 URL 获取。get_download_url 内部已经做了音质降级，外层只重试网络异常。"""
    last_err: Optional[str] = None
    for attempt in range(max(1, retry_times)):
        try:
            r = await platform.get_download_url(song, quality=quality)
            if r.success:
                return r
            last_err = r.error
        except Exception as e:
            last_err = str(e)
            logger.warning(f"get_download_url attempt {attempt + 1} failed: {e}")
        # 退避
        if attempt < retry_times - 1:
            wait = backoff[min(attempt, len(backoff) - 1)] if backoff else 2
            await asyncio.sleep(wait)
    return DownloadResult(
        platform=song.platform,
        platform_song_id=song.platform_song_id,
        success=False,
        error=last_err or "url retrieval failed",
    )


async def _stream_download(
    url: str,
    target: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> int:
    """下载到目标文件，返回字节数。"""
    written = 0
    headers = {"User-Agent": _DOWNLOAD_UA}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0), follow_redirects=True) as cli:
        async with cli.stream("GET", url, headers=headers) as r:
            r.raise_for_status()
            total_raw = r.headers.get("content-length")
            total = int(total_raw) if total_raw and total_raw.isdigit() else None
            with target.open("wb") as fp:
                async for chunk in r.aiter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    written += len(chunk)
                    if progress_callback:
                        await progress_callback(written, total)
    if progress_callback:
        await progress_callback(written, written)
    return written


async def _fetch_bytes(url: str) -> bytes:
    """同步下载小文件（封面）。"""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as cli:
        r = await cli.get(url, headers={"User-Agent": _DOWNLOAD_UA})
        r.raise_for_status()
        return r.content


async def _search_fallback(platform: Platform, song: SongInfo) -> Optional[SongInfo]:
    """URL 获取失败时，只用高置信度搜索结果兜底，避免把翻唱/Remix 绑到原曲 ID。"""
    try:
        query = f"{song.name} {song.primary_artist}".strip()
        results = await platform.search_songs(query, limit=10)
        for r in results:
            if r.platform_song_id == song.platform_song_id:
                continue
            if _is_safe_fallback_match(song, r):
                return r
    except Exception as e:
        logger.warning(f"search fallback failed for '{song.name}': {e}")
    return None


def _is_safe_fallback_match(original: SongInfo, candidate: SongInfo) -> bool:
    """兜底候选必须同名、同主歌手；双方有时长时还必须接近。"""
    if candidate.name.lower().strip() != original.name.lower().strip():
        return False
    if (
        candidate.primary_artist
        and original.primary_artist
        and candidate.primary_artist.lower().strip() != original.primary_artist.lower().strip()
    ):
        return False
    if candidate.duration_ms and original.duration_ms:
        if abs(candidate.duration_ms - original.duration_ms) > 5000:
            return False
    return True
