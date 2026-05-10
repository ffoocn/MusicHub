"""
名称标准化工具。

歌名 / 歌手 / 专辑名标准化是跨平台去重的核心：
    - 全角转半角
    - 简繁转换（保留简体）
    - 去除空白、控制字符
    - 去除常见装饰括号内容（如 "(Live)" "(Remastered)"）
    - 大小写统一为小写

文件名清洗（清除非法字符）单独由 organize.py 处理。
"""

from __future__ import annotations

import re
import unicodedata

# 常见装饰性后缀（用于去重时弱化匹配）
_DECOR_PATTERNS = [
    r"\((live|remastered|remix|acoustic|demo|inst(?:rumental)?|cover|piano|extended|short|radio[\s\-]*edit|original|version|feat\.?[^)]*)\)",
    r"\[(live|remastered|remix|acoustic|demo|inst(?:rumental)?|cover|piano|extended|short|radio[\s\-]*edit|original|version|feat\.?[^]]*)\]",
    r"（(live|remastered|remix|acoustic|demo|inst(?:rumental)?|cover|piano|扩展版|完整版|纯音乐|原曲|翻唱|现场)）",
]

# 多歌手分隔符（用于歌手名规整：取第一位作为主歌手时统一处理）
_ARTIST_SEP_RE = re.compile(r"\s*[/&,;|×x]\s*|\s+(?:and|与|和)\s+", flags=re.IGNORECASE)


def _to_halfwidth(text: str) -> str:
    """全角字符转半角（Unicode NFKC 规范化）。"""
    return unicodedata.normalize("NFKC", text)


def _strip_decorations(text: str) -> str:
    """去除括号内的常见装饰词（不区分大小写）。"""
    for pattern in _DECOR_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text


def normalize_text(text: str | None) -> str:
    """
    通用文本标准化。

    步骤：
        1. None 或 空 → 空字符串
        2. 全角 → 半角
        3. 去装饰括号
        4. 折叠空白为单空格
        5. 小写
    """
    if not text:
        return ""
    s = _to_halfwidth(text)
    s = _strip_decorations(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def normalize_song_name(name: str | None) -> str:
    return normalize_text(name)


def normalize_album_name(name: str | None) -> str:
    """专辑名空值统一为 ""，避免唯一索引把 None 当不同值。"""
    return normalize_text(name)


def parse_artists(value: str | None) -> list[str]:
    """把 "周杰伦/林俊杰" "Jay Chou & JJ Lin" 拆成 ['周杰伦', '林俊杰']。"""
    if not value:
        return []
    parts = [p.strip() for p in _ARTIST_SEP_RE.split(value) if p and p.strip()]
    return parts


def normalize_artists(artists: list[str]) -> str:
    """
    歌手列表 → 标准化字符串。

    规则：
        - 取所有歌手名分别标准化
        - 排序（避免 "A,B" 和 "B,A" 视作不同歌曲）
        - 用 / 拼接
    """
    if not artists:
        return ""
    cleaned = sorted(set(filter(None, (normalize_text(a) for a in artists))))
    return "/".join(cleaned)


def normalize_primary_artist(artists: list[str]) -> str:
    """主歌手标准化（用于目录命名）。"""
    if not artists:
        return ""
    return normalize_text(artists[0])


def make_dedupe_key(
    name: str | None,
    artists: list[str],
    album: str | None,
) -> tuple[str, str, str]:
    """
    返回去重三元组：(name_norm, artist_norm, album_norm)。

    与 db.models.Song 的联合唯一索引完全对齐。
    """
    return (
        normalize_song_name(name),
        normalize_artists(artists),
        normalize_album_name(album),
    )
