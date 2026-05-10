"""
全局配置模块。

使用 pydantic-settings 从环境变量加载配置，并提供单例 `settings`。
所有运行时常量（端口、目录、日志级别等）都集中在这里。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置。从环境变量读取，未设置时使用默认值。"""

    # 服务监听端口
    port: int = Field(default=5173, description="FastAPI 监听端口")

    # 音乐文件输出根目录（容器内绝对路径）
    music_dir: Path = Field(default=Path("/music"), description="音乐输出根目录")

    # 配置/数据库目录（容器内绝对路径）
    config_dir: Path = Field(default=Path("/config"), description="配置和数据库目录")

    # 日志级别
    log_level: str = Field(default="INFO", description="日志级别 DEBUG|INFO|WARNING|ERROR")

    # 时区
    tz: str = Field(default="Asia/Shanghai", description="时区")

    # 可选 HTTP 代理
    http_proxy: str | None = Field(default=None, description="可选 HTTP 代理")
    https_proxy: str | None = Field(default=None, description="可选 HTTPS 代理")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # 派生路径属性
    # ------------------------------------------------------------------
    @property
    def db_path(self) -> Path:
        """SQLite 数据库文件路径。"""
        return self.config_dir / "musichub.db"

    @property
    def db_url(self) -> str:
        """SQLAlchemy 异步连接串。"""
        return f"sqlite+aiosqlite:///{self.db_path}"

    @property
    def m3u_dir(self) -> Path:
        """m3u8 歌单输出目录。"""
        return self.music_dir / "_m3u"

    def ensure_dirs(self) -> None:
        """启动时确保所有必需目录存在。"""
        for d in (self.music_dir, self.config_dir, self.m3u_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取单例配置对象。"""
    return Settings()


settings = get_settings()
