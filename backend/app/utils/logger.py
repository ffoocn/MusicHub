"""
统一日志配置。

使用 loguru 替换 stdlib logging，所有模块通过 `from app.utils.logger import logger` 使用。
"""

from __future__ import annotations

import sys

from loguru import logger as _logger

from app.config import settings


def _setup_logger() -> None:
    """初始化 loguru，输出到 stderr，按配置级别过滤。"""
    _logger.remove()
    _logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=False,  # 生产环境不打印变量值，避免泄露 Cookie
    )


_setup_logger()

logger = _logger
