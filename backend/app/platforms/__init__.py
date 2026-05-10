"""平台适配模块。所有平台实现都基于 base.Platform 接口契约。"""

from app.platforms.base import (
    AlbumInfo,
    ArtistInfo,
    DownloadResult,
    LoginQRCode,
    LoginStatus,
    PlatformID,
    PlaylistInfo,
    QualityLevel,
    SongInfo,
    SongSource,
)

__all__ = [
    "AlbumInfo",
    "ArtistInfo",
    "DownloadResult",
    "LoginQRCode",
    "LoginStatus",
    "PlatformID",
    "PlaylistInfo",
    "QualityLevel",
    "SongInfo",
    "SongSource",
]
