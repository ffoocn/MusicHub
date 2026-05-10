"""
异步 SQLAlchemy 会话管理。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.db.models import Base
from app.utils.logger import logger

# 全局引擎和会话工厂
_engine = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine, _session_maker
    if _engine is None:
        settings.ensure_dirs()
        _engine = create_async_engine(
            settings.db_url,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        # SQLite 并发优化：WAL 模式 + busy_timeout。
        #
        # 之前这里全局使用 BEGIN IMMEDIATE，连纯读取请求都会先抢写锁。
        # 后台下载/同步任务持锁时，订阅列表和父级开关都会被一起堵住。
        # 改回普通 BEGIN：读请求保持 WAL 的读写并发，写入冲突交给
        # busy_timeout 等待，避免 UI 因为只读查询而卡死。
        @event.listens_for(_engine.sync_engine, "connect")
        def _on_connect(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
            # 让 SQLAlchemy 完全接管事务边界，不再让 pysqlite/aiosqlite
            # 在写语句前自动 emit BEGIN（DEFERRED）。
            dbapi_connection.isolation_level = None

        @event.listens_for(_engine.sync_engine, "begin")
        def _on_begin(conn):
            conn.exec_driver_sql("BEGIN")

        _session_maker = async_sessionmaker(
            bind=_engine, expire_on_commit=False, class_=AsyncSession
        )
        logger.info(f"DB engine initialized: {settings.db_url} (WAL mode)")
    return _engine


async def init_db() -> None:
    """启动时调用：建表 + 自动添加新字段（轻量迁移，不动已有数据）。"""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_auto_migrate)
    logger.info("DB tables ensured.")


def _auto_migrate(sync_conn) -> None:
    """
    SQLite 轻量迁移：模型新增字段时通过 ALTER TABLE ADD COLUMN 兼容旧库。

    不删除字段、不改类型，只补缺失的列。
    """
    inspector = inspect(sync_conn)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            # 用 SQLAlchemy 编译列定义
            col_type = col.type.compile(dialect=sync_conn.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
            if not col.nullable and col.default is None:
                # 加非空列时 SQLite 要求默认值，这里跳过非空字段（设计上新字段都允许 NULL）
                logger.warning(
                    f"skip auto-migrate non-null column {table.name}.{col.name}"
                )
                continue
            try:
                sync_conn.execute(text(ddl))
                logger.info(f"auto-migrate: ADD COLUMN {table.name}.{col.name}")
            except Exception as e:
                logger.warning(f"auto-migrate failed for {table.name}.{col.name}: {e}")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入用：每个请求一个会话。"""
    _get_engine()
    assert _session_maker is not None
    async with _session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def session_factory():
    """非 FastAPI 上下文用：手动获取一个会话。"""
    _get_engine()
    assert _session_maker is not None
    return _session_maker()
