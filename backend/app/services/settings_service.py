"""
全局设置读写服务（基于 Setting 表 key/value）。

启动时会调用 ensure_defaults() 写入默认值，避免首次使用为空。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.db.models import Setting

# ----- 默认设置 -----
DEFAULTS: dict[str, Any] = {
    # 下载
    "download.max_quality": "lossless",         # lossless | exhigh | standard
    "download.concurrency": 3,                  # 并发数
    "download.retry_times": 3,                  # 单首重试次数
    "download.retry_backoff_secs": [2, 5, 10],  # 重试间隔
    "queue.paused": False,                      # 队列暂停状态（重启后恢复）
    # 元数据
    "meta.embed_cover": True,
    "meta.embed_lyric": True,
    "meta.save_lrc_sidecar": True,              # 旁存 .lrc
    "meta.save_jpg_sidecar": False,             # 旁存 .jpg
    "meta.write_id3_tags": True,
    # 文件组织
    "organize.dir_layout": "artist-album-song",  # artist-song | artist-album-song
    "organize.filename_format": "name-artist",   # name | name-artist | name-artist-album
    # M3U
    "m3u.enabled": True,
    "m3u.path_mode": "relative",                 # relative | absolute | custom
    "m3u.relative_prefix": "../",
    # m3u8 文件名模板，可用变量：{platform}、{name}
    "m3u.filename_template": "[{platform}] {name}",
    # m3u8 内歌曲路径前缀。留空 = 写真实绝对路径；
    # 填写如 "/music" 时，会把每首歌路径里的「实际下载根目录」替换成这个值，
    # 方便把 m3u8 给 Plex/容器/NAS 直接消费。
    "m3u.path_root": "",
}


# ==================================================================
# 读写
# ==================================================================
async def get_all(session: AsyncSession) -> dict[str, Any]:
    """获取所有设置，未存的项用默认值补齐。"""
    rows = (await session.scalars(select(Setting))).all()
    result = dict(DEFAULTS)
    for r in rows:
        result[r.key] = r.value
    return result


async def get_value(session: AsyncSession, key: str) -> Any:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        return DEFAULTS.get(key)
    return row.value


async def set_value(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))


# ==================================================================
# 路径解析
# ==================================================================
def resolve_music_dir(cfg: dict[str, Any]) -> Path:  # noqa: ARG001 (cfg 保留兼容)
    """实际音乐根目录（环境变量 MUSIC_DIR）。歌曲会下载到这里。"""
    base = app_settings.music_dir
    base.mkdir(parents=True, exist_ok=True)
    return base


def resolve_m3u_dir(cfg: dict[str, Any]) -> Path:
    """m3u8 输出目录：<真实音乐目录>/_m3u。"""
    out = resolve_music_dir(cfg) / "_m3u"
    out.mkdir(parents=True, exist_ok=True)
    return out


def resolve_m3u_path_root(cfg: dict[str, Any]) -> str | None:
    """
    m3u8 里写歌曲路径时使用的根。

    返回非 None 时，m3u_service 会把每首歌的真实路径里的 `music_dir` 前缀替换为它。
    返回 None 表示直接写真实绝对路径。
    """
    raw = (cfg.get("m3u.path_root") or "").strip()
    if not raw:
        return None
    # 去掉末尾斜杠，方便后续拼接
    return raw.rstrip("/").rstrip("\\")


async def set_many(session: AsyncSession, kv: dict[str, Any]) -> None:
    """批量更新设置项。仅接受白名单内的 key。"""
    allowed = set(DEFAULTS.keys())
    for k, v in kv.items():
        if k not in allowed:
            continue
        await set_value(session, k, v)
    await session.commit()


# ==================================================================
# 初始化
# ==================================================================
async def ensure_defaults(session: AsyncSession) -> None:
    """启动时调用：补齐默认设置项。"""
    rows = (await session.scalars(select(Setting))).all()
    existing = {r.key for r in rows}
    for k, v in DEFAULTS.items():
        if k not in existing:
            session.add(Setting(key=k, value=v))
    await session.commit()
