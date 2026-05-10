"""
平台抽象基类与统一数据模型。

所有平台（网易云、QQ 音乐，以及未来扩展的酷我）都必须实现 Platform 协议，
业务层只依赖这些抽象类型，不感知具体平台细节。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ==================================================================
# 平台标识
# ==================================================================
class PlatformID(str, Enum):
    """平台标识符，作为字符串枚举方便与数据库交互。"""

    NETEASE = "netease"
    QQ = "qq"


# ==================================================================
# 音质等级
# ==================================================================
class QualityLevel(str, Enum):
    """统一的音质等级（按优先级从高到低排序）。"""

    LOSSLESS = "lossless"  # FLAC 无损
    EXHIGH = "exhigh"      # 320k / 640k 高码率
    STANDARD = "standard"  # 128k 标准

    @classmethod
    def descending(cls) -> list["QualityLevel"]:
        """按优先级从高到低返回所有等级，便于降级遍历。"""
        return [cls.LOSSLESS, cls.EXHIGH, cls.STANDARD]


# ==================================================================
# 登录相关
# ==================================================================
@dataclass
class LoginQRCode:
    """二维码登录所需信息。"""

    platform: PlatformID
    # 用于轮询的票据（网易云 unikey、QQ qrsig 等）
    ticket: str
    # 二维码内容（URL，前端用 qrcode 库渲染成图）
    qr_url: str
    # 二维码 PNG 二进制（部分平台只返回图片，比如 QQ 的 ptqrshow）
    qr_image_png: bytes | None = None
    # 创建时间戳（毫秒），用于过期判断
    created_at_ms: int = 0


class LoginStatus(str, Enum):
    """登录轮询状态。"""

    EXPIRED = "expired"
    PENDING = "pending"      # 等待扫码
    SCANNED = "scanned"      # 已扫码、等待确认
    SUCCESS = "success"      # 登录成功
    UNKNOWN = "unknown"


@dataclass
class LoginResult:
    """登录成功后的账号信息。"""

    platform: PlatformID
    status: LoginStatus
    # 完整 cookie，登录成功时填充
    cookie: dict[str, str] = field(default_factory=dict)
    # 平台账号 ID（网易 userId、QQ uin 数字字符串）
    user_id: str | None = None
    nickname: str | None = None
    vip_type: int | None = None
    # 平台官方 VIP 图标 URL 列表（前端直接显示真实图标，不依赖任何文字映射）
    # - QQ：取自 VipLogin.VipLoginInter 的 userinfo.vecIcon[*].pic（如 nsvip7.png 表 SVIP 7年）
    # - 网易云：暂未暴露官方图标 URL，置为空数组（前端按 vip_type 数字回退）
    vip_icons: list[str] = field(default_factory=list)
    # 账号头像 URL（用于在 Header 显示）
    avatar_url: str | None = None
    raw_message: str | None = None  # 接口原始消息，便于调试


# ==================================================================
# 媒体数据模型
# ==================================================================
@dataclass
class SongInfo:
    """单曲统一信息。"""

    platform: PlatformID
    platform_song_id: str           # 平台内 ID（网易 id / QQ songmid）
    name: str
    artists: list[str] = field(default_factory=list)
    album: str | None = None
    album_id: str | None = None
    duration_ms: int = 0
    cover_url: str | None = None
    # 平台原始字段透传（QQ 需要 songmid 和 album.mid 来构造下载和封面）
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_artist(self) -> str:
        """主歌手（用于去重和文件名）。"""
        return self.artists[0] if self.artists else "未知歌手"


@dataclass
class PlaylistInfo:
    """歌单统一信息。"""

    platform: PlatformID
    platform_playlist_id: str
    name: str
    cover_url: str | None = None
    description: str | None = None
    creator: str | None = None
    track_count: int = 0
    play_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaginatedPlaylists:
    """
    分页歌单结果，直接对齐底层 API 的「page / page_size / has_more」语义。

    Attributes:
        items: 当页歌单列表。
        page: 当前页码（从 1 开始）。
        page_size: 当前请求的每页数量。
        has_more: 是否还有更多数据可继续翻页。
            - 来源平台原生字段优先（如 QQ ``RecommendSonglistResponse.has_more``、
              网易云 ``playlist/list.more``）；
            - 缺乏原生字段时，以 ``len(items) >= page_size`` 估计。
    """

    items: list[PlaylistInfo] = field(default_factory=list)
    page: int = 1
    page_size: int = 0
    has_more: bool = False


@dataclass
class AlbumInfo:
    """专辑统一信息。"""

    platform: PlatformID
    platform_album_id: str
    name: str
    cover_url: str | None = None
    description: str | None = None
    artists: list[str] = field(default_factory=list)
    publish_date: str | None = None
    company: str | None = None
    track_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtistInfo:
    """歌手统一信息。"""

    platform: PlatformID
    platform_artist_id: str
    name: str
    cover_url: str | None = None
    description: str | None = None
    alias: list[str] = field(default_factory=list)
    song_count: int = 0
    album_count: int = 0
    fans_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


# ==================================================================
# 下载结果
# ==================================================================
@dataclass
class SongSource:
    """下载链接信息。"""

    platform: PlatformID
    platform_song_id: str
    url: str
    quality: QualityLevel
    audio_format: str           # mp3 / flac / ogg
    bitrate: int = 0
    file_size: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DownloadResult:
    """download_song 返回值，可能拿到 URL，也可能因为权限返回 None。"""

    platform: PlatformID
    platform_song_id: str
    success: bool
    source: SongSource | None = None
    error: str | None = None


# ==================================================================
# Platform 抽象基类
# ==================================================================
class Platform(ABC):
    """所有平台必须实现的接口契约。"""

    platform_id: PlatformID

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------
    @abstractmethod
    async def create_qr_login(self) -> LoginQRCode:
        """生成扫码登录二维码。"""

    @abstractmethod
    async def poll_qr_login(self, qr: LoginQRCode) -> LoginResult:
        """轮询扫码状态。每次调用查一次最新状态。"""

    @abstractmethod
    async def check_login(self) -> LoginResult:
        """根据当前 Cookie 检查登录态是否有效。"""

    # ------------------------------------------------------------------
    # 搜索 / 详情
    # ------------------------------------------------------------------
    @abstractmethod
    async def search_songs(self, keyword: str, limit: int = 20, offset: int = 0) -> list[SongInfo]:
        """搜索歌曲。"""

    @abstractmethod
    async def search_albums(self, keyword: str, limit: int = 20, offset: int = 0) -> list[AlbumInfo]:
        """搜索专辑。"""

    async def search_playlists(
        self, keyword: str, limit: int = 20, offset: int = 0
    ) -> list[PlaylistInfo]:
        """搜索歌单。默认返回空，子类按需重写。"""
        return []

    async def search_artists(
        self, keyword: str, limit: int = 20, offset: int = 0
    ) -> list[ArtistInfo]:
        """搜索歌手。默认返回空，子类按需重写。"""
        return []

    async def get_artist(
        self, artist_id: str
    ) -> tuple[ArtistInfo, list[SongInfo], list[AlbumInfo]]:
        """
        获取歌手详情：(基本信息, 热门歌曲, 全部专辑)。
        默认抛 NotImplementedError，子类按需重写。
        """
        raise NotImplementedError

    @abstractmethod
    async def get_song(self, song_id: str) -> SongInfo:
        """获取单曲详情。"""

    @abstractmethod
    async def get_album(self, album_id: str) -> tuple[AlbumInfo, list[SongInfo]]:
        """获取专辑详情和歌曲列表。"""

    @abstractmethod
    async def get_playlist(self, playlist_id: str) -> tuple[PlaylistInfo, list[SongInfo]]:
        """获取歌单详情和歌曲列表。"""

    @abstractmethod
    async def get_lyric(self, song_id: str) -> str | None:
        """获取 LRC 歌词文本，无歌词返回 None。"""

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------
    @abstractmethod
    async def get_download_url(
        self,
        song: SongInfo,
        quality: QualityLevel = QualityLevel.LOSSLESS,
    ) -> DownloadResult:
        """
        获取下载 URL。

        实现要求：
            - 按 quality 尝试，失败时自动降级到下一档，直到拿到 URL 或全部失败。
            - 拿到的 URL 可能有时效，调用方应尽快下载。
        """

    # ------------------------------------------------------------------
    # 发现页（每日推荐 / 热门歌单 / 我的歌单）
    # ------------------------------------------------------------------
    # 这几个方法默认返回空，平台可按需重写。
    # 这样新增一个平台不会被强制实现这些"高级"接口。

    async def recommend_songs(self, limit: int = 30) -> list[SongInfo]:
        """每日推荐歌曲（需登录）。默认返回空。"""
        return []

    async def recommend_song_modes(self) -> list[dict[str, str]]:
        """
        返回当前平台支持的“推荐歌曲模式”。

        每一项格式：
            {
                "id": "mode_id",
                "label": "模式名"
            }
        """
        return [{"id": "default", "label": "推荐歌曲"}]

    async def recommend_songs_by_mode(self, mode: str, limit: int = 30) -> list[SongInfo]:
        """
        按模式拉取推荐歌曲。默认仅支持 default，回退到 recommend_songs。
        """
        _ = mode
        return await self.recommend_songs(limit=limit)

    async def recommend_playlist_modes(self) -> list[dict[str, str]]:
        """返回当前平台支持的“推荐歌单模式”列表。"""
        return [{"id": "default", "label": "推荐歌单"}]

    async def recommend_playlists_by_mode(
        self,
        mode: str,
        page: int = 1,
        page_size: int = 25,
    ) -> PaginatedPlaylists:
        """
        按模式分页拉取推荐歌单。

        参数语义直接对齐平台原生 API（QQ：``page/num``，网易云：``offset/limit``），
        子类必须自己实现这两种语义间的换算，不要在客户端做隐式聚合 / 循环翻页。

        默认实现返回空页。
        """
        _ = mode
        return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)

    async def top_lists(self) -> list[PlaylistInfo]:
        """官方排行榜目录（飙升 / 新歌 / 热歌 ...），返回元数据列表。"""
        return []

    async def hot_playlists(
        self,
        category: str = "全部",
        page: int = 1,
        page_size: int = 25,
    ) -> PaginatedPlaylists:
        """
        分类热门歌单（分页）。

        ``category == "全部"`` 时由各平台决定使用哪个数据源（如 QQ 复用
        PlaylistSquare、网易云使用 ``playlist/list?cat=全部&order=hot``）。
        默认实现返回空页。
        """
        return PaginatedPlaylists(items=[], page=page, page_size=page_size, has_more=False)

    async def hot_playlist_categories(self) -> list[str]:
        """
        供「动态热门订阅」下拉使用的分类/关键词列表（来自平台接口，非前端写死）。

        网易云：歌单广场 ``/api/playlist/catalogue``；QQ：``get_hot_category`` 广场分类。
        均含 ``全部``。
        """
        return []

    async def user_playlists(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[PlaylistInfo], list[PlaylistInfo]]:
        """
        当前账号的歌单。

        返回 (created, collected) 两组：
            - created：用户自己创建的（含「我喜欢的音乐」红心）
            - collected：用户收藏的他人歌单
        默认返回 ([], [])。
        """
        return ([], [])
