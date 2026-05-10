"""
订阅同步服务。

一次同步动作：
    1. 用对应平台 client 拉远端歌单/专辑 → 得到当前曲目列表
    2. 算 diff：找出本次新出现的曲目（不在 sub.tracks_json 里）
    3. 通过去重逻辑过滤掉本地已有的歌（避免重复入队）
    4. 把"未下载且新出现"的歌交给 TaskManager.enqueue_song()
    5. 更新 sub.tracks_json / last_sync_at / last_sync_track_count / last_sync_new_count
    6. 重新生成 m3u

返回一个 SyncReport 给调用方做日志/UI 反馈。
"""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, PlaylistSubscription, Song, SongSource, SyncRun, SyncRunItem
from app.db.session import session_factory
from app.platforms.base import Platform, PlatformID, PlaylistInfo, SongInfo
from app.platforms.netease import NeteaseClient
from app.platforms.qq import QQClient
from app.services import dedupe
from app.services.m3u_service import generate_m3u_for_subscription
from app.services.task_manager import TaskManager
from app.utils.logger import logger


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class SyncReport:
    subscription_id: int
    name: str
    remote_count: int = 0
    new_count: int = 0  # 远端新出现的曲目数（不一定全部入队）
    enqueued: int = 0  # 实际入队的数量
    already_queued: int = 0  # 已存在 queued/running 任务，直接复用
    skipped_local: int = 0  # 本地已有，跳过
    error: Optional[str] = None
    m3u_generated: bool = False
    m3u_error: Optional[str] = None
    task_ids: list[int] = field(default_factory=list)


@dataclass
class SyncBatch:
    id: str
    status: str = "running"
    total: int = 0
    completed: int = 0
    enqueued: int = 0
    already_queued: int = 0
    error: Optional[str] = None
    reports: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=utcnow)
    finished_at: Optional[datetime] = None


_SYNC_LOCKS: dict[int, asyncio.Lock] = {}
_SYNC_BATCHES: dict[str, SyncBatch] = {}


def _sync_lock(sub_id: int) -> asyncio.Lock:
    lock = _SYNC_LOCKS.get(sub_id)
    if lock is None:
        lock = asyncio.Lock()
        _SYNC_LOCKS[sub_id] = lock
    return lock


def _serialize_report(report: SyncReport) -> dict[str, Any]:
    return {
        "subscription_id": report.subscription_id,
        "name": report.name,
        "remote_count": report.remote_count,
        "new_count": report.new_count,
        "enqueued": report.enqueued,
        "already_queued": report.already_queued,
        "skipped_local": report.skipped_local,
        "task_ids": report.task_ids,
        "error": report.error,
        "m3u_generated": report.m3u_generated,
        "m3u_error": report.m3u_error,
    }


def serialize_batch(batch: SyncBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "status": batch.status,
        "total": batch.total,
        "completed": batch.completed,
        "enqueued": batch.enqueued,
        "already_queued": batch.already_queued,
        "error": batch.error,
        "reports": batch.reports,
        "started_at": batch.started_at.isoformat(),
        "finished_at": batch.finished_at.isoformat() if batch.finished_at else None,
    }


async def can_sync_subscription(
    session: AsyncSession, sub: PlaylistSubscription
) -> tuple[bool, Optional[str]]:
    if not sub.enabled:
        return False, "订阅已禁用"
    if sub.parent_subscription_id:
        parent = await session.get(PlaylistSubscription, sub.parent_subscription_id)
        if not parent:
            return False, "父级订阅不存在"
        if not parent.enabled:
            return False, "父级订阅已禁用"
    return True, None


def get_sync_batch(batch_id: str) -> Optional[SyncBatch]:
    return _SYNC_BATCHES.get(batch_id)


def start_sync_all_batch() -> SyncBatch:
    batch = SyncBatch(id=uuid.uuid4().hex[:12])
    _SYNC_BATCHES[batch.id] = batch
    asyncio.create_task(_run_sync_all_batch(batch.id), name=f"sync-all-{batch.id}")
    return batch


