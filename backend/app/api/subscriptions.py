"""
订阅路由。

GET    /api/subscriptions          列表
POST   /api/subscriptions          新增（自动从远端拉名字/封面）
PUT    /api/subscriptions/{id}     编辑（启用/禁用、同步间隔）
DELETE /api/subscriptions/{id}     删除
POST   /api/subscriptions/{id}/sync     立即同步
POST   /api/subscriptions/sync_all      全部同步
POST   /api/m3u/generate                 重新生成全部 m3u
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, PlaylistSubscription, SyncRun, SyncRunItem
from app.db.session import get_session, session_factory
from app.platforms.base import PlatformID
from app.platforms.netease import NeteaseClient
from app.platforms.qq import QQClient
from app.services import scheduler, sync_service
from app.services.m3u_service import generate_all_m3u, generate_m3u_for_subscription
from app.services.task_manager import TaskManager

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])
m3u_router = APIRouter(prefix="/api/m3u", tags=["m3u"])


_TT = Literal[
    "playlist",
    "album",
    "artist",
    "daily",
    "meta_my_created",
    "meta_my_collected",
    "meta_toplists",
]
_META_TYPES = {"meta_my_created", "meta_my_collected", "meta_toplists"}


def _is_sqlite_locked(exc: OperationalError) -> bool:
    return "database is locked" in str(exc).lower()


async def _run_subscription_write_with_retry(op, *, attempts: int = 5) -> None:
    """SQLite 写入冲突时重试整个短事务，避免删除订阅偶发 500。"""
    delay = 0.2
    for attempt in range(attempts):
        async with session_factory() as write_session:
            try:
                await op(write_session)
                await write_session.commit()
                return
            except OperationalError as e:
                await write_session.rollback()
                if not _is_sqlite_locked(e) or attempt >= attempts - 1:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 2.0)


def _mark_child_suppressed(parent: PlaylistSubscription, child: PlaylistSubscription) -> None:
    """记录用户主动删除的自动子订阅，避免后续 meta 同步再次恢复。"""
    cfg = dict(parent.meta_config or {})
    suppressed = {str(x) for x in cfg.get("suppressed_child_ids", []) if str(x or "").strip()}
    suppressed.add(str(child.platform_playlist_id))
    cfg["suppressed_child_ids"] = sorted(suppressed)
    parent.meta_config = cfg
    mirrored = {str(x) for x in (parent.tracks_json or []) if str(x or "").strip()}
    mirrored.add(str(child.platform_playlist_id))
    parent.tracks_json = sorted(mirrored)


class SubscribeRequest(BaseModel):
    platform: Literal["netease", "qq"]
    target_type: _TT = "playlist"
    id: str
    sync_interval_hours: int = 24
    enabled: bool = True
    generate_m3u: bool = True
    cross_platform: bool = False
    cross_platform_id: Optional[str] = None


class BulkSubscribeItem(BaseModel):
    platform: Literal["netease", "qq"]
    target_type: _TT = "playlist"
    id: str
    name: Optional[str] = None
    cover_url: Optional[str] = None
    creator: Optional[str] = None


class BulkSubscribeRequest(BaseModel):
    items: list[BulkSubscribeItem]
    sync_interval_hours: int = 24
    enabled: bool = True
    generate_m3u: bool = True


class QuickSubscribeRequest(BaseModel):
    """快速订阅：根据 kind 选择虚拟订阅类型。"""

    kind: Literal[
        "daily",
        "toplists_all",
        "follow_my_created",
        "follow_my_collected",
    ]
    platform: Literal["netease", "qq"]
    sync_interval_hours: int = 24
    enabled: bool = True
    generate_m3u: bool = True


class HotCategorySubscribeRequest(BaseModel):
    """
    动态热门歌单：按广场分类拉取 ``hot_playlists``，按 ``pick_mode``
    选出 ``top_n`` 个歌单，自动创建/维护 ``auto_added`` 子订阅
    （见 sync_service._sync_meta_hot_category）。
    """

    platform: Literal["netease", "qq"]
    categories: list[str] = Field(default_factory=list)
    category: str | None = None
    pick_mode: Literal["top_play_count", "random"] = "top_play_count"
    drop_policy: Literal["strict", "keep_history"] = "keep_history"
    top_n: int = 5
    pool_size: int = 50
    sync_interval_hours: int = 24
    enabled: bool = True
    generate_m3u: bool = True


class UpdateSubscriptionRequest(BaseModel):
    sync_interval_hours: Optional[int] = None
    enabled: Optional[bool] = None
    generate_m3u: Optional[bool] = None
    cross_platform: Optional[bool] = None
    cross_platform_id: Optional[str] = None


class DeleteSubscriptionRequest(BaseModel):
    child_action: Literal["delete", "promote"] = "delete"


_PLATFORM_ZH = {"netease": "网易云", "qq": "QQ 音乐"}
_HOT_CATEGORY_ACTION_LABELS = {"全部", "全部分类", "全选"}


def _daily_meta(platform: str) -> tuple[str, str]:
    """每日推荐订阅的虚拟名字 + 描述。"""
    return (f"{_PLATFORM_ZH.get(platform, platform)}每日推荐", "每日推荐 · 自动同步")


def _meta_label(platform: str, kind: str) -> tuple[str, str, str]:
    """meta 订阅的 (target_type, name, description)。"""
    pz = _PLATFORM_ZH.get(platform, platform)
    if kind == "follow_my_created":
        return (
            "meta_my_created",
            f"{pz} · 我创建的所有歌单",
            "自动跟随：我创建的所有歌单（含「我喜欢的」）",
        )
    if kind == "follow_my_collected":
        return (
            "meta_my_collected",
            f"{pz} · 我收藏的所有歌单",
            "自动跟随：我收藏的所有歌单",
        )
    if kind == "toplists_all":
        return (
            "meta_toplists",
            f"{pz} · 所有官方排行榜",
            "自动跟随：所有官方排行榜（飙升、新歌、热歌等）",
        )
    raise ValueError(f"unknown meta kind: {kind}")


def _hot_category_slot_id(
    platform: str,
    categories: list[str],
    pick_mode: str,
    top_n: int,
    pool_size: int,
    drop_policy: str,
) -> str:
    """与分类 + 选取参数绑定的稳定虚拟 ID（避免 Unicode 直接进唯一键）。"""
    norm = "\u0001".join(sorted({c.strip() for c in categories if c and c.strip()}))
    key_src = f"{platform}\0{pick_mode}\0{top_n}\0{pool_size}\0{drop_policy}\0{norm}"
    key = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:20]
    return f"meta_hot_cat_{key}"


def _serialize(sub: PlaylistSubscription) -> dict:
    return {
        "id": sub.id,
        "platform": sub.platform,
        "target_type": sub.target_type,
        "platform_playlist_id": sub.platform_playlist_id,
        "name": sub.name,
        "description": sub.description,
        "creator": sub.creator,
        "cover_url": sub.cover_url,
        "auto_added": sub.auto_added,
        "parent_subscription_id": sub.parent_subscription_id,
        "enabled": sub.enabled,
        "sync_interval_hours": sub.sync_interval_hours,
        # NULL 视为默认：generate_m3u=True、cross_platform=False
        "generate_m3u": True if sub.generate_m3u is None else bool(sub.generate_m3u),
        "cross_platform": False if sub.cross_platform is None else bool(sub.cross_platform),
        "cross_platform_id": sub.cross_platform_id,
        "meta_config": sub.meta_config,
        "last_sync_at": sub.last_sync_at.isoformat() if sub.last_sync_at else None,
        "last_sync_track_count": sub.last_sync_track_count,
        "last_sync_new_count": sub.last_sync_new_count,
        "last_error": sub.last_error,
        "m3u_file_path": sub.m3u_file_path,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


async def _make_platform(session: AsyncSession, pid: PlatformID):
    acc = await session.scalar(select(Account).where(Account.platform == pid.value))
    cookie = acc.cookie_json if acc and acc.is_valid else {}
    if pid is PlatformID.NETEASE:
        return NeteaseClient(cookie=cookie)
    if pid is PlatformID.QQ:
        return QQClient(cookie=cookie)
    raise HTTPException(status_code=400, detail=f"unknown platform: {pid}")


@router.get("")
async def list_subscriptions(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(PlaylistSubscription).order_by(PlaylistSubscription.created_at.desc())
        )
    ).scalars().all()
    return {"items": [_serialize(s) for s in rows]}


@router.post("")
async def add_subscription(
    body: SubscribeRequest, session: AsyncSession = Depends(get_session)
):
    # 重复检查（platform + target_type + platform_id）
    existing = await session.scalar(
        select(PlaylistSubscription).where(
            PlaylistSubscription.platform == body.platform,
            PlaylistSubscription.target_type == body.target_type,
            PlaylistSubscription.platform_playlist_id == body.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="此歌单/专辑已在订阅中")

    pid = PlatformID(body.platform)

    if body.target_type == "daily":
        # 每日推荐：不调远端 get_playlist，直接落库；同步时再拉 recommend_songs
        name, desc = _daily_meta(body.platform)
        sub = PlaylistSubscription(
            platform=body.platform,
            target_type="daily",
            platform_playlist_id="daily",
            name=name,
            description=desc,
            creator=_PLATFORM_ZH.get(body.platform),
            cover_url=None,
            sync_interval_hours=max(1, body.sync_interval_hours),
            enabled=body.enabled,
        )
    elif body.target_type in _META_TYPES:
        # meta_*：虚拟订阅，自动跟随平台某种集合
        if body.target_type == "meta_my_created":
            kind_label = "follow_my_created"
        elif body.target_type == "meta_my_collected":
            kind_label = "follow_my_collected"
        else:
            kind_label = "toplists_all"
        tt, name, desc = _meta_label(body.platform, kind_label)
        sub = PlaylistSubscription(
            platform=body.platform,
            target_type=tt,
            platform_playlist_id=tt,
            name=name,
            description=desc,
            creator=_PLATFORM_ZH.get(body.platform),
            cover_url=None,
            sync_interval_hours=max(1, body.sync_interval_hours),
            enabled=body.enabled,
        )
    else:
        cli = await _make_platform(session, pid)
        if body.target_type == "playlist":
            info, _ = await cli.get_playlist(body.id)
            sub = PlaylistSubscription(
                platform=body.platform,
                target_type="playlist",
                platform_playlist_id=info.platform_playlist_id,
                name=info.name,
                description=info.description,
                creator=info.creator,
                cover_url=info.cover_url,
                sync_interval_hours=max(1, body.sync_interval_hours),
                enabled=body.enabled,
            )
        elif body.target_type == "artist":
            ainfo, _, _ = await cli.get_artist(body.id)
            sub = PlaylistSubscription(
                platform=body.platform,
                target_type="artist",
                platform_playlist_id=ainfo.platform_artist_id,
                name=f"{ainfo.name} · 歌手",
                description=ainfo.description,
                creator=ainfo.name,
                cover_url=ainfo.cover_url,
                sync_interval_hours=max(1, body.sync_interval_hours),
                enabled=body.enabled,
            )
        else:
            info, _ = await cli.get_album(body.id)
            sub = PlaylistSubscription(
                platform=body.platform,
                target_type="album",
                platform_playlist_id=info.platform_album_id,
                name=info.name,
                description=info.description,
                creator=", ".join(info.artists) if info.artists else None,
                cover_url=info.cover_url,
                sync_interval_hours=max(1, body.sync_interval_hours),
                enabled=body.enabled,
            )

    # 通用：m3u 开关 + 全平台聚合
    sub.generate_m3u = body.generate_m3u
    sub.cross_platform = body.cross_platform
    sub.cross_platform_id = body.cross_platform_id

    session.add(sub)
    await session.commit()
    await session.refresh(sub)

    if sub.enabled:
        scheduler.register_subscription(sub)

    return _serialize(sub)


@router.post("/quick")
async def quick_subscribe(
    body: QuickSubscribeRequest, session: AsyncSession = Depends(get_session)
):
    """
    快速订阅入口。kind 决定虚拟订阅类型：
        daily              - 每日推荐
        toplists_all       - 所有官方排行榜（meta）
        follow_my_created  - 我创建的所有歌单（meta，含我喜欢的）
        follow_my_collected- 我收藏的所有歌单（meta）

    meta 类型每次同步会自动 bulk-subscribe 新出现的子歌单。
    """
    if body.kind == "daily":
        return await add_subscription(  # type: ignore[arg-type]
            SubscribeRequest(
                platform=body.platform,
                target_type="daily",
                id="daily",
                sync_interval_hours=body.sync_interval_hours,
                enabled=body.enabled,
                generate_m3u=body.generate_m3u,
            ),
            session,
        )
    # meta_*：检查是否已存在
    tt, name, desc = _meta_label(body.platform, body.kind)
    existing = await session.scalar(
        select(PlaylistSubscription).where(
            PlaylistSubscription.platform == body.platform,
            PlaylistSubscription.platform_playlist_id == tt,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"已存在：{name}")
    sub = PlaylistSubscription(
        platform=body.platform,
        target_type=tt,
        platform_playlist_id=tt,
        name=name,
        description=desc,
        creator=_PLATFORM_ZH.get(body.platform),
        cover_url=None,
        sync_interval_hours=max(1, body.sync_interval_hours),
        enabled=body.enabled,
        generate_m3u=body.generate_m3u,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    if sub.enabled:
        scheduler.register_subscription(sub)
    return _serialize(sub)


@router.post("/hot-category")
async def add_hot_category_subscription(
    body: HotCategorySubscribeRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    创建「分类热门 TopN」meta 订阅：定时维护最多 ``top_n`` 个子歌单订阅。

    网易云为广场分类名；QQ 为歌单广场 ``get_hot_category`` 分类名（``get_playlist_by_category``）。
    前端会把多选拆成多个请求；如果调用方传入多个分类，则作为一个父订阅的分类集合保存。
    ``pick_mode`` 为 ``top_play_count`` 时按播放量取前 N，为 ``random`` 时在池内随机 N。
    """
    cats: list[str] = []
    for c in body.categories:
        s = (c or "").strip()
        if s and s not in _HOT_CATEGORY_ACTION_LABELS and s not in cats:
            cats.append(s)
    if (
        body.category
        and (s := body.category.strip())
        and s not in _HOT_CATEGORY_ACTION_LABELS
        and s not in cats
    ):
        cats.append(s)
    if not cats:
        raise HTTPException(status_code=400, detail="请至少选择一个广场分类")
    top_n = max(1, min(30, int(body.top_n)))
    pool = max(top_n, min(100, int(body.pool_size)))
    pick_mode = body.pick_mode if body.pick_mode in ("top_play_count", "random") else "top_play_count"
    drop_policy = body.drop_policy if body.drop_policy in ("strict", "keep_history") else "keep_history"
    slot = _hot_category_slot_id(body.platform, cats, pick_mode, top_n, pool, drop_policy)
    existing = await session.scalar(
        select(PlaylistSubscription).where(
            PlaylistSubscription.platform == body.platform,
            PlaylistSubscription.platform_playlist_id == slot,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"已存在相同条件的热门订阅：{existing.name}",
        )

    pz = _PLATFORM_ZH.get(body.platform, body.platform)
    cat_label = "、".join(cats[:4]) + ("…" if len(cats) > 4 else "")
    mode_zh = "按播放量" if pick_mode == "top_play_count" else "随机"
    drop_zh = "保留历史" if drop_policy == "keep_history" else "严格 TopN"
    name = f"{pz} · 热门动态（{cat_label}）· {mode_zh} Top{top_n}"
    desc = (
        f"每 {max(1, body.sync_interval_hours)}h：从所选分类拉取热门歌单，"
        f"以「{mode_zh}」方式取 {top_n} 个并自动维护子订阅；掉榜处理：{drop_zh}"
    )
    sub = PlaylistSubscription(
        platform=body.platform,
        target_type="meta_hot_category",
        platform_playlist_id=slot,
        name=name,
        description=desc,
        creator=pz,
        cover_url=None,
        sync_interval_hours=max(1, body.sync_interval_hours),
        enabled=body.enabled,
        generate_m3u=body.generate_m3u,
        meta_config={
            "categories": cats,
            "pick_mode": pick_mode,
            "drop_policy": drop_policy,
            "top_n": top_n,
            "pool_size": pool,
        },
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    if sub.enabled:
        scheduler.register_subscription(sub)
    return _serialize(sub)


@router.post("/bulk")
async def bulk_subscribe(
    body: BulkSubscribeRequest, session: AsyncSession = Depends(get_session)
):
    """
    批量订阅。已订阅的项静默跳过，元数据来自请求体（避免对每个 id 都调远端）。

    返回 {created: [...], skipped: [...]}
    """
    created: list[dict] = []
    skipped: list[dict] = []

    for it in body.items:
        existing = await session.scalar(
            select(PlaylistSubscription).where(
                PlaylistSubscription.platform == it.platform,
                PlaylistSubscription.platform_playlist_id == it.id,
            )
        )
        if existing:
            skipped.append(
                {"platform": it.platform, "id": it.id, "name": existing.name}
            )
            continue

        if it.target_type == "daily":
            name, desc = _daily_meta(it.platform)
            sub = PlaylistSubscription(
                platform=it.platform,
                target_type="daily",
                platform_playlist_id="daily",
                name=it.name or name,
                description=desc,
                creator=_PLATFORM_ZH.get(it.platform),
                cover_url=it.cover_url,
                sync_interval_hours=max(1, body.sync_interval_hours),
                enabled=body.enabled,
                generate_m3u=body.generate_m3u,
            )
        else:
            sub = PlaylistSubscription(
                platform=it.platform,
                target_type=it.target_type,
                platform_playlist_id=it.id,
                name=it.name or it.id,
                description=None,
                creator=it.creator,
                cover_url=it.cover_url,
                sync_interval_hours=max(1, body.sync_interval_hours),
                enabled=body.enabled,
                generate_m3u=body.generate_m3u,
            )
        session.add(sub)
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            skipped.append(
                {"platform": it.platform, "id": it.id, "error": str(e)}
            )
            continue
        await session.refresh(sub)
        if sub.enabled:
            scheduler.register_subscription(sub)
        created.append(_serialize(sub))

    return {"created": created, "skipped": skipped}


@router.put("/{sub_id}")
async def update_subscription(
    sub_id: int,
    body: UpdateSubscriptionRequest,
    session: AsyncSession = Depends(get_session),
):
    sub = await session.get(PlaylistSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404)
    child_subs = (
        await session.scalars(
            select(PlaylistSubscription).where(
                PlaylistSubscription.parent_subscription_id == sub_id
            )
        )
    ).all()
    parent_enabled = True
    if sub.parent_subscription_id:
        parent = await session.get(PlaylistSubscription, sub.parent_subscription_id)
        parent_enabled = bool(parent and parent.enabled)
    if body.sync_interval_hours is not None:
        sub.sync_interval_hours = max(1, body.sync_interval_hours)
    if body.enabled is not None:
        sub.enabled = body.enabled
    if body.generate_m3u is not None:
        sub.generate_m3u = body.generate_m3u
    if body.cross_platform is not None:
        sub.cross_platform = body.cross_platform
    if body.cross_platform_id is not None:
        # 空字符串视为清除
        sub.cross_platform_id = body.cross_platform_id or None
    if child_subs and sub.target_type in _META_TYPES | {"meta_hot_category"}:
        for child in child_subs:
            if not child.auto_added:
                continue
            if body.sync_interval_hours is not None:
                child.sync_interval_hours = sub.sync_interval_hours
            if body.generate_m3u is not None:
                child.generate_m3u = sub.generate_m3u
    await session.commit()
    await session.refresh(sub)

    if sub.enabled and parent_enabled:
        scheduler.register_subscription(sub)
    else:
        scheduler.unregister_subscription(sub.id)

    for child in child_subs:
        if sub.enabled and child.enabled:
            scheduler.register_subscription(child)
        else:
            scheduler.unregister_subscription(child.id)

    return _serialize(sub)


@router.delete("/{sub_id}")
async def delete_subscription(
    sub_id: int,
    child_action: Literal["delete", "promote"] = "delete",
    session: AsyncSession = Depends(get_session),
):
    sub = await session.get(PlaylistSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404)
    suppress_parent_id = sub.parent_subscription_id if sub.auto_added else None
    children = (
        await session.scalars(
            select(PlaylistSubscription).where(
                PlaylistSubscription.parent_subscription_id == sub_id,
                PlaylistSubscription.auto_added == True,
            )
        )
    ).all()
    child_ids = [c.id for c in children]
    enabled_child_ids = [c.id for c in children if c.enabled]
    promoted_children: list[int] = []
    await session.commit()

    if suppress_parent_id:
        async def _suppress_child(write_session: AsyncSession) -> None:
            parent = await write_session.get(PlaylistSubscription, suppress_parent_id)
            child = await write_session.get(PlaylistSubscription, sub_id)
            if parent and child and parent.target_type in _META_TYPES | {"meta_hot_category"}:
                _mark_child_suppressed(parent, child)

        await _run_subscription_write_with_retry(_suppress_child)

    if child_action == "promote":
        promoted_children = child_ids

        async def _promote_children(write_session: AsyncSession) -> None:
            rows = (
                await write_session.scalars(
                    select(PlaylistSubscription).where(PlaylistSubscription.id.in_(child_ids))
                )
            ).all()
            for child in rows:
                child.parent_subscription_id = None
                child.auto_added = False

        await _run_subscription_write_with_retry(_promote_children)
    else:
        for child_id in child_ids:
            await TaskManager.get().cancel_waiting_for_subscription(child_id)

        async def _delete_children(write_session: AsyncSession) -> None:
            await write_session.execute(
                delete(PlaylistSubscription).where(PlaylistSubscription.id.in_(child_ids))
            )

        if child_ids:
            await _run_subscription_write_with_retry(_delete_children)

    await TaskManager.get().cancel_waiting_for_subscription(sub_id)

    async def _delete_parent(write_session: AsyncSession) -> None:
        row = await write_session.get(PlaylistSubscription, sub_id)
        if row:
            await write_session.delete(row)

    await _run_subscription_write_with_retry(_delete_parent)

    scheduler.unregister_subscription(sub_id)
    if child_action == "promote":
        async with session_factory() as read_session:
            promoted = (
                await read_session.scalars(
                    select(PlaylistSubscription).where(PlaylistSubscription.id.in_(enabled_child_ids))
                )
            ).all()
            for child in promoted:
                scheduler.register_subscription(child)
    else:
        for child_id in child_ids:
            scheduler.unregister_subscription(child_id)

    return {
        "deleted": sub_id,
        "deleted_children": [] if child_action == "promote" else child_ids,
        "promoted_children": promoted_children,
    }


@router.post("/{sub_id}/sync")
async def sync_now(sub_id: int, session: AsyncSession = Depends(get_session)):
    sub = await session.get(PlaylistSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404)
    report = await sync_service.sync_subscription(session, sub)
    return sync_service._serialize_report(report)


@router.post("/sync_all")
async def sync_all():
    batch = sync_service.start_sync_all_batch()
    return sync_service.serialize_batch(batch)


@router.get("/sync_all/{batch_id}")
async def get_sync_all_batch(batch_id: str):
    batch = sync_service.get_sync_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404)
    return sync_service.serialize_batch(batch)


@router.get("/sync_runs")
async def list_sync_runs(limit: int = 30, session: AsyncSession = Depends(get_session)):
    rows = (
        await session.scalars(
            select(SyncRun).order_by(SyncRun.started_at.desc()).limit(max(1, min(200, limit)))
        )
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "batch_id": row.batch_id,
                "subscription_id": row.subscription_id,
                "subscription_name": row.subscription_name,
                "status": row.status,
                "remote_count": row.remote_count,
                "new_count": row.new_count,
                "enqueued": row.enqueued,
                "already_queued": row.already_queued or 0,
                "skipped_local": row.skipped_local,
                "task_ids": row.task_ids_json or [],
                "error": row.error,
                "m3u_generated": row.m3u_generated,
                "m3u_error": row.m3u_error,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            }
            for row in rows
        ]
    }


@router.get("/sync_runs/{run_id}/items")
async def list_sync_run_items(
    run_id: int,
    limit: int = 500,
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.scalars(
            select(SyncRunItem)
            .where(SyncRunItem.sync_run_id == run_id)
            .order_by(SyncRunItem.id)
            .limit(max(1, min(2000, limit)))
        )
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "sync_run_id": row.sync_run_id,
                "subscription_id": row.subscription_id,
                "platform": row.platform,
                "platform_song_id": row.platform_song_id,
                "track_key": row.track_key,
                "title": row.title,
                "artist": row.artist,
                "status": row.status,
                "task_id": row.task_id,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@m3u_router.post("/generate")
async def m3u_generate_all(session: AsyncSession = Depends(get_session)):
    count = await generate_all_m3u(session)
    return {"generated": count}


@m3u_router.post("/generate/{sub_id}")
async def m3u_generate_one(sub_id: int, session: AsyncSession = Depends(get_session)):
    sub = await session.get(PlaylistSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404)
    p = await generate_m3u_for_subscription(session, sub)
    if p:
        sub.m3u_file_path = str(p)
        await session.commit()
    return {"file_path": str(p) if p else None}
