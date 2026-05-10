"""
路径生成 + 文件名规则。

输入：歌曲信息 + 语种分类 + 用户设置
输出：相对/绝对文件路径
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from app.config import settings as app_settings
from app.platforms.base import SongInfo

# 非法文件名字符
_ILLEGAL_RE = re.compile(r'[\\/:*?"<>|]')

# Windows 保留名（即使 Linux 上跑也保护一下，方便跨系统使用 NAS）
_RESERVED_WIN = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

DirLayout = Literal["artist-song", "artist-album-song"]
FilenameFormat = Literal["name", "name-artist", "name-artist-album"]


def safe_segment(text: str | None, fallback: str = "未知") -> str:
    """把任意字符串清洗成安全的目录/文件名片段。"""
    if not text:
        return fallback
    s = _ILLEGAL_RE.sub(" ", text)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(". ")  # Windows 下文件名不允许以 . 或空格结尾
    if not s:
        return fallback
    if s.upper() in _RESERVED_WIN:
        s = f"_{s}"
    if len(s) > 200:
        s = s[:200].rstrip()
    return s


def build_filename(song: SongInfo, fmt: FilenameFormat, ext: str) -> str:
    """根据用户偏好生成文件名（不含目录部分）。"""
    name = safe_segment(song.name)
    artist = safe_segment(song.primary_artist, fallback="未知歌手")
    album = safe_segment(song.album, fallback="未知专辑")

    if fmt == "name":
        base = name
    elif fmt == "name-artist":
        base = f"{name} - {artist}"
    else:
        base = f"{name} - {artist} - {album}"
    return f"{base}.{ext.lstrip('.')}"


def build_relative_path(
    song: SongInfo,
    audio_format: str,
    *,
    layout: DirLayout = "artist-album-song",
    filename_fmt: FilenameFormat = "name-artist",
) -> Path:
    """
    构造相对于 MUSIC_DIR 的相对路径。

    示例：
        - 简化布局：周杰伦/七里香 - 周杰伦.flac
        - 完整布局：周杰伦/七里香/七里香 - 周杰伦.flac
    """
    artist = safe_segment(song.primary_artist, fallback="未知歌手")

    parts: list[str] = [artist]
    if layout == "artist-album-song":
        parts.append(safe_segment(song.album, fallback="未知专辑"))
    parts.append(build_filename(song, filename_fmt, audio_format))
    return Path(*parts)


def build_absolute_path(
    song: SongInfo,
    audio_format: str,
    *,
    layout: DirLayout = "artist-album-song",
    filename_fmt: FilenameFormat = "name-artist",
    music_dir: Path | None = None,
) -> Path:
    """绝对路径 = music_dir / 相对路径。music_dir 未传时回退到环境变量配置。"""
    rel = build_relative_path(
        song,
        audio_format,
        layout=layout,
        filename_fmt=filename_fmt,
    )
    base = music_dir if music_dir is not None else app_settings.music_dir
    return base / rel


def build_lrc_path(audio_path: Path) -> Path:
    """对应歌词文件路径（同名 .lrc）。"""
    return audio_path.with_suffix(".lrc")


def build_cover_path(audio_path: Path) -> Path:
    """对应封面文件路径（同名 .jpg）。"""
    return audio_path.with_suffix(".jpg")
