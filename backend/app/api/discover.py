"""
发现路由：搜索 + 单曲详情。

M2 阶段实现：
    GET /api/discover/search?q=...&platform=netease|qq|all&limit=20
    GET /api/discover/song/{platform}/{id}
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account
from app.db.session import get_session
from app.platforms.base import (
    AlbumInfo,
    ArtistInfo,
    Platform,
    PlatformID,
    PlaylistInfo,
    SongInfo,
)
from app.platforms.netease import NeteaseClient
from app.platforms.qq import QQClient
from app.utils.logger import logger

router = APIRouter(prefix="/api/discover", tags=["discover"])

_CATEGORY_ACTION_LABELS = {"全部", "全部分类", "全选"}


async def _make_platform(session: AsyncSession, pid: PlatformID) -> Platform:
    """根据数据库 Cookie 构造平台 client。"""
    acc = await session.scalar(select(Account).where(Account.platform == pid.value))
    cookie = acc.cookie_json if acc and acc.is_valid else {}
    if pid is PlatformID.NETEASE:
        return NeteaseClient(cookie=cookie)
    if pid is PlatformID.QQ:
        return QQClient(cookie=cookie)
    raise HTTPException(status_code=400, detail=f"unknown platform: {pid}")


def _song_to_dict(s: SongInfo) -> dict:
    """SongInfo → 前端友好的 dict。注意去掉 extra.raw（太大）。"""
    return {
        "platform": s.platform.value,
        "id": s.platform_song_id,
        "name": s.name,
        "artists": s.artists,
        "primary_artist": s.primary_artist,
        "album": s.album,
        "album_id": s.album_id,
        "duration_ms": s.duration_ms,
        "cover_url": s.cover_url,
    }


@router.get("/search")
async def search(
    q: str = Query(..., description="搜索关键词"),
    platform: Literal["netease", "qq", "all"] = "all",
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """全平台搜索（去重合并）。"""
    if not q.strip():
        return {"items": []}

    targets: list[PlatformID] = (
        [PlatformID.NETEASE, PlatformID.QQ] if platform == "all" else [PlatformID(platform)]
    )

    async def _search_one(pid: PlatformID) -> list[SongInfo]:
        try:
            cli = await _make_platform(session, pid)
            return await cli.search_songs(q, limit=limit)
        except Exception as e:
            logger.warning(f"search on {pid.value} failed: {e}")
            return []

    results = await asyncio.gather(*[_search_one(p) for p in targets])

    # 简单合并 + 按平台依次穿插
    merged: list[SongInfo] = []
    max_len = max((len(r) for r in results), default=0)
    for i in range(max_len):
        for r in results:
            if i < len(r):
                merged.append(r[i])

    return {"items": [_song_to_dict(s) for s in merged]}


@router.get("/song/{platform}/{song_id}")
async def get_song(
    platform: Literal["netease", "qq"],
    song_id: str,
    session: AsyncSession = Depends(get_session),
):
    """单曲详情。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    s = await cli.get_song(song_id)
    return _song_to_dict(s)


@router.get("/playlist/{platform}/{playlist_id}")
async def get_playlist(
    platform: Literal["netease", "qq"],
    playlist_id: str,
    session: AsyncSession = Depends(get_session),
):
    """歌单详情 + 完整曲目列表。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    info, songs = await cli.get_playlist(playlist_id)
    return {
        "platform": platform,
        "id": info.platform_playlist_id,
        "name": info.name,
        "description": info.description,
        "cover_url": info.cover_url,
        "creator": info.creator,
        "track_count": info.track_count or len(songs),
        "songs": [_song_to_dict(s) for s in songs],
    }


@router.get("/album/{platform}/{album_id}")
async def get_album(
    platform: Literal["netease", "qq"],
    album_id: str,
    session: AsyncSession = Depends(get_session),
):
    """专辑详情 + 完整曲目列表。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    info, songs = await cli.get_album(album_id)
    return {
        "platform": platform,
        "id": info.platform_album_id,
        "name": info.name,
        "description": info.description,
        "cover_url": info.cover_url,
        "artists": info.artists,
        "company": info.company,
        "track_count": info.track_count or len(songs),
        "songs": [_song_to_dict(s) for s in songs],
    }


# ==================================================================
# 发现页：每日推荐 / 推荐歌单 / 排行榜 / 热门歌单 / 我的歌单
# ==================================================================
def _playlist_to_dict(p: PlaylistInfo) -> dict:
    """PlaylistInfo → 前端 dict（不带 extra.raw）。"""
    return {
        "platform": p.platform.value,
        "id": p.platform_playlist_id,
        "name": p.name,
        "cover_url": p.cover_url,
        "description": p.description,
        "creator": p.creator,
        "track_count": p.track_count,
        "play_count": p.play_count,
    }


