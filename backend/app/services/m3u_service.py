"""
M3U / M3U8 播放列表生成。

设计：
    - 一个订阅对应一个 .m3u8 文件（UTF-8 + #EXTINF: 元信息）
    - 文件内只放歌曲的"绝对本地文件路径"，因此本地播放器（Foobar / VLC / Plex）打开即可
    - 不在订阅里的歌曲不会被引用
    - 跨语种保留：m3u 把同一歌单的歌按原顺序写入，不二次按语种重排
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlaylistSubscription, Song, SongSource
from app.services import settings_service
from app.services.organize import safe_segment
from app.utils.logger import logger


_COVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


async def _save_cover(url: str | None, dest: Path) -> bool:
    """下载歌单封面到 dest（同名 .jpg）。失败返回 False，不抛异常。"""
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as cli:
            resp = await cli.get(url, headers=_COVER_HEADERS)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return True
    except Exception as e:
        logger.warning(f"playlist cover download failed: {url} -> {e}")
        return False


def _safe_filename(name: str) -> str:
    """歌单名转成可作为文件名的字符串。"""
    s = safe_segment(name) or "untitled"
    return s[:120]


def _render_m3u_filename(template: str, platform: str, name: str) -> str:
    """根据模板生成 m3u8 文件名（不含扩展名部分由调用方拼接）。"""
    safe_name = _safe_filename(name)
    try:
        rendered = template.format(platform=platform, name=safe_name)
    except (KeyError, IndexError):
        rendered = f"[{platform}] {safe_name}"
    rendered = rendered.strip() or safe_name or "untitled"
    # 整体再过一次安全字符过滤，避免模板里出现非法字符
    return safe_segment(rendered) or safe_name or "untitled"


async def collect_songs_for_subscription(
    session: AsyncSession, sub: PlaylistSubscription
) -> list[Song]:
    """
    根据订阅记录的曲目列表，从本地库挑出已下载的歌曲。

    匹配规则：以 (platform, platform_song_id) 命中 SongSource，
    再去取对应的 Song（要求 file_path 不为空）。
    """
    raw_track_ids: list[str] = [str(x) for x in list(sub.tracks_json or [])]
    if not raw_track_ids:
        return []

    parsed_keys: list[tuple[str, str]] = []
    for raw in raw_track_ids:
        if ":" in raw:
            platform, song_id = raw.split(":", 1)
            if platform and song_id:
                parsed_keys.append((platform, song_id))
        else:
            parsed_keys.append((sub.platform, raw))

    if not parsed_keys:
        return []

    rows = (
        await session.execute(
            select(SongSource).where(
                SongSource.platform.in_({p for p, _ in parsed_keys}),
                SongSource.platform_song_id.in_({sid for _, sid in parsed_keys}),
            )
        )
    ).scalars().all()

    parsed_key_set = set(parsed_keys)
    by_key: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r.platform, r.platform_song_id)
        if key not in parsed_key_set:
            continue
        if key in by_key and by_key[key] != r.song_id:
            logger.warning(f"duplicate song source mapping ignored for m3u: {key}")
            continue
        by_key[key] = r.song_id

    song_ids = [by_key[key] for key in parsed_keys if key in by_key]
    if not song_ids:
        return []

    songs = (
        await session.execute(
            select(Song).where(Song.id.in_(song_ids), Song.file_path.is_not(None))
        )
    ).scalars().all()

    by_id = {
        s.id: s
        for s in songs
        if s.file_path and Path(s.file_path).exists()
    }
    # 保留原顺序
    return [by_id[sid] for sid in song_ids if sid in by_id]


def _format_extinf(song: Song) -> str:
    """生成 m3u 行：#EXTINF:duration,artist - title"""
    duration = max(0, int((song.duration_ms or 0) / 1000))
    return f"#EXTINF:{duration},{song.artist} - {song.name}"


def _translate_song_path(file_path: str, music_root: Path, path_root: str | None) -> str:
    """
    把歌曲的真实绝对路径转成 m3u8 里的路径。

    path_root 非空时：用它替换 music_root 前缀（例如本机 /Users/.../music
    映射到容器里的 /music），保留后面的子目录与文件名。
    path_root 为空时：原样写绝对路径。
    """
    if not file_path or not path_root:
        return file_path
    try:
        rel = Path(file_path).resolve().relative_to(music_root.resolve())
    except ValueError:
        return file_path
    # 用正斜杠拼接，便于跨平台播放器读取
    rel_posix = rel.as_posix()
    return f"{path_root}/{rel_posix}"


async def generate_m3u_for_subscription(
    session: AsyncSession, sub: PlaylistSubscription
) -> Path | None:
    """
    生成 m3u8 文件，返回写入的绝对路径。

    没歌可写时不生成文件，返回 None。
    """
    songs = await collect_songs_for_subscription(session, sub)
    if not songs:
        logger.info(f"subscription #{sub.id} has no local songs, skip m3u")
        return None

    cfg = await settings_service.get_all(session)
    out_dir = settings_service.resolve_m3u_dir(cfg)
    music_root = settings_service.resolve_music_dir(cfg)
    path_root = settings_service.resolve_m3u_path_root(cfg)
    template = cfg.get("m3u.filename_template") or "[{platform}] {name}"
    base_name = _render_m3u_filename(template, sub.platform, sub.name)
    fpath = out_dir / f"{base_name}.m3u8"

    lines = ["#EXTM3U"]
    for s in songs:
        lines.append(_format_extinf(s))
        lines.append(_translate_song_path(s.file_path or "", music_root, path_root))
    fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"m3u generated: {fpath} ({len(songs)} tracks)")

    # 同步保存歌单封面（同名 .jpg），仅在远端有 cover_url 时
    if sub.cover_url:
        cover_path = out_dir / f"{base_name}.jpg"
        # 缺失时下载；如果远端 URL 已变（订阅刷新过）也重新下载
        if not cover_path.exists():
            await _save_cover(sub.cover_url, cover_path)

    return fpath


async def generate_all_m3u(session: AsyncSession) -> int:
    """对所有启用的订阅重新生成 m3u。返回写入文件数。"""
    subs = (
        await session.execute(
            select(PlaylistSubscription).where(PlaylistSubscription.enabled == True)
        )
    ).scalars().all()
    by_id = {sub.id: sub for sub in subs}
    count = 0
    for s in subs:
        if s.parent_subscription_id:
            parent = by_id.get(s.parent_subscription_id) or await session.get(
                PlaylistSubscription, s.parent_subscription_id
            )
            if not parent or not parent.enabled:
                continue
        # 关掉 m3u 生成的订阅跳过（None 视作开启，兼容旧记录）
        if s.generate_m3u is False:
            continue
        p = await generate_m3u_for_subscription(session, s)
        if p:
            s.m3u_file_path = str(p)
            count += 1
    await session.commit()
    return count