async def _run_sync_all_batch(batch_id: str) -> None:
    batch = _SYNC_BATCHES[batch_id]
    try:
        async with session_factory() as session:
            rows = (
                await session.execute(
                    select(PlaylistSubscription).where(PlaylistSubscription.enabled == True)
                )
            ).scalars().all()
            effective: list[PlaylistSubscription] = []
            for sub in rows:
                ok, reason = await can_sync_subscription(session, sub)
                if ok:
                    effective.append(sub)
                else:
                    batch.reports.append(
                        _serialize_report(
                            SyncReport(subscription_id=sub.id, name=sub.name, error=reason)
                        )
                    )

        batch.total = len(effective)
        for sub in effective:
            async with session_factory() as session:
                current = await session.get(PlaylistSubscription, sub.id)
                if not current:
                    report = SyncReport(subscription_id=sub.id, name=sub.name, error="订阅不存在")
                else:
                    report = await sync_subscription(session, current, batch_id=batch.id)
                batch.reports.append(_serialize_report(report))
                batch.enqueued += report.enqueued
                batch.already_queued += report.already_queued
                batch.completed += 1
        batch.status = "completed"
    except Exception as e:
        batch.status = "failed"
        batch.error = str(e)
        logger.exception(f"sync all batch {batch_id} failed: {e}")
    finally:
        batch.finished_at = utcnow()


async def _make_platform(session: AsyncSession, pid: PlatformID) -> Platform:
    acc = await session.scalar(select(Account).where(Account.platform == pid.value))
    cookie = acc.cookie_json if acc and acc.is_valid else {}
    if pid is PlatformID.NETEASE:
        return NeteaseClient(cookie=cookie)
    if pid is PlatformID.QQ:
        return QQClient(cookie=cookie)
    raise RuntimeError(f"unknown platform: {pid}")


async def _fetch_remote(
    cli: Platform, target_type: str, target_id: str
) -> tuple[str, Optional[str], Optional[str], list[SongInfo]]:
    """统一拉远端：返回 (name, cover_url, description, songs)"""
    if target_type == "playlist":
        info, songs = await cli.get_playlist(target_id)
        return info.name, info.cover_url, info.description, songs
    if target_type == "album":
        info, songs = await cli.get_album(target_id)
        return info.name, info.cover_url, info.description, songs
    if target_type == "daily":
        # 每日推荐：当作虚拟歌单同步，不替换现有 name/cover/desc
        songs = await cli.recommend_songs(limit=100)
        return "", None, None, songs
    if target_type == "artist":
        # 歌手：拉热门 + 全部专辑里所有歌曲，按 mid 去重组成大歌单
        ainfo, hot_songs, albums = await cli.get_artist(target_id)
        seen: set[str] = set()
        all_songs: list[SongInfo] = []
        for s in hot_songs:
            if s.platform_song_id in seen:
                continue
            seen.add(s.platform_song_id)
            all_songs.append(s)
        for al in albums:
            try:
                _, al_songs = await cli.get_album(al.platform_album_id)
            except Exception as e:
                logger.warning(f"artist sync: get_album {al.platform_album_id} failed: {e}")
                continue
            for s in al_songs:
                if s.platform_song_id in seen:
                    continue
                seen.add(s.platform_song_id)
                all_songs.append(s)
        return (
            f"{ainfo.name} · 歌手",
            ainfo.cover_url,
            ainfo.description,
            all_songs,
        )
    raise ValueError(f"unknown target_type: {target_type}")


async def _is_already_local(session: AsyncSession, song: SongInfo) -> bool:
    """本地是否已经有这首歌（去重命中）。"""
    existing = await dedupe.find_existing(session, song)
    if existing and existing.file_path and Path(existing.file_path).exists():
        src = await session.scalar(
            select(SongSource).where(
                SongSource.platform == song.platform.value,
                SongSource.platform_song_id == song.platform_song_id,
            )
        )
        if src is None:
            session.add(
                SongSource(
                    song_id=existing.id,
                    platform=song.platform.value,
                    platform_song_id=song.platform_song_id,
                    max_quality=None,
                )
            )
        return True
    src = await session.scalar(
        select(SongSource).where(
            SongSource.platform == song.platform.value,
            SongSource.platform_song_id == song.platform_song_id,
        )
    )
    if src is None:
        return False
    row = await session.get(Song, src.song_id)
    return bool(row and row.file_path and Path(row.file_path).exists())


_META_TYPES = {"meta_my_created", "meta_my_collected", "meta_toplists"}