@router.get("/recommend/songs")
async def recommend_songs(
    platform: Literal["netease", "qq"] = "netease",
    mode: str = "default",
    limit: int = 30,
    session: AsyncSession = Depends(get_session),
):
    """每日推荐歌曲（需登录对应平台）。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    songs = await cli.recommend_songs_by_mode(mode=mode, limit=limit)
    return {"items": [_song_to_dict(s) for s in songs]}


@router.get("/recommend/playlists")
async def recommend_playlists(
    platform: Literal["netease", "qq"] = "netease",
    mode: str = "default",
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(25, ge=1, le=100, description="每页数量"),
    session: AsyncSession = Depends(get_session),
):
    """
    首页推荐歌单（个性化），按平台原生分页透传。

    返回字段：
        - items: 当页歌单列表
        - page / page_size：当前请求的分页参数
        - has_more：是否还可以继续翻页（来自平台原生字段）
    """
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    result = await cli.recommend_playlists_by_mode(mode=mode, page=page, page_size=page_size)
    return {
        "items": [_playlist_to_dict(p) for p in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_more": result.has_more,
    }


@router.get("/recommend/modes")
async def recommend_modes(
    platform: Literal["netease", "qq"] = "netease",
    session: AsyncSession = Depends(get_session),
):
    """返回平台支持的推荐模式（歌曲 + 歌单）。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    return {
        "song_modes": await cli.recommend_song_modes(),
        "playlist_modes": await cli.recommend_playlist_modes(),
    }


@router.get("/toplists")
async def top_lists(
    platform: Literal["netease", "qq"] = "netease",
    session: AsyncSession = Depends(get_session),
):
    """排行榜目录（飙升 / 新歌 / 热歌 / 原创 / 各语种榜）。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    pls = await cli.top_lists()
    return {"items": [_playlist_to_dict(p) for p in pls]}


@router.get("/hot/playlists")
async def hot_playlists(
    platform: Literal["netease", "qq"] = "netease",
    category: str = "全部",
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(25, ge=1, le=100, description="每页数量"),
    session: AsyncSession = Depends(get_session),
):
    """
    分类热门歌单（分页）。直接透传 `page / page_size` 给平台原生 API。

    返回字段：items / page / page_size / has_more。
    """
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    result = await cli.hot_playlists(category=category, page=page, page_size=page_size)
    return {
        "items": [_playlist_to_dict(p) for p in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_more": result.has_more,
    }


@router.get("/hot/playlist-categories")
async def list_hot_playlist_categories(
    platform: Literal["netease", "qq"] = "netease",
    session: AsyncSession = Depends(get_session),
):
    """
    动态热门订阅用的分类下拉数据。

    - 网易云：公开 ``/api/playlist/catalogue`` 广场分类。
    - QQ：``music.web_category_svr.get_hot_category`` 歌单广场分类（与广场拉歌单一致）。
    """
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    names = await cli.hot_playlist_categories()
    items = [n for n in names if str(n or "").strip() not in _CATEGORY_ACTION_LABELS]
    return {"items": items}


@router.get("/my/playlists")
async def my_playlists(
    platform: Literal["netease", "qq"] = "netease",
    session: AsyncSession = Depends(get_session),
):
    """我创建的 + 我收藏的歌单（需登录）。"""
    pid = PlatformID(platform)
    acc = await session.scalar(select(Account).where(Account.platform == pid.value))
    if not acc or not acc.is_valid or not acc.user_id:
        return {"created": [], "collected": [], "logged_in": False}
    cli = await _make_platform(session, pid)
    created, collected = await cli.user_playlists(acc.user_id)
    return {
        "created": [_playlist_to_dict(p) for p in created],
        "collected": [_playlist_to_dict(p) for p in collected],
        "logged_in": True,
        "user_id": acc.user_id,
        "nickname": acc.nickname,
    }


# ==================================================================
# 搜索建议（用于「手动添加订阅」对话框的自动补全）
# ==================================================================
def _artist_to_dict(a: ArtistInfo) -> dict:
    return {
        "platform": a.platform.value,
        "id": a.platform_artist_id,
        "name": a.name,
        "cover_url": a.cover_url,
        "alias": a.alias,
        "song_count": a.song_count,
        "album_count": a.album_count,
        "fans_count": a.fans_count,
    }


def _album_to_dict(a: AlbumInfo) -> dict:
    return {
        "platform": a.platform.value,
        "id": a.platform_album_id,
        "name": a.name,
        "cover_url": a.cover_url,
        "artists": a.artists,
        "publish_date": a.publish_date,
        "track_count": a.track_count,
    }


@router.get("/suggest/{kind}")
async def suggest(
    kind: Literal["playlist", "album", "artist"],
    q: str = Query(..., min_length=1),
    platform: Literal["netease", "qq"] = "netease",
    limit: int = 12,
    session: AsyncSession = Depends(get_session),
):
    """搜索建议（订阅/手动添加用）。返回该平台对应类型的前 N 个匹配项。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    try:
        if kind == "playlist":
            items = await cli.search_playlists(q, limit=limit)
            return {"items": [_playlist_to_dict(p) for p in items]}
        if kind == "album":
            items = await cli.search_albums(q, limit=limit)
            return {"items": [_album_to_dict(a) for a in items]}
        # artist
        items = await cli.search_artists(q, limit=limit)
        return {"items": [_artist_to_dict(a) for a in items]}
    except Exception as e:
        logger.warning(f"suggest {kind} on {platform} failed: {e}")
        return {"items": []}


@router.get("/artist/{platform}/{artist_id}")
async def get_artist(
    platform: Literal["netease", "qq"],
    artist_id: str,
    session: AsyncSession = Depends(get_session),
):
    """歌手详情：基本信息 + 热门歌曲 + 全部专辑。"""
    pid = PlatformID(platform)
    cli = await _make_platform(session, pid)
    info, hot_songs, albums = await cli.get_artist(artist_id)
    return {
        **_artist_to_dict(info),
        "hot_songs": [_song_to_dict(s) for s in hot_songs],
        "albums": [_album_to_dict(a) for a in albums],
    }
