"""
qqmusic_api 模型到项目统一 Platform 数据模型的映射工具。
"""

from __future__ import annotations

from typing import Any

from app.platforms.base import AlbumInfo, ArtistInfo, PlatformID, PlaylistInfo, SongInfo


def song_to_info(song: Any) -> SongInfo:
    artists = [s.name for s in getattr(song, "singer", []) if getattr(s, "name", "")]
    album = getattr(song, "album", None)
    album_mid = getattr(album, "mid", "") if album else ""
    album_name = getattr(album, "name", "") if album else ""
    cover_url = song.cover_url(500) if hasattr(song, "cover_url") else None
    return SongInfo(
        platform=PlatformID.QQ,
        platform_song_id=str(getattr(song, "mid", "")),
        name=getattr(song, "name", "") or getattr(song, "title", ""),
        artists=artists,
        album=album_name or None,
        album_id=album_mid or None,
        duration_ms=int(getattr(song, "interval", 0) or 0) * 1000,
        cover_url=cover_url or None,
        extra={"raw": song.model_dump(mode="json") if hasattr(song, "model_dump") else {}},
    )


def songlist_to_playlist(songlist: Any) -> PlaylistInfo:
    creator = None
    creator_obj = getattr(songlist, "creator", None)
    if creator_obj is not None:
        creator = getattr(creator_obj, "nick", None)
    creator = creator or getattr(songlist, "creator_nick", None)
    return PlaylistInfo(
        platform=PlatformID.QQ,
        platform_playlist_id=str(getattr(songlist, "id", 0) or getattr(songlist, "dirid", "")),
        name=getattr(songlist, "title", "") or getattr(songlist, "name", ""),
        cover_url=getattr(songlist, "picurl", "") or None,
        description=getattr(songlist, "desc", "") or None,
        creator=creator,
        track_count=int(getattr(songlist, "songnum", 0) or 0),
        play_count=int(getattr(songlist, "listennum", 0) or 0),
        extra={"raw": songlist.model_dump(mode="json") if hasattr(songlist, "model_dump") else {}},
    )


def album_to_info(album: Any, *, artists: list[str] | None = None, company: str | None = None) -> AlbumInfo:
    artist_names = artists or []
    if not artist_names:
        singer_list = getattr(album, "singer_list", None) or []
        artist_names = [s.name for s in singer_list if getattr(s, "name", "")]
    cover_url = album.cover_url(500) if hasattr(album, "cover_url") else None
    return AlbumInfo(
        platform=PlatformID.QQ,
        platform_album_id=str(getattr(album, "mid", "")),
        name=getattr(album, "name", "") or getattr(album, "title", ""),
        cover_url=cover_url or None,
        description=getattr(album, "desc", "") or getattr(album, "description", "") or None,
        artists=artist_names,
        publish_date=getattr(album, "time_public", "") or None,
        company=company or None,
        extra={"raw": album.model_dump(mode="json") if hasattr(album, "model_dump") else {}},
    )


def singer_to_artist(singer: Any) -> ArtistInfo:
    cover_url = singer.cover_url(500) if hasattr(singer, "cover_url") else getattr(singer, "pic", "")
    return ArtistInfo(
        platform=PlatformID.QQ,
        platform_artist_id=str(getattr(singer, "mid", "")),
        name=getattr(singer, "name", "") or getattr(singer, "title", ""),
        cover_url=cover_url or None,
        description=None,
        song_count=int(getattr(singer, "song_num", 0) or 0),
        album_count=int(getattr(singer, "album_num", 0) or 0),
        fans_count=int(getattr(singer, "fans", 0) or 0),
        extra={"raw": singer.model_dump(mode="json") if hasattr(singer, "model_dump") else {}},
    )


def plaza_v_playlist_to_playlist(d: dict[str, Any]) -> PlaylistInfo:
    """歌单广场 ``v_playlist`` 单条 → ``PlaylistInfo``（与 ``SongList`` 字段不同）。"""
    tid = d.get("tid")
    title = str(d.get("title") or "")
    ci = d.get("creator_info") if isinstance(d.get("creator_info"), dict) else {}
    nick = str(ci.get("nick") or "") if isinstance(ci, dict) else ""
    cover = (
        d.get("cover_url_medium")
        or d.get("cover_url_big")
        or d.get("cover_url_small")
        or ""
    )
    song_ids = d.get("song_ids") or []
    track_count = len(song_ids) if isinstance(song_ids, list) else 0
    return PlaylistInfo(
        platform=PlatformID.QQ,
        platform_playlist_id=str(tid) if tid is not None else "",
        name=title,
        cover_url=str(cover) if cover else None,
        description=None,
        creator=nick or None,
        track_count=track_count,
        play_count=int(d.get("access_num") or 0),
        extra={"raw": d},
    )


def top_to_playlist(top: Any) -> PlaylistInfo:
    cover_url = getattr(top, "front_pic_url", "") or getattr(top, "head_pic_url", "")
    return PlaylistInfo(
        platform=PlatformID.QQ,
        platform_playlist_id=f"top_{getattr(top, 'id', 0)}",
        name=getattr(top, "name", ""),
        cover_url=cover_url or None,
        description=getattr(top, "intro", "") or None,
        creator="QQ音乐",
        track_count=int(getattr(top, "total_num", 0) or 0),
        play_count=int(getattr(top, "listen_num", 0) or 0),
        extra={"raw": top.model_dump(mode="json") if hasattr(top, "model_dump") else {}},
    )

