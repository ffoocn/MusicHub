"""
音频元数据写入服务（基于 mutagen）。

支持的格式：
    - MP3 (ID3v2.4)
    - FLAC (Vorbis Comment + 内嵌封面)
    - OGG Vorbis (类似 FLAC)

输入：本地音频文件路径 + SongInfo + 可选封面字节 + 可选 LRC 歌词
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, ID3NoHeaderError, TALB, TIT2, TPE1, TPE2, USLT
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis

from app.platforms.base import SongInfo
from app.utils.logger import logger


def _detect_cover_mime(data: bytes) -> str:
    """简单根据魔术字判断 jpeg/png。"""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    return "image/jpeg"


def write_tags(
    audio_path: Path,
    song: SongInfo,
    *,
    cover_bytes: Optional[bytes] = None,
    lyric_text: Optional[str] = None,
) -> None:
    """
    写入元数据。根据扩展名自动选择格式。

    错误时仅记日志，不中断主流程（写标签失败不应该让下载失败）。
    """
    try:
        ext = audio_path.suffix.lower().lstrip(".")
        if ext == "mp3":
            _write_mp3(audio_path, song, cover_bytes, lyric_text)
        elif ext == "flac":
            _write_flac(audio_path, song, cover_bytes, lyric_text)
        elif ext == "ogg":
            _write_ogg(audio_path, song, cover_bytes, lyric_text)
        else:
            logger.warning(f"unsupported tag format: {ext}, skip")
    except Exception as e:
        logger.warning(f"write_tags failed for {audio_path.name}: {e}")


# ==================================================================
# MP3 (ID3v2.4)
# ==================================================================
def _write_mp3(
    path: Path,
    song: SongInfo,
    cover: Optional[bytes],
    lyric: Optional[str],
) -> None:
    try:
        audio = MP3(path, ID3=ID3)
    except Exception:
        audio = MP3(path)

    try:
        tags = audio.tags
        if tags is None:
            audio.add_tags()
            tags = audio.tags
    except ID3NoHeaderError:
        audio.add_tags()
        tags = audio.tags
    assert tags is not None

    tags.add(TIT2(encoding=3, text=song.name))
    if song.artists:
        tags.add(TPE1(encoding=3, text=song.artists))
        tags.add(TPE2(encoding=3, text=song.primary_artist))
    if song.album:
        tags.add(TALB(encoding=3, text=song.album))
    if lyric:
        tags.add(USLT(encoding=3, lang="chi", desc="", text=lyric))
    if cover:
        tags.delall("APIC")
        tags.add(
            APIC(
                encoding=3,
                mime=_detect_cover_mime(cover),
                type=3,  # cover (front)
                desc="Cover",
                data=cover,
            )
        )
    audio.save(v2_version=4)


# ==================================================================
# FLAC
# ==================================================================
def _write_flac(
    path: Path,
    song: SongInfo,
    cover: Optional[bytes],
    lyric: Optional[str],
) -> None:
    audio = FLAC(path)
    audio["title"] = song.name
    if song.artists:
        audio["artist"] = song.artists
        audio["albumartist"] = song.primary_artist
    if song.album:
        audio["album"] = song.album
    if lyric:
        audio["lyrics"] = lyric
    if cover:
        audio.clear_pictures()
        pic = Picture()
        pic.type = 3
        pic.mime = _detect_cover_mime(cover)
        pic.desc = "Cover"
        pic.data = cover
        audio.add_picture(pic)
    audio.save()


# ==================================================================
# OGG Vorbis
# ==================================================================
def _write_ogg(
    path: Path,
    song: SongInfo,
    cover: Optional[bytes],
    lyric: Optional[str],
) -> None:
    audio = OggVorbis(path)
    audio["title"] = song.name
    if song.artists:
        audio["artist"] = song.artists
        audio["albumartist"] = song.primary_artist
    if song.album:
        audio["album"] = song.album
    if lyric:
        audio["lyrics"] = lyric
    # OGG 封面嵌入复杂（需 base64 编码 + METADATA_BLOCK_PICTURE），简化：旁存即可
    audio.save()


def save_sidecar_lrc(audio_path: Path, lyric: str) -> Path | None:
    """同名 .lrc 文件旁存。"""
    if not lyric:
        return None
    p = audio_path.with_suffix(".lrc")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(lyric, encoding="utf-8")
    return p


def save_sidecar_cover(audio_path: Path, cover_bytes: bytes) -> Path | None:
    """同名 .jpg 文件旁存。"""
    if not cover_bytes:
        return None
    p = audio_path.with_suffix(".jpg")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(cover_bytes)
    return p