async def _sync_meta_hot_category(
    session: AsyncSession, sub: PlaylistSubscription
) -> SyncReport:
    """
    「分类热门歌单」meta：每次同步按 ``meta_config.categories``（或旧版单条 ``category``）
    分别拉取 ``hot_playlists``，合并去重后在候选池中按 ``pick_mode`` 选出 ``top_n``；
    自动创建/维护 ``auto_added`` 子订阅。``drop_policy=keep_history`` 时只新增不删除，
    ``drop_policy=strict`` 时才严格移除掉出 TopN 的自动子订阅。
    """
    report = SyncReport(subscription_id=sub.id, name=sub.name)
    raw_cfg: dict[str, Any] = sub.meta_config or {}
    raw_cats = raw_cfg.get("categories")
    categories: list[str] = []
    if isinstance(raw_cats, list):
        for c in raw_cats:
            s = str(c or "").strip()
            if s and s not in categories:
                categories.append(s)
    if not categories:
        legacy = str(raw_cfg.get("category") or "").strip()
        if legacy:
            categories = [legacy]
    top_n = max(1, min(30, int(raw_cfg.get("top_n") or 5)))
    pool_size = max(top_n, min(100, int(raw_cfg.get("pool_size") or 50)))
    pick_mode = str(raw_cfg.get("pick_mode") or "top_play_count").strip()
    if pick_mode not in ("top_play_count", "random"):
        pick_mode = "top_play_count"
    drop_policy = str(raw_cfg.get("drop_policy") or "keep_history").strip()
    if drop_policy not in ("strict", "keep_history"):
        drop_policy = "keep_history"

    if not categories:
        report.error = "缺少分类：请在 meta_config 中设置 categories（或旧版 category）"
        sub.last_error = report.error
        sub.last_sync_at = utcnow()
        await session.commit()
        return report

    pid = PlatformID(sub.platform)
    cli = await _make_platform(session, pid)
    # ★ HTTP 拉热门歌单期间不持写锁
    await session.commit()

    merged: dict[str, PlaylistInfo] = {}
    remote_total = 0
    failed_categories: list[str] = []
    for cat in categories:
        try:
            page = await cli.hot_playlists(
                category=cat, page=1, page_size=pool_size
            )
        except Exception as e:
            logger.warning(f"meta_hot_category fetch cat={cat!r} failed: {e}")
            failed_categories.append(cat)
            continue
        remote_total += len(page.items)
        for p in page.items:
            prev = merged.get(p.platform_playlist_id)
            if prev is None or int(p.play_count or 0) > int(prev.play_count or 0):
                merged[p.platform_playlist_id] = p

    if not merged:
        report.error = "拉取热门歌单失败：所有分类均无数据"
        sub.last_error = report.error
        sub.last_sync_at = utcnow()
        await session.commit()
        return report

    pool = list(merged.values())
    if pick_mode == "random":
        random.shuffle(pool)
        targets = pool[:top_n]
    else:
        pool.sort(key=lambda p: p.play_count, reverse=True)
        targets = pool[:top_n]
    report.remote_count = remote_total

    new_ids = [t.platform_playlist_id for t in targets]
    new_set = set(new_ids)
    already_mirrored = set(sub.tracks_json or [])
    suppressed_ids = _suppressed_child_ids(sub)
    can_remove_old = drop_policy == "strict" and not failed_categories
    removed_ids = already_mirrored - new_set if can_remove_old else set()

    enqueued_children = 0
    for t in targets:
        if t.platform_playlist_id in suppressed_ids:
            continue
        existing_child = await session.scalar(
            select(PlaylistSubscription).where(
                PlaylistSubscription.platform == sub.platform,
                PlaylistSubscription.platform_playlist_id == t.platform_playlist_id,
            )
        )
        if existing_child is None:
            child = PlaylistSubscription(
                platform=sub.platform,
                target_type="playlist",
                platform_playlist_id=t.platform_playlist_id,
                name=t.name,
                description=t.description,
                creator=t.creator,
                cover_url=t.cover_url,
                auto_added=True,
                parent_subscription_id=sub.id,
                sync_interval_hours=sub.sync_interval_hours,
                enabled=True,
                generate_m3u=sub.generate_m3u,
            )
            session.add(child)
            try:
                await session.commit()
                await session.refresh(child)
                enqueued_children += 1
                from app.services import scheduler as _sched

                _sched.register_subscription(child)
            except Exception as e:
                await session.rollback()
                logger.warning(f"meta_hot_category create child failed: {e}")
                continue

    for rid in removed_ids:
        victim = await session.scalar(
            select(PlaylistSubscription).where(
                PlaylistSubscription.platform == sub.platform,
                PlaylistSubscription.platform_playlist_id == rid,
                PlaylistSubscription.parent_subscription_id == sub.id,
                PlaylistSubscription.auto_added.is_(True),
            )
        )
        if victim is None:
            continue
        vid = victim.id
        await TaskManager.get().cancel_waiting_for_subscription(vid)
        await session.delete(victim)
        await session.commit()
        from app.services import scheduler as _sched

        _sched.unregister_subscription(vid)

    preserved_ids = set() if can_remove_old else already_mirrored
    sub.tracks_json = list(new_set | preserved_ids | suppressed_ids)
    sub.last_sync_at = utcnow()
    sub.last_sync_track_count = len(targets)
    sub.last_sync_new_count = enqueued_children
    if failed_categories:
        sub.last_error = f"部分分类拉取失败，已保留旧子订阅：{'、'.join(failed_categories)}"
        report.error = sub.last_error
    else:
        sub.last_error = None
    await session.commit()

    report.new_count = enqueued_children
    report.enqueued = enqueued_children
    return report


