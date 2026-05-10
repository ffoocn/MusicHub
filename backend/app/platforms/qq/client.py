"""
QQ 音乐平台适配器（基于 qqmusic-api-python）。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from qqmusic_api import Client, Platform
from qqmusic_api.core.exceptions import LoginError
from qqmusic_api.models.login import QR, QRCodeLoginEvents, QRLoginType
from qqmusic_api.models.request import Credential
from qqmusic_api.modules.login_utils import QRCodeLoginSession
from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.song import SongFileInfo, SongFileType

from app.platforms.base import (
    AlbumInfo,
    ArtistInfo,
    DownloadResult,
    LoginQRCode,
    LoginResult,
    LoginStatus,
    PaginatedPlaylists,
    Platform as PlatformBase,
    PlatformID,
    PlaylistInfo,
    QualityLevel,
    SongInfo,
    SongSource,
)
from app.platforms.qq.credential import cookie_to_credential, credential_to_cookie
from app.platforms.qq.plaza import (
    fetch_qq_plaza_playlists_by_title_id,
    load_qq_plaza_category_names_and_ids,
    resolve_plaza_title_id,
)
from app.platforms.qq.mappers import (
    album_to_info,
    singer_to_artist,
    song_to_info,
    songlist_to_playlist,
    top_to_playlist,
)
from app.utils.logger import logger

# 用于剥离搜索接口返回的关键词高亮标签 <em>...</em>
import re as _re

_EM_TAG_RE = _re.compile(r"</?em>", flags=_re.IGNORECASE)


def _strip_em_tags(text: str) -> str:
    """去掉搜索结果中的 <em>...</em> 关键词高亮标签，仅保留文本。"""
    return _EM_TAG_RE.sub("", text)


class QQClient(PlatformBase):
    """QQ 音乐平台实现（qqmusic_api 适配层）。"""

    platform_id = PlatformID.QQ

    def __init__(
        self,
        cookie: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._cookie: dict[str, str] = cookie or {}
        self._timeout = timeout
        self._credential = cookie_to_credential(self._cookie)
        self._client = Client(
            credential=self._credential,
            platform=Platform.ANDROID,
            rate=20.0,
            capacity=100.0,
        )
        self._qr_map: dict[str, QR] = {}
        self._mobile_streams: dict[str, Any] = {}
        self._mobile_next_tasks: dict[str, asyncio.Task[Any]] = {}

    @property
    def cookie(self) -> dict[str, str]:
        return self._cookie

    def set_cookie(self, cookie: dict[str, str]) -> None:
        self._cookie = cookie
        self._credential = cookie_to_credential(cookie)
        self._client.credential = self._credential

    def _update_credential(self, credential: Credential, *, extra: dict[str, str] | None = None) -> None:
        self._credential = credential
        self._client.credential = credential
        self._cookie = credential_to_cookie(credential, extra=extra or self._cookie)

    def _build_login_result(
        self,
        credential: Credential,
        *,
        event: LoginStatus = LoginStatus.SUCCESS,
        raw_message: str | None = None,
    ) -> LoginResult:
        self._update_credential(credential)
        nickname = self._cookie.get("nick") or self._cookie.get("ptlogin_nick")
        avatar_url = self._cookie.get("avatar_url")
        vip_type = None
        vip_icons: list[str] = []
        try:
            vip = self._client.user.get_vip_info()
            vip_type = vip.userinfo.music_level
        except Exception:
            vip_type = None
        return LoginResult(
            platform=self.platform_id,
            status=event,
            cookie=dict(self._cookie),
            user_id=str(credential.musicid) if credential.musicid else None,
            nickname=nickname,
            vip_type=vip_type,
            vip_icons=vip_icons,
            avatar_url=avatar_url,
            raw_message=raw_message,
        )

    async def refresh_credential(self) -> bool:
        """尝试刷新凭证，成功返回 True。"""
        try:
            refreshed = await self._client.login.refresh_credential(self._credential)
        except Exception as e:
            logger.warning(f"[qq] refresh credential failed: {e}")
            return False
        self._update_credential(refreshed)
        return True

    async def _fetch_user_profile(self, uin: str) -> tuple[str | None, int | None, list[str], str | None]:
        nickname: str | None = None
        avatar_url: str | None = None
        vip_type: int | None = None
        vip_icons: list[str] = []
        try:
            homepage = await self._client.user.get_homepage(
                self._cookie.get("encryptUin") or self._credential.encrypt_uin or uin
            )
            nickname = homepage.base_info.name or None
            avatar_url = homepage.base_info.avatar or None
        except Exception as e:
            logger.debug(f"[qq] get_homepage failed: {e}")
        try:
            vip = await self._client.user.get_vip_info()
            vip_type = vip.userinfo.music_level
        except Exception as e:
            logger.debug(f"[qq] get_vip_info failed: {e}")
        return nickname, vip_type, vip_icons, avatar_url

    async def create_qr_login(self) -> LoginQRCode:
        qr = await self._client.login.get_qrcode(QRLoginType.QQ)
        ticket = f"qq:{qr.identifier}"
        self._qr_map[ticket] = qr
        return LoginQRCode(
            platform=self.platform_id,
            ticket=ticket,
            qr_url="",
            qr_image_png=qr.data,
            created_at_ms=int(time.time() * 1000),
        )

    async def create_wx_qr_login(self) -> LoginQRCode:
        qr = await self._client.login.get_qrcode(QRLoginType.WX)
        ticket = f"wx:{qr.identifier}"
        self._qr_map[ticket] = qr
        return LoginQRCode(
            platform=self.platform_id,
            ticket=ticket,
            qr_url=f"https://open.weixin.qq.com/connect/qrcode/{qr.identifier}",
            qr_image_png=qr.data,
            created_at_ms=int(time.time() * 1000),
        )

    async def create_mobile_qr_login(self) -> LoginQRCode:
        session = QRCodeLoginSession(
            self._client.login,
            QRLoginType.MOBILE,
            interval=1.5,
            timeout_seconds=180.0,
            emit_repeat=False,
        )
        qr = await session.get_qrcode()
        ticket = f"mobile:{qr.identifier}"
        self._qr_map[ticket] = qr
        # 为每个 mobile ticket 保留一个持续事件流，避免每次 poll 重建 MQTT 会话。
        self._mobile_streams[ticket] = session.iter_events()
        return LoginQRCode(
            platform=self.platform_id,
            ticket=ticket,
            qr_url="",
            qr_image_png=qr.data,
            created_at_ms=int(time.time() * 1000),
        )

    async def _poll_qr(self, qr: QR) -> LoginResult:
        result = await self._client.login.check_qrcode(qr)
        if result.event == QRCodeLoginEvents.TIMEOUT:
            return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED)
        if result.event == QRCodeLoginEvents.SCAN:
            return LoginResult(platform=self.platform_id, status=LoginStatus.PENDING)
        if result.event == QRCodeLoginEvents.CONF:
            return LoginResult(platform=self.platform_id, status=LoginStatus.SCANNED)
        if result.event != QRCodeLoginEvents.DONE or not result.credential:
            return LoginResult(platform=self.platform_id, status=LoginStatus.UNKNOWN)
        credential = result.credential
        nickname, vip_type, vip_icons, avatar_url = await self._fetch_user_profile(str(credential.musicid))
        out = self._build_login_result(credential, event=LoginStatus.SUCCESS)
        out.nickname = nickname or out.nickname
        out.vip_type = vip_type
        out.vip_icons = vip_icons
        out.avatar_url = avatar_url
        if out.nickname:
            self._cookie["nick"] = out.nickname
        if out.avatar_url:
            self._cookie["avatar_url"] = out.avatar_url
        return out

    async def poll_qr_login(self, qr: LoginQRCode) -> LoginResult:
        qrobj = self._qr_map.get(qr.ticket)
        if not qrobj:
            return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED, raw_message="ticket not found")
        return await self._poll_qr(qrobj)

    async def poll_wx_qr_login(self, qr: LoginQRCode) -> LoginResult:
        return await self.poll_qr_login(qr)

    async def poll_mobile_qr_login(self, qr: LoginQRCode) -> LoginResult:
        if qr.ticket not in self._qr_map:
            return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED, raw_message="ticket not found")
        stream = self._mobile_streams.get(qr.ticket)
        if stream is None:
            return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED, raw_message="stream not found")
        try:
            task = self._mobile_next_tasks.get(qr.ticket)
            if task is None:
                task = asyncio.create_task(anext(stream))
                self._mobile_next_tasks[qr.ticket] = task
            event = await asyncio.wait_for(asyncio.shield(task), timeout=1.8)
            self._mobile_next_tasks.pop(qr.ticket, None)
            if event.event == QRCodeLoginEvents.DONE and event.credential:
                self._mobile_streams.pop(qr.ticket, None)
                self._mobile_next_tasks.pop(qr.ticket, None)
                return self._build_login_result(event.credential, event=LoginStatus.SUCCESS)
            if event.event == QRCodeLoginEvents.TIMEOUT:
                self._mobile_streams.pop(qr.ticket, None)
                self._mobile_next_tasks.pop(qr.ticket, None)
                return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED)
            if event.event == QRCodeLoginEvents.REFUSE:
                self._mobile_streams.pop(qr.ticket, None)
                self._mobile_next_tasks.pop(qr.ticket, None)
                return LoginResult(platform=self.platform_id, status=LoginStatus.UNKNOWN, raw_message="refused")
            if event.event == QRCodeLoginEvents.CONF:
                return LoginResult(platform=self.platform_id, status=LoginStatus.SCANNED)
            if event.event == QRCodeLoginEvents.SCAN:
                return LoginResult(platform=self.platform_id, status=LoginStatus.PENDING)
            if event.event == QRCodeLoginEvents.OTHER:
                return LoginResult(platform=self.platform_id, status=LoginStatus.UNKNOWN, raw_message="mobile login failed")
            return LoginResult(platform=self.platform_id, status=LoginStatus.PENDING)
        except asyncio.TimeoutError:
            # 本次轮询窗口内无新事件，保持 pending 让前端继续轮询。
            return LoginResult(platform=self.platform_id, status=LoginStatus.PENDING)
        except StopAsyncIteration:
            self._mobile_streams.pop(qr.ticket, None)
            self._mobile_next_tasks.pop(qr.ticket, None)
            return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED, raw_message="stream ended")
        except Exception as e:
            logger.warning(f"[qq] poll mobile qr failed: {e}")
        return LoginResult(platform=self.platform_id, status=LoginStatus.PENDING)

    async def check_login(self) -> LoginResult:
        try:
            expired = await self._client.login.check_expired(self._credential)
            if expired:
                refreshed = await self.refresh_credential()
                if not refreshed:
                    return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED)
            nickname, vip_type, vip_icons, avatar_url = await self._fetch_user_profile(str(self._credential.musicid))
            result = self._build_login_result(self._credential, event=LoginStatus.SUCCESS)
            result.nickname = nickname or result.nickname
            result.vip_type = vip_type
            result.vip_icons = vip_icons
            result.avatar_url = avatar_url
            if result.nickname:
                self._cookie["nick"] = result.nickname
            if result.avatar_url:
                self._cookie["avatar_url"] = result.avatar_url
            return result
        except LoginError as e:
            return LoginResult(platform=self.platform_id, status=LoginStatus.EXPIRED, raw_message=str(e))
        except Exception as e:
            return LoginResult(platform=self.platform_id, status=LoginStatus.UNKNOWN, raw_message=str(e))

    async def search_songs(self, keyword: str, limit: int = 20, offset: int = 0) -> list[SongInfo]:
        page = max(1, offset // max(1, limit) + 1)
        resp = await self._client.search.search_by_type(
            keyword,
            search_type=SearchType.SONG,
            num=limit,
            page=page,
        )
        return [song_to_info(item) for item in resp.song]

    async def search_albums(self, keyword: str, limit: int = 20, offset: int = 0) -> list[AlbumInfo]:
        page = max(1, offset // max(1, limit) + 1)
        resp = await self._client.search.search_by_type(
            keyword,
            search_type=SearchType.ALBUM,
            num=limit,
            page=page,
        )
        return [album_to_info(item) for item in resp.album]

    async def search_playlists(self, keyword: str, limit: int = 20, offset: int = 0) -> list[PlaylistInfo]:
        page = max(1, offset // max(1, limit) + 1)
        resp = await self._client.search.search_by_type(
            keyword,
            search_type=SearchType.SONGLIST,
            num=limit,
            page=page,
        )
        return [songlist_to_playlist(item) for item in resp.songlist]

    async def search_artists(self, keyword: str, limit: int = 20, offset: int = 0) -> list[ArtistInfo]:
        page = max(1, offset // max(1, limit) + 1)
        resp = await self._client.search.search_by_type(
            keyword,
            search_type=SearchType.SINGER,
            num=limit,
            page=page,
        )
        return [singer_to_artist(item) for item in resp.singer]

    async def get_artist(self, artist_id: str) -> tuple[ArtistInfo, list[SongInfo], list[AlbumInfo]]:
        info = await self._client.singer.get_info(artist_id)
        singer = info.info
        artist = singer_to_artist(singer)
        desc = await self._client.singer.get_desc([artist_id])
        if desc.data:
            artist.description = desc.data[0].desc

        songs_resp = await self._client.singer.get_songs_list(artist_id, num=50, page=1)
        hot_songs = [song_to_info(s) for s in songs_resp.songs]

        albums: list[AlbumInfo] = []
        page = 1
        while page <= 20:
            alb_resp = await self._client.singer.get_album_list(artist_id, num=30, page=page)
            if not alb_resp.albums:
                break
            albums.extend([album_to_info(a, artists=[artist.name]) for a in alb_resp.albums])
            if len(alb_resp.albums) < 30:
                break
            page += 1
        artist.album_count = max(artist.album_count, len(albums))
        return artist, hot_songs, albums

    async def get_song(self, song_id: str) -> SongInfo:
        song = await self._client.song.get_detail(song_id)
        return song_to_info(song.track)

    async def get_album(self, album_id: str) -> tuple[AlbumInfo, list[SongInfo]]:
        detail = await self._client.album.get_detail(album_id)
        artists = [s.name for s in detail.singers if s.name]
        info = album_to_info(detail.album, artists=artists, company=detail.company.name)

        page_size = 500
        page = 1
        songs: list[SongInfo] = []
        while True:
            songs_resp = await self._client.album.get_song(album_id, num=page_size, page=page)
            page_songs = [song_to_info(s) for s in songs_resp.song_list]
            songs.extend(page_songs)
            total = int(getattr(songs_resp, "total", 0) or getattr(info, "track_count", 0) or 0)
            if not page_songs or len(page_songs) < page_size or (total and len(songs) >= total):
                break
            page += 1
        info.track_count = max(int(info.track_count or 0), len(songs))
        return info, songs

    async def get_playlist(self, playlist_id: str) -> tuple[PlaylistInfo, list[SongInfo]]:
        if playlist_id.startswith("top_"):
            top_id = int(playlist_id.split("_", 1)[1])
            top_detail = await self._client.top.get_detail(top_id, num=200, page=1)
            info = top_to_playlist(top_detail.info)
            songs = [song_to_info(s) for s in top_detail.songs]
            info.track_count = len(songs)
            return info, songs
        page_size = 500
        page = 1
        first_detail = await self._client.songlist.get_detail(int(playlist_id), num=page_size, page=page)
        info = songlist_to_playlist(first_detail.info)
        total = int(first_detail.total or 0)
        songs = [song_to_info(s) for s in first_detail.songs]
        while first_detail.songs and len(first_detail.songs) >= page_size and (not total or len(songs) < total):
            page += 1
            page_detail = await self._client.songlist.get_detail(int(playlist_id), num=page_size, page=page)
            page_songs = [song_to_info(s) for s in page_detail.songs]
            if not page_songs:
                break
            songs.extend(page_songs)
            if len(page_songs) < page_size:
                break
        info.track_count = total or len(songs)
        return info, songs

    async def get_lyric(self, song_id: str) -> str | None:
        lyric = await self._client.lyric.get_lyric(song_id, qrc=False, trans=False, roma=False)
        dec = lyric.decrypt()
        return dec.lyric or None

    def _quality_file_types(self, quality: QualityLevel) -> list[SongFileType]:
        if quality == QualityLevel.LOSSLESS:
            return [SongFileType.MASTER, SongFileType.ATMOS_2, SongFileType.FLAC]
        if quality == QualityLevel.EXHIGH:
            return [SongFileType.OGG_640, SongFileType.MP3_320]
        return [SongFileType.MP3_128]

    def _song_file_infos(self, song: SongInfo, file_type: SongFileType) -> list[SongFileInfo]:
        raw = song.extra.get("raw", {})
        media_mid = ((raw.get("file") or {}).get("media_mid")) if isinstance(raw, dict) else None
        return [SongFileInfo(mid=song.platform_song_id, file_type=file_type, media_mid=media_mid)]

    async def get_download_url(
        self,
        song: SongInfo,
        quality: QualityLevel = QualityLevel.LOSSLESS,
    ) -> DownloadResult:
        order = QualityLevel.descending()
        start = order.index(quality) if quality in order else 0
        for q in order[start:]:
            for ft in self._quality_file_types(q):
                try:
                    file_infos = self._song_file_infos(song, ft)
                    url_resp = await self._client.song.get_song_urls(file_infos, file_type=ft)
                    if not url_resp.data:
                        continue
                    item = url_resp.data[0]
                    if not item.purl:
                        continue
                    cdn = await self._client.song.get_cdn_dispatch()
                    if not cdn.sip:
                        continue
                    final_url = item.purl if item.purl.startswith("http") else cdn.sip[0] + item.purl
                    source = SongSource(
                        platform=self.platform_id,
                        platform_song_id=song.platform_song_id,
                        url=final_url,
                        quality=q,
                        audio_format=ft.e.lstrip("."),
                        bitrate=0,
                        file_size=None,
                        extra={"filename": item.filename, "result": item.result, "vkey": bool(item.vkey)},
                    )
                    return DownloadResult(
                        platform=self.platform_id,
                        platform_song_id=song.platform_song_id,
                        success=True,
                        source=source,
                    )
                except Exception as e:
                    logger.debug(f"[qq] get_download_url failed quality={q.value} type={ft.name}: {e}")
                    continue
        return DownloadResult(
            platform=self.platform_id,
            platform_song_id=song.platform_song_id,
            success=False,
            error="no available url for any quality/file type",
        )

    async def recommend_songs(self, limit: int = 30) -> list[SongInfo]:
        """
        默认推荐入口。

        历史背景：之前默认走 ``guess_recommend``，但实测发现：
          - 上游 SDK 把 ``num`` 写死成 5（``modules/recommend.py::get_guess_recommend``）；
          - 同时该接口对冷启动 / 偏好不足的账号经常返回空数组；
          - 导致用户面前的"猜你喜欢"经常 0 首。

        ``radar_recommend``（雷达推荐）实测稳定返回 10+ 首歌曲，作为默认更可靠。
        """
        return await self.recommend_songs_by_mode("radar_recommend", limit=limit)

    async def recommend_song_modes(self) -> list[dict[str, str]]:
        """
        QQ 推荐歌曲模式枚举。

        说明：原本还提供 "主页推荐 home_feed"，但 QQ ``RecommendFeed`` 接口
        本质是「楼层化混合卡片」（歌单/专辑/电台/有声书/MV 各种类型混合），
        不是纯歌曲流。把它当歌曲列表展示会把"有声书 / 助眠节目"等非歌曲
        当成歌曲推给用户，体验错位，因此从 modes 里删掉。
        想看主页推荐请走"推荐歌单"模式（``recommend_playlists_by_mode``）。
        """
        return [
            {"id": "radar_recommend", "label": "雷达推荐"},
            {"id": "recommend_newsong", "label": "推荐新歌"},
            {"id": "guess_recommend", "label": "猜你喜欢"},
        ]

    async def _guess_recommend_with_num(self, num: int) -> list[SongInfo]:
        """
        绕过 SDK ``get_guess_recommend()`` 写死 ``num=5`` 的限制：
        直接用 ``_build_request`` 自定义 ``num`` 参数发请求。

        接口路径：``music.radioProxy.MbTrackRadioSvr.get_radio_track``
        ``id=99`` 是"猜你喜欢"电台 ID。
        """
        from qqmusic_api.models.recommend import GuessRecommendResponse

        # 注意：调 protected ``_build_request`` 是 SDK 实现限制下的妥协做法，
        # 公开 API 没有暴露 num 参数；如果上游后续放开就改回 get_guess_recommend。
        req = self._client.recommend._build_request(  # type: ignore[arg-type]
            module="music.radioProxy.MbTrackRadioSvr",
            method="get_radio_track",
            param={
                "id": 99,
                "num": max(1, int(num)),
                "from": 0,
                "scene": 0,
                "song_ids": [],
            },
            response_model=GuessRecommendResponse,
        )
        resp = await req
        return [song_to_info(s) for s in resp.songs]

    async def recommend_songs_by_mode(self, mode: str, limit: int = 30) -> list[SongInfo]:
        """
        按模式拉取推荐歌曲。``limit`` 仅对 ``guess_recommend`` 起作用
        （其它模式由上游接口自己决定返回数量）。
        """
        if mode == "guess_recommend":
            try:
                # 把 num 设大一些，避免 SDK 默认 5 太少；冷启动用户可能仍空
                songs = await self._guess_recommend_with_num(num=max(20, int(limit or 30)))
                if songs:
                    return songs
            except Exception as e:
                logger.warning(f"[qq] guess_recommend with custom num failed: {e}")
            # 兜底：调 SDK 默认实现（num=5）
            try:
                resp = await self._client.recommend.get_guess_recommend()
                return [song_to_info(s) for s in resp.songs]
            except Exception as e:
                logger.warning(f"[qq] get_guess_recommend fallback failed: {e}")
                return []

        if mode == "radar_recommend":
            try:
                resp = await self._client.recommend.get_radar_recommend(page=1)
                return [song_to_info(s) for s in resp.songs]
            except Exception as e:
                logger.warning(f"[qq] get_radar_recommend failed: {e}")
                return []

        if mode == "recommend_newsong":
            try:
                resp = await self._client.recommend.get_recommend_newsong()
                return [song_to_info(s) for s in resp.songs]
            except Exception as e:
                logger.warning(f"[qq] get_recommend_newsong failed: {e}")
                return []

        # 旧 mode "home_feed" 已废弃（见 recommend_song_modes 注释）；
        # 兼容性：如果前端还传过来，回退到 radar 避免空白。
        if mode == "home_feed":
            logger.info("[qq] mode=home_feed 已废弃，回退到 radar_recommend")
            return await self.recommend_songs_by_mode("radar_recommend", limit=limit)

        return []

    async def recommend_playlist_modes(self) -> list[dict[str, str]]:
        return [{"id": "recommend_songlist", "label": "推荐歌单"}]

    async def recommend_playlists_by_mode(
        self,
        mode: str,
        page: int = 1,
        page_size: int = 25,
    ) -> PaginatedPlaylists:
        """
        QQ「推荐歌单广场」（``music.playlist.PlaylistSquare.GetRecommendFeed``）。

        直接把 ``page / page_size`` 透传给 ``recommend.get_recommend_songlist(page, num)``，
        并把响应体里的 ``has_more`` 原样返回给上层。
        """
        if mode != "recommend_songlist":
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)
        try:
            resp = await self._client.recommend.get_recommend_songlist(page=page, num=page_size)
        except Exception as e:
            logger.warning(f"[qq] get_recommend_songlist(page={page}, num={page_size}) failed: {e}")
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)
        items = [songlist_to_playlist(s) for s in (resp.songlists or [])]
        return PaginatedPlaylists(
            items=items,
            page=page,
            page_size=page_size,
            has_more=bool(getattr(resp, "has_more", False)),
        )

    async def top_lists(self) -> list[PlaylistInfo]:
        try:
            resp = await self._client.top.get_category()
        except Exception as e:
            logger.warning(f"[qq] top_lists failed: {e}")
            return []
        out: list[PlaylistInfo] = []
        for group in resp.group:
            for top in group.toplist:
                out.append(top_to_playlist(top))
        return out

    async def hot_playlists(
        self,
        category: str = "全部",
        page: int = 1,
        page_size: int = 25,
    ) -> PaginatedPlaylists:
        """
        QQ 平台的「分类热门歌单」（分页）。

        - ``category == "全部"`` / 空 → ``recommend.get_recommend_songlist``（推荐广场）。
        - 名称命中分类目录（``y.qq.com/n/ryqq_v2/category``）→ ``get_playlist_by_category``。
        - 仍拿不到结果（如 Chill Vibes 等广场虚拟分类）→ 降级歌单搜索 ``search_by_type``。

        分类名既支持 ``"流派 · 民谣"`` 格式，也兼容旧订阅里的纯名 ``"民谣"``。
        """
        keyword = (category or "").strip()

        # 全部：与「推荐歌单」同源（PlaylistSquare）
        if keyword in ("", "全部"):
            try:
                resp = await self._client.recommend.get_recommend_songlist(page=page, num=page_size)
            except Exception as e:
                logger.warning(f"[qq] hot_playlists(全部) page={page} failed: {e}")
                return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)
            items = [songlist_to_playlist(s) for s in (resp.songlists or [])]
            return PaginatedPlaylists(
                items=items,
                page=page,
                page_size=page_size,
                has_more=bool(getattr(resp, "has_more", False)),
            )

        _, id_by_name = await load_qq_plaza_category_names_and_ids(timeout=self._timeout)
        title_id = resolve_plaza_title_id(keyword, id_by_name)
        if title_id is not None and title_id != 0:
            page_data = await fetch_qq_plaza_playlists_by_title_id(
                title_id=title_id,
                page=page,
                page_size=page_size,
                timeout=self._timeout,
            )
            if page_data.items:
                return page_data
            # 命中分类但拿不到歌单（部分广场虚拟分类如 Chill Vibes / AI 歌单）→ 走搜索兜底

        # 未命中广场分类（旧订阅纯关键词）或广场为空：降级歌单搜索
        # 搜索关键词去掉 "分组 · " 前缀，提升命中
        kw_for_search = keyword.split(" · ", 1)[-1] if " · " in keyword else keyword
        try:
            resp = await self._client.search.search_by_type(
                kw_for_search,
                search_type=SearchType.SONGLIST,
                num=page_size,
                page=page,
            )
        except Exception as e:
            logger.warning(f"[qq] hot_playlists search keyword={kw_for_search!r} page={page} failed: {e}")
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)

        raw_items = list(getattr(resp, "songlist", []) or [])
        items: list[PlaylistInfo] = []
        for raw in raw_items:
            info = songlist_to_playlist(raw)
            if info.name:
                info.name = _strip_em_tags(info.name)
            items.append(info)
        return PaginatedPlaylists(
            items=items,
            page=page,
            page_size=page_size,
            has_more=len(raw_items) >= page_size,
        )

    async def hot_playlist_categories(self) -> list[str]:
        """
        QQ 歌单广场分类列表，与 ``hot_playlists`` 一一对应。

        来源：``y.qq.com/n/ryqq_v2/category`` 网页 SSR 注入的 ``__INITIAL_DATA__``
        （热门 / 主题 / 场景 / 心情 / 年代 / 流派 / 语种 共约 80 项），
        失败时回退 ``music.web_category_svr.get_hot_category``。
        """
        names, _ = await load_qq_plaza_category_names_and_ids(timeout=self._timeout)
        return names

    async def user_playlists(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PlaylistInfo], list[PlaylistInfo]]:
        """
        获取用户的「创建的歌单」和「收藏的歌单」。

        QQ Music 的两个接口对 UIN 形式要求不同（这是历史 API 设计的坑）：
          - ``get_created_songlist`` 接收**数字 UIN**（``int(user_id)``）；
          - ``get_fav_songlist``     接收**加密 UIN（euin）**，
            对应 cookie ``encryptUin`` / ``Credential.encrypt_uin``。

        旧版本调用 ``get_fav_songlist(num=limit, page=page)`` 漏传 euin，
        QQ 服务端会因为 ``uin`` 为空而返回空列表 → 用户看不到收藏的歌单。
        现按照 QQMusicApi 仓库 ``modules/user.py`` 的接口定义补上 euin。
        """
        created: list[PlaylistInfo] = []
        collected: list[PlaylistInfo] = []

        # 1) 创建的歌单：数字 UIN
        try:
            created_resp = await self._client.user.get_created_songlist(int(user_id))
            created = [songlist_to_playlist(p) for p in created_resp.playlists]
        except Exception as e:
            logger.warning(f"[qq] get_created_songlist failed: {e}")

        # 2) 收藏的歌单：加密 UIN（euin）
        # 优先取 cookie 里登录服务端写下来的 encryptUin，再退到 Credential
        # 字段。两者通常都存在；老 cookie 没 encryptUin 时 Credential 仍可用。
        euin = (
            (self._cookie or {}).get("encryptUin")
            or getattr(self._credential, "encrypt_uin", "")
            or ""
        )
        if not euin:
            logger.warning(
                "[qq] get_fav_songlist: 缺少 encrypt_uin（请重新扫码登录），跳过收藏歌单"
            )
            return created, collected

        page = max(1, offset // max(1, limit) + 1)
        try:
            fav_resp = await self._client.user.get_fav_songlist(
                euin, page=page, num=limit
            )
            collected = [songlist_to_playlist(p) for p in fav_resp.playlists]
        except Exception as e:
            logger.warning(f"[qq] get_fav_songlist failed: {e}")
        return created, collected
