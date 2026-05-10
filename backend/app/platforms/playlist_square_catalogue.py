"""
网易云公开的「歌单广场」分类目录（``GET /api/playlist/catalogue``）。

QQ 音乐没有等价的官方分类枚举接口；动态热门订阅 UI 与两平台 ``hot_playlists`` 的
``category`` 选词对齐为同一套中文广场分类名。QQ 侧仍通过歌单搜索拉取结果。
"""

from __future__ import annotations

import httpx

from app.utils.logger import logger

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


async def fetch_playlist_square_category_names(*, timeout: float = 15.0) -> list[str]:
    """返回广场分类名列表，首项为「全部」，与网易云 ``hot_playlists(cat=...)`` 一致。"""
    url = "https://music.163.com/api/playlist/catalogue"
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Referer": "https://music.163.com/",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
            resp = await cli.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"playlist_square_catalogue fetch failed: {e}")
        return ["全部"]
    if data.get("code") != 200:
        return ["全部"]
    seen: set[str] = set()
    out: list[str] = []
    for first in ("全部",):
        if first not in seen:
            seen.add(first)
            out.append(first)
    for it in data.get("sub") or []:
        name = str((it or {}).get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out
