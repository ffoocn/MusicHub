"""
数据库 ORM 模型。

设计要点：
    - songs 表的 (name_norm, artist_norm, album_norm) 联合唯一索引是跨平台去重核心。
    - song_sources 表保存"同一首歌在哪些平台有"，用于挑选下载源。
    - 所有时间字段使用 UTC，前端展示时再做时区转换。

注意：
    SQLAlchemy 2.x 的 Mapped[] 注解会在运行时被反射 eval。
    为了同时兼容 Python 3.9 / 3.11，这里使用 Optional[X] 而不是 X | None。
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    """SQLAlchemy 2.x 风格基类。"""


# ==================================================================
# Song：已下载歌曲（去重核心）
# ==================================================================
class Song(Base):
    __tablename__ = "songs"
    __table_args__ = (
        UniqueConstraint("name_norm", "artist_norm", "album_norm", name="uq_song_dedup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str] = mapped_column(String(500))
    album: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    name_norm: Mapped[str] = mapped_column(String(500), index=True)
    artist_norm: Mapped[str] = mapped_column(String(500), index=True)
    album_norm: Mapped[str] = mapped_column(String(500))

    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    audio_format: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    has_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    has_lyric: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    sources: Mapped[List["SongSource"]] = relationship(
        back_populates="song", cascade="all, delete-orphan", lazy="selectin"
    )


# ==================================================================
# SongSource：歌曲多平台来源
# ==================================================================
class SongSource(Base):
    __tablename__ = "song_sources"
    __table_args__ = (
        UniqueConstraint("platform", "platform_song_id", name="uq_source_platform_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    platform_song_id: Mapped[str] = mapped_column(String(100), index=True)
    max_quality: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    song: Mapped["Song"] = relationship(back_populates="sources")


# ==================================================================
# PlaylistSubscription：订阅的歌单
# ==================================================================
class PlaylistSubscription(Base):
    __tablename__ = "playlist_subscriptions"
    # 注意：旧表里有 (platform, platform_playlist_id) 唯一约束。
    # 新增 target_type 后逻辑上应该是 (platform, target_type, platform_playlist_id)，
    # 但 SQLite 不能在 ALTER TABLE 修改约束，因此约束在应用层在 sync_service 中再做一次校验。
    __table_args__ = (
        UniqueConstraint("platform", "platform_playlist_id", name="uq_sub_platform_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    target_type: Mapped[str] = mapped_column(
        String(20), default="playlist", index=True
    )  # playlist | album
    platform_playlist_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creator: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_added: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_subscription_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    sync_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sync_track_count: Mapped[int] = mapped_column(Integer, default=0)
    last_sync_new_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tracks_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    # 上次同步时记录的「平台原始曲目 ID 列表」，用于 diff
    m3u_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # 是否生成 m3u8 文件。NULL 视为 True（兼容旧记录）
    generate_m3u: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=True)
    # 全平台聚合：开启时同步会同时拉另一平台的同名歌手/专辑，合并曲目
    cross_platform: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    # 另一平台对应的歌手/专辑 ID。留空时自动按名字搜索（保险起见建议手动指定）
    cross_platform_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # meta_hot_category 等扩展 meta：存 category / top_n / pool_size 等 JSON，普通歌单为 NULL
    meta_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ==================================================================
# DownloadTask：下载任务
# ==================================================================
class DownloadTask(Base):
    __tablename__ = "download_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_task_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    target_type: Mapped[str] = mapped_column(String(20))  # song | playlist | album
    target_id: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(20))
    source_subscription_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    sync_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    source_type: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True, default="manual"
    )
    source_subscription_ids_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    sync_run_ids_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    source_types_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sub_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # queued | running | success | failed | skipped_dup | cancelled
    priority: Mapped[int] = mapped_column(Integer, default=10)  # 0=auto，10=manual
    progress: Mapped[float] = mapped_column(default=0.0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1500), nullable=True)
    audio_format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ==================================================================
# SyncRun：订阅同步运行记录
# ==================================================================
class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    subscription_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    subscription_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    remote_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    enqueued: Mapped[int] = mapped_column(Integer, default=0)
    already_queued: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    skipped_local: Mapped[int] = mapped_column(Integer, default=0)
    task_ids_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    m3u_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    m3u_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ==================================================================
# SyncRunItem：订阅同步逐首处理明细
# ==================================================================
class SyncRunItem(Base):
    __tablename__ = "sync_run_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    platform_song_id: Mapped[str] = mapped_column(String(100), index=True)
    track_key: Mapped[str] = mapped_column(String(140), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    artist: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# ==================================================================
# Account：平台账号
# ==================================================================
class Account(Base):
    __tablename__ = "accounts"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    cookie_json: Mapped[Any] = mapped_column(JSON, default=dict)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    vip_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 平台官方 VIP 图标 URL 列表（JSON 数组，前端直接渲染图片）
    # 来源：QQ 取自 vip_login_base.userinfo.vecIcon[*].pic
    vip_icons: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ==================================================================
# Setting：键值对配置
# ==================================================================
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
