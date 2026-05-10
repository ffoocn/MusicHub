"""
本地库 API：浏览已下载的歌曲。

GET /api/library/songs                  歌曲列表（多维度筛选 + 分页）
    query:
      q          关键词（在 name/artist/album 全文匹配）
      artist     歌手精确匹配（normalized）
      album      专辑精确匹配
      sort       latest | name | duration（默认 latest）
      limit/offset 分页
GET /api/library/artists                歌手聚合（带歌曲数量）
GET /api/library/albums                 专辑聚合
GET /api/library/stream/{song_id}       本地音频流（前端 audio 直链播放本地文件）
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Song, SongSource
from app.db.session import get_session
from app.services.local_file_service import delete_local_song_file

router = APIRouter(prefix="/api/library", tags=["library"])

_AUDIO_MIME = {
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
}


def _serialize_song(s: Song) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "artist": s.artist,
        "album": s.album,
        "duration_ms": s.duration_ms,
        "audio_format": s.audio_format,
        "bitrate": s.bitrate,
        "file_size": s.file_size,
        "has_cover": s.has_cover,
        "has_lyric": s.has_lyric,
        "file_path": s.file_path,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "sources": [
            {"platform": src.platform, "platform_song_id": src.platform_song_id}
            for src in s.sources
        ],
    }


@router.get("/songs")
async def list_songs(
    q: Optional[str] = Query(default=None),
    artist: Optional[str] = None,
    album: Optional[str] = None,
    sort: str = Query(default="latest", regex="^(latest|name|duration)$"),
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Song)
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(Song.name.ilike(like), Song.artist.ilike(like), Song.album.ilike(like)))
    if artist:
        conds.append(Song.artist_norm == artist)
    if album:
        conds.append(Song.album == album)
    if conds:
        stmt = stmt.where(and_(*conds))

    if sort == "latest":
        stmt = stmt.order_by(Song.created_at.desc())
    elif sort == "name":
        stmt = stmt.order_by(Song.name)
    elif sort == "duration":
        stmt = stmt.order_by(Song.duration_ms)

    count_stmt = select(func.count(Song.id))
    if conds:
        count_stmt = count_stmt.where(and_(*conds))
    total = await session.scalar(count_stmt) or 0

    rows = (await session.scalars(stmt.limit(limit).offset(offset))).all()
    return {
        "items": [_serialize_song(s) for s in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


@router.get("/artists")
async def list_artists(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(
                Song.artist,
                Song.artist_norm,
                func.count(Song.id).label("song_count"),
            )
            .group_by(Song.artist, Song.artist_norm)
            .order_by(func.count(Song.id).desc())
        )
    ).all()
    return {
        "items": [
            {"name": r[0], "key": r[1], "song_count": int(r[2])} for r in rows
        ],
    }


@router.get("/albums")
async def list_albums(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(
                Song.album,
                Song.artist,
                func.count(Song.id).label("song_count"),
            )
            .where(Song.album.is_not(None))
            .group_by(Song.album, Song.artist)
            .order_by(func.count(Song.id).desc())
        )
    ).all()
    return {
        "items": [
            {"name": r[0], "artist": r[1], "song_count": int(r[2])} for r in rows
        ],
    }


@router.get("/song/{song_id}")
async def get_song_detail(song_id: int, session: AsyncSession = Depends(get_session)):
    s = await session.get(Song, song_id)
    if not s:
        raise HTTPException(status_code=404)
    return _serialize_song(s)


@router.delete("/song/{song_id}")
async def delete_song(song_id: int, session: AsyncSession = Depends(get_session)):
    """删除本地歌曲：移除库记录 + 物理文件（侧链 .lrc/.jpg 一起清理）。"""
    s = await session.get(Song, song_id)
    if not s:
        raise HTTPException(status_code=404)
    delete_result = None
    if s.file_path:
        delete_result = delete_local_song_file(s.file_path)
        if not delete_result.ok_for_db_delete:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "本地文件删除失败，已保留数据库记录",
                    "file_path": s.file_path,
                    "error": delete_result.error,
                },
            )
    await session.delete(s)
    await session.commit()
    return {
        "ok": True,
        "id": song_id,
        "file_deleted": bool(delete_result and delete_result.file_deleted),
        "missing_main": bool(delete_result and delete_result.missing_main),
        "sidecars_deleted": delete_result.sidecars_deleted if delete_result else [],
    }


# ==================================================================
# 本地封面（从音频文件中提取嵌入封面，或读取同名 sidecar 图片）
# ==================================================================
@router.get("/cover/{song_id}")
async def get_song_cover(song_id: int, session: AsyncSession = Depends(get_session)):
    s = await session.get(Song, song_id)
    if not s or not s.file_path:
        raise HTTPException(status_code=404)
    path = Path(s.file_path)
    if not path.exists():
        raise HTTPException(status_code=404)

    cache_headers = {"Cache-Control": "public, max-age=86400"}

    # 1) sidecar 图片
    for ext in ("jpg", "jpeg", "png"):
        sidecar = path.with_suffix("." + ext)
        if sidecar.exists():
            mime = "image/png" if ext == "png" else "image/jpeg"
            return FileResponse(sidecar, media_type=mime, headers=cache_headers)

    # 2) 内嵌封面
    try:
        from mutagen import File as MutagenFile  # type: ignore
        from mutagen.flac import Picture  # type: ignore
        from mutagen.id3 import APIC  # type: ignore
        from mutagen.mp4 import MP4Cover  # type: ignore

        m = MutagenFile(str(path))
        if m is None:
            raise HTTPException(status_code=404)

        # ID3 (MP3) — APIC frames
        tags = getattr(m, "tags", None)
        if tags is not None:
            try:
                for key in tags.keys():
                    if key.startswith("APIC"):
                        frame = tags[key]
                        if isinstance(frame, APIC) and frame.data:
                            return Response(content=frame.data, media_type=frame.mime or "image/jpeg", headers=cache_headers)
            except Exception:
                pass

        # FLAC pictures
        pictures = getattr(m, "pictures", None)
        if pictures:
            pic: Picture = pictures[0]
            return Response(content=pic.data, media_type=pic.mime or "image/jpeg", headers=cache_headers)

        # MP4 / M4A — covr atom
        try:
            covr = (tags or {}).get("covr") if tags is not None else None
        except Exception:
            covr = None
        if covr:
            cover = covr[0]
            mime = "image/png" if getattr(cover, "imageformat", None) == MP4Cover.FORMAT_PNG else "image/jpeg"
            return Response(content=bytes(cover), media_type=mime, headers=cache_headers)
    except HTTPException:
        raise
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="no cover")


# ==================================================================
# 本地文件流
# ==================================================================
@router.get("/stream/{song_id}")
async def stream_song(
    song_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    本地音频流式响应（支持 Range 断点续传，<audio> 拖动进度条用）。
    """
    s = await session.get(Song, song_id)
    if not s or not s.file_path:
        raise HTTPException(status_code=404)
    path = Path(s.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="本地文件不存在（可能已被移动/删除）")

    file_size = path.stat().st_size
    ext = path.suffix.lstrip(".").lower()
    mime = _AUDIO_MIME.get(ext, "application/octet-stream")
    range_header = request.headers.get("range")

    if not range_header:
        return FileResponse(
            path,
            media_type=mime,
            filename=path.name,
            headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        )

    # Range: bytes=START-END
    try:
        units, _, rng = range_header.partition("=")
        if units.strip().lower() != "bytes":
            raise ValueError
        start_s, _, end_s = rng.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
        if start < 0 or end >= file_size or start > end:
            raise ValueError
    except Exception:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    chunk_size = 1024 * 64

    def _iter() -> "any":
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                buf = f.read(min(chunk_size, remaining))
                if not buf:
                    break
                remaining -= len(buf)
                yield buf

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Content-Type": mime,
    }
    return StreamingResponse(_iter(), status_code=206, headers=headers, media_type=mime)
