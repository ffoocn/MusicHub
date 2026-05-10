"""
网易云音乐平台客户端。

整合：
    - login.py：扫码登录
    - search.py：搜索歌曲、专辑
    - playlist.py：歌单详情
    - album.py：专辑详情
    - song.py：单曲详情、歌词
    - download.py：下载 URL
"""

from __future__ import annotations

import re
import secrets
import time
from typing import Any

import httpx

from app.crypto import netease_eapi, netease_linux, netease_weapi
from app.platforms.base import (
    AlbumInfo,
    ArtistInfo,
    DownloadResult,
    LoginQRCode,
    LoginResult,
    LoginStatus,
    PaginatedPlaylists,
    Platform,
    PlatformID,
    PlaylistInfo,
    QualityLevel,
    SongInfo,
    SongSource,
)
from app.platforms.playlist_square_catalogue import fetch_playlist_square_category_names
from app.utils.logger import logger

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class NeteaseClient(Platform):
    """网易云客户端。所有方法都是协程。"""

    platform_id = PlatformID.NETEASE

    # 基础默认 cookie（参考 NeteaseCloudMusicApi）
    # 这些字段能让 weapi 接口在未登录时也通过反爬校验、返回正常数据
    _BASE_COOKIE = {
        "os": "pc",
        "appver": "8.9.70",
        "__remember_me": "true",
        "channel": "netease",
    }

    def __init__(
        self,
        cookie: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._cookie: dict[str, str] = dict(self._BASE_COOKIE)
        if cookie:
            self._cookie.update(cookie)
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Cookie 访问
    # ------------------------------------------------------------------
    @property
    def cookie(self) -> dict[str, str]:
        return self._cookie

    def set_cookie(self, cookie: dict[str, str]) -> None:
        self._cookie = cookie

    def _csrf_token(self) -> str:
        return self._cookie.get("__csrf", "")

    # ------------------------------------------------------------------
    # 内部 HTTP 工具
    # ------------------------------------------------------------------
    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": _DEFAULT_UA,
            "Referer": "http://music.163.com/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if extra:
            headers.update(extra)
        return headers

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookie.items())

    @staticmethod
    def _collect_set_cookies(resp: "httpx.Response") -> dict[str, str]:
        """
        从响应头手工解析 Set-Cookie。

        httpx 的 resp.cookies 在收到多个同名 Set-Cookie 时会抛 CookieConflict
        （网易云会多次 set 同一个 key 用最后一次为准），
        我们直接取最后出现的值。
        """
        out: dict[str, str] = {}
        try:
            raw_list = resp.headers.get_list("set-cookie")  # type: ignore[attr-defined]
        except AttributeError:
            raw = resp.headers.get("set-cookie", "")
            raw_list = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
        for sc in raw_list:
            if not sc:
                continue
            first_seg = sc.split(";", 1)[0].strip()
            if "=" not in first_seg:
                continue
            k, _, v = first_seg.partition("=")
            k = k.strip()
            v = v.strip()
            if k and v and v.upper() != "EXPIRED":
                out[k] = v
        return out

    async def _ensure_anonymous_cookie(self) -> None:
        """
        首次请求前预热匿名 cookie。

        网易云 weapi 接口在未登录时必须带 MUSIC_A (匿名 token) 才能正常工作，
        否则扫码 poll 会一直返回 800（过期）、搜索返回 50000005。

        步骤：
            1. GET 首页拿 NMTID 等基础 cookie
            2. POST register/anonimous 拿匿名 token，写到 MUSIC_A
        """
        if self._cookie.get("MUSIC_U") or self._cookie.get("MUSIC_A"):
            return
        # 1. 拿基础 cookie
        if not self._cookie.get("NMTID"):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, follow_redirects=True
                ) as cli:
                    resp = await cli.get(
                        "https://music.163.com/",
                        headers={"User-Agent": _DEFAULT_UA, "Referer": "https://music.163.com/"},
                    )
                    self._cookie.update(self._collect_set_cookies(resp))
            except Exception as e:
                logger.warning(f"warmup base cookie failed: {e}")
        # 2. 拿匿名 token（不能调 _post_weapi 因为会递归）
        await self._fetch_anonymous_token()

    async def _fetch_anonymous_token(self) -> None:
        """
        调用 /api/register/anonimous 拿 MUSIC_A 匿名 token。

        参考 NeteaseCloudMusicApi 实现：
            - body: weapi 加密的 {username: <随机串>}
            - 响应 Set-Cookie 中含 MUSIC_A 或 MUSIC_A_T
        """
        try:
            url = "https://music.163.com/api/register/anonimous"
            device_id = secrets.token_hex(7).upper()
            username = f"{device_id} anonymous"
            encrypted = netease_weapi.encrypt({"username": username})
            headers = self._build_headers()
            headers["Cookie"] = self._cookie_header()

            async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=True
            ) as cli:
                resp = await cli.post(
                    url + "?csrf_token=",
                    data=encrypted.as_form(),
                    headers=headers,
                )
                # 优先从 Set-Cookie 抓
                got = False
                cookies_set = self._collect_set_cookies(resp)
                for k in ("MUSIC_A", "MUSIC_A_T"):
                    if cookies_set.get(k):
                        self._cookie["MUSIC_A"] = cookies_set[k]
                        got = True
                        break
                # 接口返回里也可能有 cookie 字段
                if not got:
                    try:
                        body = resp.json()
                        cookie_raw = body.get("cookie") or ""
                        if isinstance(cookie_raw, list):
                            cookie_raw = "; ".join(cookie_raw)
                        m = re.search(r"MUSIC_A_T=([^;]+)|MUSIC_A=([^;]+)", cookie_raw)
                        if m:
                            self._cookie["MUSIC_A"] = m.group(1) or m.group(2)
                            got = True
                    except Exception:
                        pass
                if not got:
                    # 这个接口需要 cloudmusicDllEncode 算法生成 username，
                    # 失败时其实不影响扫码流程，所以只 debug 日志
                    logger.debug(
                        f"register/anonimous no MUSIC_A returned: {resp.text[:120]}"
                    )
        except Exception as e:
            logger.warning(f"fetch anonymous token failed: {e}")

    async def _post_weapi(
        self,
        url: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """统一发起 weapi POST 请求并解析 JSON。"""
        await self._ensure_anonymous_cookie()
        encrypted = netease_weapi.encrypt(payload)
        headers = self._build_headers()
        if self._cookie:
            headers["Cookie"] = self._cookie_header()

        async with httpx.AsyncClient(timeout=timeout or self._timeout, follow_redirects=True) as cli:
            resp = await cli.post(url, data=encrypted.as_form(), headers=headers)
            resp.raise_for_status()
            # 收集响应 cookie 合并到客户端（登录时关键）
            self._cookie.update(self._collect_set_cookies(resp))
            return resp.json()

    async def _post_eapi(self, eapi_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """eapi 接口请求（高音质下载用）。"""
        encrypted_hex = netease_eapi.encrypt(eapi_path, payload)
        url = "https://interface3.music.163.com" + eapi_path
        headers = self._build_headers()
        if self._cookie:
            headers["Cookie"] = self._cookie_header()

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as cli:
            resp = await cli.post(url, data={"params": encrypted_hex}, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def _post_linux_api(self, url_inner: str, params: dict[str, Any]) -> dict[str, Any]:
        """Linux API 请求（专辑搜索用）。"""
        plain = {"url": url_inner, "params": params, "method": "post"}
        eparams = netease_linux.encrypt(plain)
        url = "http://music.163.com/api/linux/forward"
        headers = self._build_headers()
        if self._cookie:
            headers["Cookie"] = self._cookie_header()

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as cli:
            resp = await cli.post(url, data={"eparams": eparams}, headers=headers)
            resp.raise_for_status()
            return resp.json()

    # ==================================================================
    # 登录
    # ==================================================================
    async def create_qr_login(self) -> LoginQRCode:
        """生成扫码登录二维码。"""
        url = "https://music.163.com/weapi/login/qrcode/unikey?csrf_token="
        data = await self._post_weapi(url, {"type": "1"})
        if data.get("code") != 200:
            raise RuntimeError(f"create unikey failed: {data}")
        unikey = data["unikey"]
        return LoginQRCode(
            platform=self.platform_id,
            ticket=unikey,
            qr_url=f"https://music.163.com/login?codekey={unikey}",
            created_at_ms=int(time.time() * 1000),
        )

    async def poll_qr_login(self, qr: LoginQRCode) -> LoginResult:
        """
        轮询扫码状态。code: 800/801/802/803。

        payload 里需带 cookie='' 字段（与 NeteaseCloudMusicApi 一致），
        否则部分线路服务端会直接返回 800（误报过期）。
        """
        url = "https://music.163.com/weapi/login/qrcode/client/login?csrf_token="
        data = await self._post_weapi(
            url, {"type": "1", "key": qr.ticket, "cookie": ""}
        )
        code = data.get("code")
        msg = data.get("message", "")

        status_map = {
            800: LoginStatus.EXPIRED,
            801: LoginStatus.PENDING,
            802: LoginStatus.SCANNED,
            803: LoginStatus.SUCCESS,
        }
        if code not in status_map:
            logger.warning(f"netease poll unknown code={code}, raw={data}")
        status = status_map.get(code, LoginStatus.UNKNOWN)

        result = LoginResult(platform=self.platform_id, status=status, raw_message=msg)
        if status is LoginStatus.SUCCESS:
            # 此时 _post_weapi 已把 Set-Cookie 合并到 self._cookie
            result.cookie = dict(self._cookie)
            # 顺便取一下账号信息（含头像）
            try:
                info = await self.check_login()
                result.user_id = info.user_id
                result.nickname = info.nickname
                result.vip_type = info.vip_type
                result.avatar_url = info.avatar_url
            except Exception as e:
                logger.warning(f"check_login after qr success failed: {e}")
        return result

    async def check_login(self) -> LoginResult:
        """用当前 Cookie 查账号详情，验证登录态。"""
        url = "https://music.163.com/weapi/nuser/account/get"
        data = await self._post_weapi(url, {"csrf_token": self._csrf_token()})
        if data.get("code") != 200:
            return LoginResult(
                platform=self.platform_id,
                status=LoginStatus.EXPIRED,
                raw_message=str(data.get("code")),
            )
        profile = data.get("profile") or {}
        return LoginResult(
            platform=self.platform_id,
            status=LoginStatus.SUCCESS,
            cookie=dict(self._cookie),
            user_id=str(profile.get("userId", "")) if profile.get("userId") is not None else None,
            nickname=profile.get("nickname"),
            vip_type=profile.get("vipType"),
            avatar_url=profile.get("avatarUrl"),
        )

    # ==================================================================
    # 搜索
    # ==================================================================
    async def search_songs(self, keyword: str, limit: int = 20, offset: int = 0) -> list[SongInfo]:
        """
        搜索歌曲。

        优先使用 weapi cloudsearch（带富信息字段）；当未登录被风控时，
        回退到旧版未加密 GET 接口（无字段那么全，但能拿到关键 ID/名称）。
        """
        # 主路径：weapi
        url = "https://music.163.com/weapi/cloudsearch/get/web"
        payload = {
            "s": keyword,
            "type": 1,
            "limit": limit,
            "offset": offset,
            "csrf_token": self._csrf_token(),
        }
        try:
            data = await self._post_weapi(url, payload)
            if data.get("code") == 200 and data.get("result"):
                result = (data.get("result") or {}).get("songs") or []
                return [self._parse_song(item) for item in result]
            logger.info(f"netease weapi search code={data.get('code')}, fallback to legacy api")
        except Exception as e:
            logger.warning(f"netease weapi search failed: {e}, fallback to legacy api")

        # 回退：旧版 GET 接口
        return await self._search_songs_legacy(keyword, limit, offset)

    async def _search_songs_legacy(
        self, keyword: str, limit: int, offset: int
    ) -> list[SongInfo]:
        """旧版未加密搜索接口。匿名状态可用。"""
        url = "https://music.163.com/api/search/get/web"
        params = {
            "s": keyword,
            "type": 1,
            "limit": limit,
            "offset": offset,
        }
        headers = self._build_headers()
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as cli:
            resp = await cli.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        if data.get("code") != 200:
            return []
        items = ((data.get("result") or {}).get("songs")) or []
        return [self._parse_song(item) for item in items]

    async def search_albums(self, keyword: str, limit: int = 20, offset: int = 0) -> list[AlbumInfo]:
        """搜索专辑。Linux api 接口 type=10。"""
        result = await self._post_linux_api(
            "http://music.163.com/api/cloudsearch/pc",
            {"s": keyword, "type": 10, "offset": offset, "limit": limit},
        )
        items = (result.get("result") or {}).get("albums") or []
        return [self._parse_album_brief(item) for item in items]

    async def search_playlists(
        self, keyword: str, limit: int = 20, offset: int = 0
    ) -> list[PlaylistInfo]:
        """搜索歌单。type=1000。"""
        try:
            result = await self._post_linux_api(
                "http://music.163.com/api/cloudsearch/pc",
                {"s": keyword, "type": 1000, "offset": offset, "limit": limit},
            )
        except Exception as e:
            logger.warning(f"netease search_playlists failed: {e}")
            return []
        items = (result.get("result") or {}).get("playlists") or []
        return [self._parse_playlist_brief(it) for it in items]

    async def search_artists(
        self, keyword: str, limit: int = 20, offset: int = 0
    ) -> list["ArtistInfo"]:
        """搜索歌手。type=100。"""
        try:
            result = await self._post_linux_api(
                "http://music.163.com/api/cloudsearch/pc",
                {"s": keyword, "type": 100, "offset": offset, "limit": limit},
            )
        except Exception as e:
            logger.warning(f"netease search_artists failed: {e}")
            return []
        items = (result.get("result") or {}).get("artists") or []
        out: list[ArtistInfo] = []
        for it in items:
            aid = it.get("id")
            if aid is None:
                continue
            out.append(
                ArtistInfo(
                    platform=self.platform_id,
                    platform_artist_id=str(aid),
                    name=it.get("name") or "",
                    cover_url=it.get("img1v1Url") or it.get("picUrl") or None,
                    alias=list(it.get("alias") or []),
                    song_count=int(it.get("musicSize") or 0),
                    album_count=int(it.get("albumSize") or 0),
                    extra={"raw": it},
                )
            )
        return out

    async def get_artist(
        self, artist_id: str
    ) -> tuple["ArtistInfo", list[SongInfo], list[AlbumInfo]]:
        """歌手详情：基本信息 + 热门歌曲 + 全部专辑（自动翻页）。"""
        # 1) 基本信息 + top 50 热门
        url = "https://music.163.com/weapi/v1/artist/" + str(artist_id)
        try:
            data = await self._post_weapi(url, {"csrf_token": self._csrf_token()})
        except Exception as e:
            logger.warning(f"netease get_artist info failed: {e}")
            data = {}
        a_raw = data.get("artist") or {}
        info = ArtistInfo(
            platform=self.platform_id,
            platform_artist_id=str(artist_id),
            name=a_raw.get("name") or "",
            cover_url=a_raw.get("img1v1Url") or a_raw.get("picUrl"),
            description=a_raw.get("briefDesc"),
            alias=list(a_raw.get("alias") or []),
            song_count=int(a_raw.get("musicSize") or 0),
            album_count=int(a_raw.get("albumSize") or 0),
            extra={"raw": a_raw},
        )
        hot_songs = [self._parse_song(s) for s in (data.get("hotSongs") or [])]

        # 2) 全部专辑（翻页）
        albums: list[AlbumInfo] = []
        seen: set[str] = set()
        offset = 0
        page = 30
        for _ in range(20):  # 至多 600 张专辑
            try:
                d = await self._post_weapi(
                    "https://music.163.com/weapi/artist/albums/" + str(artist_id),
                    {"limit": page, "offset": offset, "total": True, "csrf_token": self._csrf_token()},
                )
            except Exception as e:
                logger.warning(f"netease artist/albums failed: {e}")
                break
            page_albums = d.get("hotAlbums") or []
            if not page_albums:
                break
            for it in page_albums:
                aid = str(it.get("id") or "")
                if not aid or aid in seen:
                    continue
                seen.add(aid)
                albums.append(self._parse_album_brief(it))
            if not d.get("more"):
                break
            offset += len(page_albums)

        info.album_count = max(info.album_count, len(albums))
        return info, hot_songs, albums

    # ==================================================================
    # 单曲详情 / 歌词
    # ==================================================================
    async def get_song(self, song_id: str) -> SongInfo:
        url = "https://music.163.com/weapi/v3/song/detail"
        payload = {
            "c": f'[{{"id":"{song_id}"}}]',
            "ids": f'["{song_id}"]',
        }
        data = await self._post_weapi(url, payload)
        songs = data.get("songs") or []
        if not songs:
            raise RuntimeError(f"song not found: {song_id}")
        return self._parse_song(songs[0])

    async def get_lyric(self, song_id: str) -> str | None:
        url = "https://music.163.com/weapi/song/lyric"
        payload = {
            "csrf_token": self._csrf_token(),
            "id": str(song_id),
            "lv": -1,
            "tv": -1,
            "rv": -1,
            "yv": -1,
        }
        data = await self._post_weapi(url, payload)
        if data.get("code") != 200:
            return None
        return ((data.get("lrc") or {}).get("lyric")) or None

    # ==================================================================
    # 歌单 / 专辑
    # ==================================================================
    async def get_playlist(self, playlist_id: str) -> tuple[PlaylistInfo, list[SongInfo]]:
        """获取歌单详情，n=0 取全部曲目 ID 后再批量取详情。"""
        url = "https://music.163.com/weapi/v3/playlist/detail"
        data = await self._post_weapi(
            url,
            {"id": str(playlist_id), "n": 100000, "csrf_token": self._csrf_token()},
        )
        if data.get("code") != 200:
            raise RuntimeError(f"playlist {playlist_id} fetch failed: code={data.get('code')}")
        pl = data["playlist"]
        info = PlaylistInfo(
            platform=self.platform_id,
            platform_playlist_id=str(pl.get("id")),
            name=pl.get("name") or "",
            cover_url=pl.get("coverImgUrl"),
            description=pl.get("description"),
            creator=(pl.get("creator") or {}).get("nickname"),
            track_count=int(pl.get("trackCount") or 0),
            play_count=int(pl.get("playCount") or 0),
        )
        # tracks 字段在 n != 0 时会直接返回完整歌曲对象
        tracks = pl.get("tracks") or []
        if tracks:
            songs = [self._parse_song(t) for t in tracks]
        else:
            # 兜底：用 trackIds 走批量详情
            ids = [str(t.get("id")) for t in (pl.get("trackIds") or [])]
            songs = await self._batch_song_detail(ids)
        return info, songs

    async def get_album(self, album_id: str) -> tuple[AlbumInfo, list[SongInfo]]:
        url = f"https://music.163.com/weapi/v1/album/{album_id}"
        data = await self._post_weapi(url, {"csrf_token": self._csrf_token()})
        if data.get("code") != 200:
            raise RuntimeError(f"album {album_id} fetch failed: {data}")
        album_raw = data.get("album") or {}
        info = AlbumInfo(
            platform=self.platform_id,
            platform_album_id=str(album_raw.get("id")),
            name=album_raw.get("name") or "",
            cover_url=album_raw.get("picUrl"),
            description=album_raw.get("description") or album_raw.get("briefDesc"),
            artists=[(album_raw.get("artist") or {}).get("name")] if album_raw.get("artist") else [],
            company=album_raw.get("company"),
            track_count=int(album_raw.get("size") or 0),
        )
        songs = [self._parse_song(t) for t in (data.get("songs") or [])]
        return info, songs

    async def _batch_song_detail(self, ids: list[str], chunk_size: int = 500) -> list[SongInfo]:
        """批量取歌曲详情。"""
        all_songs: list[SongInfo] = []
        for i in range(0, len(ids), chunk_size):
            batch = ids[i : i + chunk_size]
            url = "https://music.163.com/weapi/v3/song/detail"
            c = "[" + ",".join(f'{{"id":{x}}}' for x in batch) + "]"
            ids_field = "[" + ",".join(f'"{x}"' for x in batch) + "]"
            data = await self._post_weapi(url, {"c": c, "ids": ids_field})
            for s in data.get("songs") or []:
                all_songs.append(self._parse_song(s))
        return all_songs

    # ==================================================================
    # 下载 URL（eapi 高音质 + weapi 兜底）
    # ==================================================================
    async def get_download_url(
        self,
        song: SongInfo,
        quality: QualityLevel = QualityLevel.LOSSLESS,
    ) -> DownloadResult:
        # 网易云音质等级映射
        level_map = {
            QualityLevel.LOSSLESS: "lossless",
            QualityLevel.EXHIGH: "exhigh",
            QualityLevel.STANDARD: "standard",
        }

        # 按目标音质开始，按优先级降级
        descending = QualityLevel.descending()
        start_idx = descending.index(quality) if quality in descending else 0
        for q in descending[start_idx:]:
            try:
                src = await self._try_eapi(song, level_map[q])
                if src:
                    return DownloadResult(
                        platform=self.platform_id,
                        platform_song_id=song.platform_song_id,
                        success=True,
                        source=src,
                    )
            except Exception as e:
                logger.warning(f"eapi quality {q} failed: {e}")
        # 全部失败时兜底 weapi
        try:
            src = await self._try_weapi_url(song)
            if src:
                return DownloadResult(
                    platform=self.platform_id,
                    platform_song_id=song.platform_song_id,
                    success=True,
                    source=src,
                )
        except Exception as e:
            logger.warning(f"weapi url failed: {e}")
        return DownloadResult(
            platform=self.platform_id,
            platform_song_id=song.platform_song_id,
            success=False,
            error="no available url for any quality",
        )

    async def _try_eapi(self, song: SongInfo, level: str) -> SongSource | None:
        """尝试 eapi 高音质接口。"""
        eapi_path = "/eapi/song/enhance/player/url/v1"
        payload = {
            "ids": [int(song.platform_song_id)],
            "level": level,
            "encodeType": "flac",
            "header": '{"os":"pc","appver":"","osver":"","deviceId":"pyncm!","requestId":"12345678"}',
        }
        data = await self._post_eapi(eapi_path, payload)
        if data.get("code") != 200:
            return None
        items = data.get("data") or []
        if not items:
            return None
        d = items[0]
        url = d.get("url")
        if not url:
            return None
        actual_level = d.get("level") or level
        actual_q = self._level_to_quality(actual_level)
        return SongSource(
            platform=self.platform_id,
            platform_song_id=song.platform_song_id,
            url=url,
            quality=actual_q,
            audio_format=(d.get("type") or "mp3").lower(),
            bitrate=int(d.get("br") or 0),
            file_size=int(d.get("size") or 0) or None,
            extra={"raw": d},
        )

    async def _try_weapi_url(self, song: SongInfo) -> SongSource | None:
        """weapi 兜底接口。"""
        url = "http://music.163.com/weapi/song/enhance/player/url"
        payload = {"ids": [str(song.platform_song_id)], "br": 320000}
        data = await self._post_weapi(url, payload)
        if data.get("code") != 200:
            return None
        items = data.get("data") or []
        if not items or not items[0].get("url"):
            return None
        d = items[0]
        return SongSource(
            platform=self.platform_id,
            platform_song_id=song.platform_song_id,
            url=d["url"],
            quality=QualityLevel.EXHIGH,
            audio_format="mp3",
            bitrate=int(d.get("br") or 0),
            extra={"raw": d, "source": "weapi"},
        )

    @staticmethod
    def _level_to_quality(level: str) -> QualityLevel:
        if level in ("lossless", "hires"):
            return QualityLevel.LOSSLESS
        if level == "exhigh":
            return QualityLevel.EXHIGH
        return QualityLevel.STANDARD

    # ==================================================================
    # 发现：每日推荐 / 推荐歌单 / 排行榜 / 热门歌单 / 我的歌单
    # ==================================================================
    async def recommend_songs(self, limit: int = 30) -> list[SongInfo]:
        """
        每日推荐歌曲。

        优先调登录态 weapi 接口；如服务端风控返回 data=null（自托管/海外 IP
        下经常发生），自动回退到飙升榜（19723756）前 N 首作为兜底，
        保证用户在"每日推荐" tab 永远看到内容。
        """
        items: list[dict] = []
        if self._cookie.get("MUSIC_U"):
            url = "https://music.163.com/weapi/v3/discovery/recommend/songs"
            try:
                data = await self._post_weapi(url, {})
                if data.get("code") == 200:
                    d = data.get("data") or {}
                    items = d.get("dailySongs") or d.get("recommend") or []
            except Exception as e:
                logger.warning(f"recommend/songs failed: {e}")

        if items:
            return [self._parse_song(it) for it in items[:limit]]

        # 兜底：拉飙升榜
        try:
            _, songs = await self.get_playlist("19723756")
            return songs[:limit]
        except Exception as e:
            logger.warning(f"fallback toplist failed: {e}")
            return []

    async def recommend_playlist_modes(self) -> list[dict[str, str]]:
        return [{"id": "personalized", "label": "推荐歌单"}]

    async def recommend_playlists_by_mode(
        self,
        mode: str,
        page: int = 1,
        page_size: int = 25,
    ) -> PaginatedPlaylists:
        """
        网易云个性化推荐歌单（``/weapi/personalized/playlist``）。

        weapi 该接口仅支持 ``limit``，没有 ``offset``，所以这里一次性取
        ``page * page_size`` 条再做尾部切片，对外仍然给出 ``page / page_size /
        has_more`` 的统一分页语义。
        """
        if mode not in ("default", "personalized"):
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)

        want = max(1, page) * max(1, page_size)
        url = "https://music.163.com/weapi/personalized/playlist"
        payload: dict[str, Any] = {
            "total": True,
            "n": 1000,
            "limit": want,
            "csrf_token": self._csrf_token(),
        }
        try:
            data = await self._post_weapi(url, payload)
        except Exception as e:
            logger.warning(f"personalized/playlist page={page} failed: {e}")
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)
        if data.get("code") != 200:
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)

        all_items = [self._parse_playlist_brief(it) for it in (data.get("result") or [])]
        start = (page - 1) * page_size
        slice_items = all_items[start : start + page_size]
        has_more = bool(data.get("more")) or len(all_items) > start + page_size
        return PaginatedPlaylists(
            items=slice_items, page=page, page_size=page_size, has_more=has_more,
        )

    async def top_lists(self) -> list[PlaylistInfo]:
        """官方排行榜目录。"""
        url = "https://music.163.com/weapi/toplist/detail"
        try:
            data = await self._post_weapi(url, {"csrf_token": self._csrf_token()})
        except Exception as e:
            logger.warning(f"toplist/detail failed: {e}")
            return []
        if data.get("code") != 200:
            return []
        return [self._parse_playlist_brief(it) for it in (data.get("list") or [])]

    async def hot_playlists(
        self,
        category: str = "全部",
        page: int = 1,
        page_size: int = 25,
    ) -> PaginatedPlaylists:
        """
        分类热门歌单。category 例如：全部/华语/欧美/日语/韩语/纯音乐 ...

        weapi ``/playlist/list`` 原生支持 ``offset / limit``，并返回 ``more``
        字段表示是否还有下一页，这里直接透传 ``page / page_size``。
        """
        offset = max(0, page - 1) * max(1, page_size)
        url = "https://music.163.com/weapi/playlist/list"
        payload: dict[str, Any] = {
            "cat": category or "全部",
            "order": "hot",
            "offset": offset,
            "limit": page_size,
            "total": True,
            "csrf_token": self._csrf_token(),
        }
        try:
            data = await self._post_weapi(url, payload)
        except Exception as e:
            logger.warning(f"playlist/list cat={category!r} page={page} failed: {e}")
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)
        if data.get("code") != 200:
            return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)
        items = [
            self._parse_playlist_brief(it) for it in (data.get("playlists") or [])
        ]
        has_more = bool(data.get("more")) or len(items) >= page_size
        return PaginatedPlaylists(
            items=items, page=page, page_size=page_size, has_more=has_more,
        )

    async def hot_playlist_categories(self) -> list[str]:
        """歌单广场分类目录（公开 GET，无需登录）。"""
        return await fetch_playlist_square_category_names(timeout=self._timeout)

    async def user_playlists(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[PlaylistInfo], list[PlaylistInfo]]:
        """
        用户创建/收藏的歌单。

        网易云一次返回所有歌单，按 `subscribed`(true/false) 区分创建 vs 收藏。
        第一条通常就是「我喜欢的音乐」红心歌单（subscribed=False）。
        """
        if not user_id:
            return ([], [])
        url = "https://music.163.com/weapi/user/playlist"
        payload = {
            "uid": str(user_id),
            "limit": limit,
            "offset": offset,
            "includeVideo": False,
            "csrf_token": self._csrf_token(),
        }
        try:
            data = await self._post_weapi(url, payload)
        except Exception as e:
            logger.warning(f"user/playlist failed: {e}")
            return ([], [])
        if data.get("code") != 200:
            return ([], [])
        all_pl = data.get("playlist") or []
        created: list[PlaylistInfo] = []
        collected: list[PlaylistInfo] = []
        for it in all_pl:
            pi = self._parse_playlist_brief(it)
            if it.get("subscribed"):
                collected.append(pi)
            else:
                created.append(pi)
        return (created, collected)

    def _parse_playlist_brief(self, raw: dict[str, Any]) -> PlaylistInfo:
        """把网易云 playlist/recommend 项解析成统一的 PlaylistInfo。"""
        creator = raw.get("creator") or {}
        # 个性化推荐用 picUrl，user/playlist 用 coverImgUrl
        cover = raw.get("picUrl") or raw.get("coverImgUrl") or ""
        # trackCount 在不同接口字段名不同
        track_count = (
            raw.get("trackCount")
            or raw.get("songCount")
            or raw.get("trackNumberUpdateTime")
            or 0
        )
        # 热门播放量
        play_count = raw.get("playCount") or raw.get("playcount") or 0
        return PlaylistInfo(
            platform=self.platform_id,
            platform_playlist_id=str(raw.get("id")),
            name=raw.get("name") or "",
            cover_url=cover,
            description=raw.get("description") or raw.get("copywriter"),
            creator=creator.get("nickname") or raw.get("creatorName") or None,
            track_count=int(track_count) if isinstance(track_count, (int, float)) else 0,
            play_count=int(play_count) if isinstance(play_count, (int, float)) else 0,
            extra={"raw": raw},
        )

    # ==================================================================
    # 通用解析
    # ==================================================================
    def _parse_song(self, raw: dict[str, Any]) -> SongInfo:
        """统一解析歌曲对象。同时兼容 weapi 和 cloudsearch 字段命名。"""
        sid = raw.get("id")
        # 歌手字段：weapi v3 用 "ar"，老接口用 "artists"
        ar = raw.get("ar") or raw.get("artists") or []
        artists = [a.get("name") for a in ar if a.get("name")]
        # 专辑字段：weapi v3 用 "al"，老接口用 "album"
        al = raw.get("al") or raw.get("album") or {}
        return SongInfo(
            platform=self.platform_id,
            platform_song_id=str(sid),
            name=raw.get("name") or "",
            artists=artists,
            album=al.get("name"),
            album_id=str(al.get("id")) if al.get("id") is not None else None,
            duration_ms=int(raw.get("dt") or raw.get("duration") or 0),
            cover_url=al.get("picUrl"),
            extra={"raw": raw},
        )

    def _parse_album_brief(self, raw: dict[str, Any]) -> AlbumInfo:
        artists_raw = raw.get("artists") or ([raw.get("artist")] if raw.get("artist") else [])
        artists = [a.get("name") for a in artists_raw if a and a.get("name")]
        return AlbumInfo(
            platform=self.platform_id,
            platform_album_id=str(raw.get("id")),
            name=raw.get("name") or "",
            cover_url=raw.get("picUrl"),
            description=raw.get("description") or raw.get("briefDesc"),
            artists=artists,
            company=raw.get("company"),
            track_count=int(raw.get("size") or 0),
            extra={"raw": raw},
        )