async def _sync_meta(
    session: AsyncSession, sub: PlaylistSubscription
) -> SyncReport:
    """
    Meta 订阅同步：拉取上游集合（创建/收藏/排行榜），把新出现的子歌单
    bulk-subscribe 进来（auto_added=True）。

    sub.tracks_json 在 meta 模式下用作"已镜像子歌单 ID 列表"。
    被用户后续手动删除的子订阅，不会再被这里恢复（避免和用户作对）。
    """
    report = SyncReport(subscription_id=sub.id, name=sub.name)
    pid = PlatformID(sub.platform)
    cli = await _make_platform(session, pid)

    # 1) 拉远端集合
    try:
        if sub.target_type == "meta_toplists":
            # ★ HTTP 期间不持写锁
            await session.commit()
            targets = await cli.top_lists()
        else:
            acc = await session.scalar(
                select(Account).where(Account.platform == sub.platform)
            )
            if not acc or not acc.is_valid or not acc.user_id:
                report.error = "未登录该平台，无法拉取我的歌单"
                sub.last_error = report.error
                sub.last_sync_at = utcnow()
                await session.commit()
                return report
            user_id = acc.user_id
            # ★ HTTP 期间不持写锁
            await session.commit()
            created, collected = await cli.user_playlists(user_id)
            targets = (
                created if sub.target_type == "meta_my_created" else collected
            )
    except Exception as e:
        report.error = f"拉取远端失败：{e}"
        sub.last_error = report.error
        sub.last_sync_at = utcnow()
        await session.commit()
        return report

    report.remote_count = len(targets)
    already_mirrored = set(sub.tracks_json or [])
    suppressed_ids = _suppressed_child_ids(sub)
    new_targets = [
        t
        for t in targets
        if t.platform_playlist_id not in already_mirrored
        and t.platform_playlist_id not in suppressed_ids
    ]

    # 2) 把新出现的子歌单创建为普通订阅
    enqueued = 0  # 这里用作 "新增 child sub 数"
    for t in new_targets:
        existing_child = await session.scalar(
            select(PlaylistSubscription).where(
                PlaylistSubscription.platform == sub.platform,
                PlaylistSubscription.platform_playlist_id == t.platform_playlist_id,
            )
        )
        if existing_child is None:
            child = PlaylistSubscription(
                platform=sub.platform,
                target_type="playlist",
                platform_playlist_id=t.platform_playlist_id,
                name=t.name,
                description=t.description,
                creator=t.creator,
                cover_url=t.cover_url,
                auto_added=True,
                parent_subscription_id=sub.id,
                sync_interval_hours=sub.sync_interval_hours,
                enabled=True,
                generate_m3u=sub.generate_m3u,
            )
            session.add(child)
            try:
                await session.commit()
                await session.refresh(child)
                enqueued += 1
                from app.services import scheduler as _sched

                _sched.register_subscription(child)
            except Exception as e:
                await session.rollback()
                logger.warning(f"meta create child failed: {e}")
                continue

    # 3) 更新 meta 自身状态：tracks_json 记录当前镜像列表的全集
    sub.tracks_json = list(
        already_mirrored | suppressed_ids | {t.platform_playlist_id for t in targets}
    )
    sub.last_sync_at = utcnow()
    sub.last_sync_track_count = len(targets)
    sub.last_sync_new_count = enqueued
    sub.last_error = None
    await session.commit()

    report.new_count = enqueued
    report.enqueued = enqueued
    return report


