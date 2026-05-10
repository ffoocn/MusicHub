"""
QQ 音乐「歌单广场」公开接口（``musicu.fcg`` + 网页 SSR 数据），与 qqmusic_api 中
仅暴露的 ``PlaylistSquare.GetRecommendFeed`` 互补：完整分类目录 + 按分类拉歌单。

分类来源优先级：
1. ``https://y.qq.com/n/ryqq_v2/category`` 网页 SSR 注入的 ``__INITIAL_DATA__``
   （含 7~8 个分组、上百个分类，与官网 ``分类歌单`` 页一致）。
2. 失败时回退 ``music.web_category_svr.get_hot_category``（仅热门十几项）。

按分类拉歌单：``playlist.PlayListPlazaServer.get_playlist_by_category``。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from app.platforms.base import PaginatedPlaylists, PlaylistInfo
from app.platforms.qq.mappers import plaza_v_playlist_to_playlist
from app.utils.logger import logger

_MUSICU_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
_V2_CATEGORY_URL = "https://y.qq.com/n/ryqq_v2/category"

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# title_id == 0 表示走推荐广场（即 hot_playlists 的「全部」分支）
_PLAZA_ID_ALL = 0

# 内存缓存：分类列表 + 名称→title_id 映射；进程内多个 QQClient 共享。
_plaza_cache: tuple[float, list[str], dict[str, int]] | None = None
_PLAZA_TTL_SEC = 600.0

_INITIAL_DATA_RE = re.compile(
    r"window\.__INITIAL_DATA__\s*=\s*(\{.*?\})\s*</script>",
    re.DOTALL,
)


async def _musicu_json(body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Referer": "https://y.qq.com/",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
        resp = await cli.post(_MUSICU_URL, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()


async def _fetch_v2_initial_data(*, timeout: float) -> dict[str, Any] | None:
    """从 v2 分类页 HTML 抓 ``__INITIAL_DATA__`` JSON。失败返回 None。"""
    headers = {"User-Agent": _DEFAULT_UA, "Referer": "https://y.qq.com/"}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
            resp = await cli.get(_V2_CATEGORY_URL, headers=headers)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"[qq] plaza fetch v2 category html failed: {e}")
        return None

    m = _INITIAL_DATA_RE.search(html)
    if not m:
        logger.warning("[qq] plaza __INITIAL_DATA__ not found in v2 html")
        return None
    raw = m.group(1)
    try:
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[qq] plaza parse __INITIAL_DATA__ failed: {e}")
        return None


def _build_full_catalog_from_v2(initial: dict[str, Any]) -> tuple[list[str], dict[str, int]]:
    """从 v2 SSR `categories` 数组构造下拉名 + 名称→title_id 映射。"""
    cats = initial.get("categories") or []
    id_by_name: dict[str, int] = {"全部": _PLAZA_ID_ALL}
    names: list[str] = ["全部"]
    seen_pairs: set[tuple[int, int]] = set()

    for grp in cats:
        if not isinstance(grp, dict):
            continue
        group_name = str(grp.get("categoryGroupName") or "").strip()
        group_id = int(grp.get("groupId") or 0)
        for it in grp.get("items") or []:
            if not isinstance(it, dict):
                continue
            cat_name = str(it.get("categoryName") or "").strip()
            cat_id = int(it.get("categoryId") or 0)
            # source=0：标准分类，可走 ``get_playlist_by_category``；
            # source!=0（如 AI 歌单、Chill Vibes）：广场虚拟集合，无法按分类列表，跳过。
            source = int(it.get("source") or 0)
            if source != 0:
                continue
            if not cat_name or not cat_id:
                continue
            if (group_id, cat_id) in seen_pairs:
                continue
            seen_pairs.add((group_id, cat_id))
            display = f"{group_name} · {cat_name}" if group_name else cat_name
            if display not in id_by_name:
                id_by_name[display] = cat_id
                names.append(display)
            # 同时为纯分类名注册 alias（向后兼容存量订阅，仅当不冲突时记录）
            id_by_name.setdefault(cat_name, cat_id)
    return names, id_by_name


async def _build_full_catalog_from_hot(*, timeout: float) -> tuple[list[str], dict[str, int]] | None:
    """回退方案：``get_hot_category`` 仅含「热门推荐」一组（约 16 项）。"""
    body = {
        "comm": {"ct": 24, "cv": 0},
        "category": {
            "module": "music.web_category_svr",
            "method": "get_hot_category",
            "param": {"qq": ""},
        },
    }
    try:
        root = await _musicu_json(body, timeout=timeout)
    except Exception as e:
        logger.warning(f"[qq] plaza get_hot_category failed: {e}")
        return None
    groups = (((root.get("category") or {}).get("data") or {}).get("category")) or []
    id_by_name: dict[str, int] = {"全部": _PLAZA_ID_ALL}
    names: list[str] = ["全部"]
    for grp in groups:
        if not isinstance(grp, dict):
            continue
        for it in grp.get("items") or []:
            if not isinstance(it, dict):
                continue
            raw_name = str(it.get("item_name") or "").strip()
            if not raw_name or raw_name in ("全部分类",):
                continue
            tid = int(it.get("item_id") or 0)
            if not tid:
                continue
            if raw_name not in id_by_name:
                id_by_name[raw_name] = tid
                names.append(raw_name)
    return names, id_by_name


async def load_qq_plaza_category_names_and_ids(*, timeout: float) -> tuple[list[str], dict[str, int]]:
    """
    返回 (展示名列表, 名称→title_id)。优先 v2 全量目录，回退热门推荐。

    展示名形如 ``主题 · KTV金曲``；同名 alias（纯 ``KTV金曲``）也写入映射，
    以便兼容历史 ``meta_config.categories`` 中的纯名条目。
    """
    global _plaza_cache
    now = time.monotonic()
    if _plaza_cache is not None and now - _plaza_cache[0] < _PLAZA_TTL_SEC:
        return _plaza_cache[1], _plaza_cache[2]

    initial = await _fetch_v2_initial_data(timeout=timeout)
    if initial:
        names, mapping = _build_full_catalog_from_v2(initial)
        if len(names) >= 2:
            _plaza_cache = (now, names, mapping)
            return names, mapping

    fallback = await _build_full_catalog_from_hot(timeout=timeout)
    if fallback is not None:
        names, mapping = fallback
        _plaza_cache = (now, names, mapping)
        return names, mapping

    return ["全部"], {"全部": _PLAZA_ID_ALL}


def resolve_plaza_title_id(category: str, id_by_name: dict[str, int]) -> int | None:
    """返回广场 title_id；``None`` 表示未知（可降级搜索）。"""
    key = (category or "").strip()
    if key in ("", "全部"):
        return _PLAZA_ID_ALL
    return id_by_name.get(key)


async def fetch_qq_plaza_playlists_by_title_id(
    *,
    title_id: int,
    page: int,
    page_size: int,
    timeout: float,
) -> PaginatedPlaylists:
    """按广场分类 ``title_id`` 分页拉取歌单列表。"""
    page = max(1, page)
    size = max(1, min(100, page_size))
    body = {
        "comm": {"ct": 24, "cv": 0},
        "playlist": {
            "module": "playlist.PlayListPlazaServer",
            "method": "get_playlist_by_category",
            "param": {
                "id": title_id,
                "titleid": title_id,
                "curPage": page,
                "size": size,
                "order": 5,
            },
        },
    }
    try:
        root = await _musicu_json(body, timeout=timeout)
    except Exception as e:
        logger.warning(f"[qq] plaza get_playlist_by_category id={title_id} failed: {e}")
        return PaginatedPlaylists(items=[], page=page, page_size=size, has_more=False)

    pl = (root.get("playlist") or {}).get("data") or {}
    raw_list = list(pl.get("v_playlist") or [])
    total = int(pl.get("total") or 0)
    items: list[PlaylistInfo] = []
    for raw in raw_list:
        if isinstance(raw, dict):
            items.append(plaza_v_playlist_to_playlist(raw))

    if total > 0:
        has_more = total > page * size
    else:
        has_more = len(raw_list) >= size
    return PaginatedPlaylists(
        items=items,
        page=page,
        page_size=size,
        has_more=has_more,
    )
