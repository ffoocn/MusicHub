"""
本地音频文件清理工具。

所有删除入口统一走这里，避免本地库删除、任务删除、下载失败清理各自处理
sidecar 文件而产生残留或数据库/文件状态不一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.utils.logger import logger


SIDECAR_SUFFIXES = (".lrc", ".jpg", ".jpeg", ".png", ".webp")


@dataclass
class LocalDeleteResult:
    """本地文件删除结果。missing_main=True 表示主体音频本来就不存在。"""

    file_path: str
    file_deleted: bool = False
    missing_main: bool = False
    sidecars_deleted: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok_for_db_delete(self) -> bool:
        """主体文件已删除或原本不存在时，数据库记录可以安全删除。"""
        return self.file_deleted or self.missing_main


def delete_local_song_file(file_path: str | Path) -> LocalDeleteResult:
    """
    删除音频主体和同名 sidecar。

    删除失败时返回 error，不抛出异常；调用方据此决定是否删除数据库记录。
    """
    path = Path(file_path)
    result = LocalDeleteResult(file_path=str(path))
    try:
        if path.exists():
            if path.is_file():
                path.unlink(missing_ok=True)
                result.file_deleted = True
            else:
                result.error = "path exists but is not a file"
                return result
        else:
            result.missing_main = True

        for suffix in SIDECAR_SUFFIXES:
            sidecar = path.with_suffix(suffix)
            if sidecar.exists() and sidecar.is_file():
                sidecar.unlink(missing_ok=True)
                result.sidecars_deleted.append(str(sidecar))
        return result
    except OSError as e:
        result.error = str(e)
        logger.warning(f"delete local song file failed: {path}: {e}")
        return result