def _song_key(s: SongInfo) -> str:
    """跨平台 diff/dedupe 用的 key：'<platform>:<song_id>'。"""
    return f"{s.platform.value}:{s.platform_song_id}"


def _normalize_old_track_keys(raw: list, primary_platform: str) -> set[str]:
    """旧记录里 tracks_json 是 ['id1','id2',...]（无前缀），新格式带前缀。
    把无前缀项当成 primary_platform 的 ID 处理，避免升级后误判全为新增。"""
    out: set[str] = set()
    for x in raw or []:
        x = str(x)
        if ":" in x:
            out.add(x)
        else:
            out.add(f"{primary_platform}:{x}")
    return out


def _suppressed_child_ids(sub: PlaylistSubscription) -> set[str]:
    """读取用户主动删除/隐藏的自动子订阅 ID。"""
    cfg = sub.meta_config or {}
    raw = cfg.get("suppressed_child_ids")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if str(x or "").strip()}


def _build_sync_item(
    run_id: Optional[int],
    sub_id: int,
    song: SongInfo,
    status: str,
    *,
    task_id: Optional[int] = None,
    error: Optional[str] = None,
) -> Optional[SyncRunItem]:
    """持久化单首歌在本次 Sync 中的处理结果。"""
    if run_id is None:
        return None
    return SyncRunItem(
        sync_run_id=run_id,
        subscription_id=sub_id,
        platform=song.platform.value,
        platform_song_id=song.platform_song_id,
        track_key=_song_key(song),
        title=song.name,
        artist=song.primary_artist,
        status=status,
        task_id=task_id,
        error=error,
    )


async def _fetch_cross_platform(
    primary_platform: PlatformID,
    primary_name: str,
    target_type: str,
    other_id: str | None = None,
) -> list[SongInfo]:
    """
    全平台聚合：在另一平台拉同名/同 ID 歌手或专辑的所有曲目。

    优先使用 `other_id`（用户在另一平台手动指定的 ID）。
    没有时回退到按名字搜索 + 名字精确匹配 + 最相似 fallback。
    target_type 仅支持 artist 和 album，其他返回空。
    """
    other_pid = (
        PlatformID.QQ if primary_platform is PlatformID.NETEASE else PlatformID.NETEASE
    )
    if other_pid is PlatformID.NETEASE:
        from app.platforms.netease import NeteaseClient

        other_cli: Platform = NeteaseClient(cookie={})
    else:
        from app.platforms.qq import QQClient

        other_cli = QQClient(cookie={})

    try:
        if target_type == "artist":
            artist_id = other_id
            if not artist_id:
                cands = await other_cli.search_artists(primary_name, limit=3)
                picked = next(
                    (c for c in cands if c.name.strip() == primary_name.strip()),
                    cands[0] if cands else None,
                )
                if not picked:
                    return []
                artist_id = picked.platform_artist_id
            _, hot_songs, albums = await other_cli.get_artist(artist_id)
            seen: set[str] = set()
            songs: list[SongInfo] = []
            for s in hot_songs:
                k = s.platform_song_id
                if k in seen:
                    continue
                seen.add(k)
                songs.append(s)
            for al in albums:
                try:
                    _, al_songs = await other_cli.get_album(al.platform_album_id)
                except Exception as e:
                    logger.warning(f"cross_platform: get_album failed: {e}")
                    continue
                for s in al_songs:
                    if s.platform_song_id in seen:
                        continue
                    seen.add(s.platform_song_id)
                    songs.append(s)
            return songs

        if target_type == "album":
            album_id = other_id
            if not album_id:
                cands = await other_cli.search_albums(primary_name, limit=3)
                picked = next(
                    (c for c in cands if c.name.strip() == primary_name.strip()),
                    cands[0] if cands else None,
                )
                if not picked:
                    return []
                album_id = picked.platform_album_id
            try:
                _, songs = await other_cli.get_album(album_id)
                return songs
            except Exception as e:
                logger.warning(f"cross_platform: get_album {album_id} failed: {e}")
                return []
    except Exception as e:
        logger.warning(f"cross_platform fetch failed: {e}")
    return []


async def sync_subscription(
    session: AsyncSession, sub: PlaylistSubscription, batch_id: Optional[str] = None
) -> SyncReport:
    report = SyncReport(subscription_id=sub.id, name=sub.name)
    ok, reason = await can_sync_subscription(session, sub)
    if not ok:
        report.error = reason
        return report

    lock = _sync_lock(sub.id)
    if lock.locked():
        report.error = "订阅正在同步中"
        return report
    async with lock:
        run = SyncRun(
            batch_id=batch_id,
            subscription_id=sub.id,
            subscription_name=sub.name,
            status="running",
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        try:
            report = await _sync_subscription_inner(session, sub, run.id)
        except Exception as e:
            current = await session.get(SyncRun, run.id)
            if current:
                current.status = "failed"
                current.error = str(e)
                current.finished_at = utcnow()
                await session.commit()
            raise

        current = await session.get(SyncRun, run.id)
        if current:
            current.status = "failed" if report.error else "completed"
            current.remote_count = report.remote_count
            current.new_count = report.new_count
            current.enqueued = report.enqueued
            current.already_queued = report.already_queued
            current.skipped_local = report.skipped_local
            current.task_ids_json = list(report.task_ids)
            current.error = report.error
            current.m3u_generated = report.m3u_generated
            current.m3u_error = report.m3u_error
            current.finished_at = utcnow()
            await session.commit()
        return report


async def _sync_subscription_inner(
    session: AsyncSession, sub: PlaylistSubscription, run_id: Optional[int] = None
) -> SyncReport:
    """
    执行一次订阅同步。

    **关键设计：尽早 commit 释放 SQLite 写锁**

        引擎层 ``BEGIN IMMEDIATE`` 让所有事务一开始就抢写锁，否则会撞
        DEFERRED 事务升级冲突立即失败。但副作用是「读事务」也变写事务，
        所以本函数必须在每个 IO 边界（HTTP 拉取 / 循环间隔）主动 commit
        一次，把写锁还回去，否则同步过程中用户的任何管理请求都要排队等
        到本次同步全部结束（持续几秒~几分钟）。

        各 commit 节点：
          1. ``_make_platform`` 之后：释放 SELECT account 拿到的写锁，再
             去拉远端；
          2. 跨平台聚合后：释放 ORM 修改的写锁（HTTP 期间不持锁）；
          3. 每首歌 ``_is_already_local`` SELECT 之后立即 commit，让循环
             里的写锁占用窗口缩到 ms 级；
          4. 最后一次：写最终状态 + 触发 m3u 生成。
    """
    report = SyncReport(subscription_id=sub.id, name=sub.name)
    if not sub.enabled:
        report.error = "订阅已禁用"
        return report

    if sub.target_type == "meta_hot_category":
        return await _sync_meta_hot_category(session, sub)

    if sub.target_type in _META_TYPES:
        return await _sync_meta(session, sub)

    pid = PlatformID(sub.platform)
    cli = await _make_platform(session, pid)
    # ★ 关键：拉远端前立即释放写锁，HTTP 期间不持锁
    await session.commit()

    try:
        name, cover, desc, songs = await _fetch_remote(
            cli, sub.target_type or "playlist", sub.platform_playlist_id
        )
    except Exception as e:
        report.error = f"拉取远端失败：{e}"
        sub.last_error = report.error
        sub.last_sync_at = utcnow()
        await session.commit()
        return report

    sub.name = name or sub.name
    sub.cover_url = cover or sub.cover_url
    sub.description = desc or sub.description

    # 全平台聚合：仅 artist / album 类型生效，其他类型忽略此开关
    if bool(sub.cross_platform) and sub.target_type in ("artist", "album"):
        # 用主平台返回的真名（去掉 " · 歌手" 后缀）去搜
        primary_name = (sub.name or "").replace(" · 歌手", "").strip()
        if primary_name or sub.cross_platform_id:
            extra_songs = await _fetch_cross_platform(
                pid,
                primary_name,
                sub.target_type,
                other_id=sub.cross_platform_id,
            )
            if extra_songs:
                logger.info(
                    f"cross-platform sync #{sub.id}: +{len(extra_songs)} from other platform"
                    f"{' (manual id=' + sub.cross_platform_id + ')' if sub.cross_platform_id else ' (auto match)'}"
                )
                songs = list(songs) + list(extra_songs)

    # 跨平台 diff：用 'platform:song_id' 作为 key
    report.remote_count = len(songs)
    old_keys = _normalize_old_track_keys(sub.tracks_json or [], sub.platform)
    cur_keys: list[str] = []
    cur_seen: set[str] = set()
    deduped_songs: list[SongInfo] = []
    for s in songs:
        k = _song_key(s)
        if k in cur_seen:
            continue
        cur_seen.add(k)
        cur_keys.append(k)
        deduped_songs.append(s)

    new_songs = [s for s in deduped_songs if _song_key(s) not in old_keys]
    report.new_count = len(new_songs)

    # ★ 进入循环前 commit：让远端拉取过程中累积的 ORM 修改（sub.name 等）
    # 入库，并释放写锁。
    await session.commit()

    final_key_set = {k for k in cur_keys if k in old_keys}
    to_process: list[tuple[SongInfo, bool]] = []
    for s in deduped_songs:
        key = _song_key(s)
        if key not in old_keys:
            to_process.append((s, False))
            continue
        if not await _is_already_local(session, s):
            await session.commit()
            to_process.append((s, True))

    enqueued = 0
    already_queued = 0
    skipped_local = 0
    enqueue_failed = 0
    sync_items: list[SyncRunItem] = []
    for s, known_missing in to_process:
        key = _song_key(s)
        already_local = False if known_missing else await _is_already_local(session, s)
        if not known_missing:
            # ★ 立即 commit：把这次 SELECT 触发的事务还回去，
            # 否则整段循环都持锁，enqueue_song 内部的 INSERT 拿不到锁。
            await session.commit()
        if already_local:
            skipped_local += 1
            final_key_set.add(key)
            item = _build_sync_item(run_id, sub.id, s, "skipped_local")
            if item:
                sync_items.append(item)
            continue
        try:
            # 入队时用每首歌自己的 platform（跨平台拉来的会用对应的客户端下载）
            enqueue_result = await TaskManager.get().enqueue_song_with_result(
                s.platform,
                s,
                priority=0,
                source_subscription_id=sub.id,
                sync_run_id=run_id,
                source_type="subscription_sync",
            )
            tid = enqueue_result.task_id
            report.task_ids.append(tid)
            if enqueue_result.created:
                enqueued += 1
                item_status = "enqueued"
            else:
                already_queued += 1
                item_status = "already_queued"
            final_key_set.add(key)
            item = _build_sync_item(run_id, sub.id, s, item_status, task_id=tid)
            if item:
                sync_items.append(item)
        except Exception as e:
            enqueue_failed += 1
            final_key_set.discard(key)
            item = _build_sync_item(run_id, sub.id, s, "enqueue_failed", error=str(e))
            if item:
                sync_items.append(item)
            logger.warning(f"enqueue {s.name} failed: {e}")

    report.enqueued = enqueued
    report.already_queued = already_queued
    report.skipped_local = skipped_local

    if sync_items:
        session.add_all(sync_items)
    sub.tracks_json = [k for k in cur_keys if k in final_key_set]
    sub.last_sync_at = utcnow()
    sub.last_sync_track_count = len(cur_keys)
    sub.last_sync_new_count = report.new_count
    report.error = f"{enqueue_failed} 首歌曲入队失败，将在下次同步重试" if enqueue_failed else None
    sub.last_error = report.error
    await session.commit()

    # 同步完顺手刷一遍 m3u（除非订阅关闭了 m3u 生成）
    if sub.generate_m3u is None or sub.generate_m3u:
        try:
            p = await generate_m3u_for_subscription(session, sub)
            if p:
                sub.m3u_file_path = str(p)
                report.m3u_generated = True
                await session.commit()
        except Exception as e:
            report.m3u_error = str(e)
            report.error = f"{report.error}；m3u 生成失败：{e}" if report.error else f"m3u 生成失败：{e}"
            sub.last_error = report.error
            await session.commit()
            logger.warning(f"m3u generate failed: {e}")

    return report
