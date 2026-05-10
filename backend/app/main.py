"""
FastAPI 应用入口。

在仓库根目录启动时**必须**设置 ``PYTHONPATH=backend``，否则 ``import app`` 会失败。

推荐：``./scripts/run-backend.sh``（见 readme「本地开发快速启动」）。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import auth as auth_router
from app.api import discover as discover_router
from app.api import download as download_router
from app.api import health as health_router
from app.api import library as library_router
from app.api import preview as preview_router
from app.api import settings as settings_router
from app.api import stats as stats_router
from app.api import subscriptions as sub_router
from app.api import tasks as tasks_router
from app.config import settings
from app.db.session import init_db, session_factory
from app.services import scheduler as scheduler_service
from app.services import settings_service
from app.services.task_manager import TaskManager
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用启动/关闭钩子。"""
    settings.ensure_dirs()
    await init_db()
    async with session_factory() as session:
        await settings_service.ensure_defaults(session)
    await TaskManager.get().start()
    await scheduler_service.start()
    logger.info(f"MusicHub v{__version__} started on port {settings.port}")
    logger.info(f"music_dir={settings.music_dir}, config_dir={settings.config_dir}")
    yield
    logger.info("MusicHub stopping...")
    try:
        await scheduler_service.stop()
    except Exception as e:
        logger.warning(f"scheduler stop error: {e}")
    try:
        await TaskManager.get().stop()
    except Exception as e:
        logger.warning(f"TaskManager stop error: {e}")


app = FastAPI(
    title="MusicHub",
    description="自托管多平台音乐下载器（网易云 + QQ 音乐）",
    version=__version__,
    lifespan=lifespan,
)


# 开发期允许跨域（前端 dev server 调后端时要用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- API 路由 ----------
app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(discover_router.router)
app.include_router(download_router.router)
app.include_router(settings_router.router)
app.include_router(tasks_router.router)
app.include_router(sub_router.router)
app.include_router(sub_router.m3u_router)
app.include_router(preview_router.router)
app.include_router(library_router.router)
app.include_router(stats_router.router)
# WebSocket 路由会自动挂载在 /api/tasks/ws


# ---------- 静态文件（前端构建产物）----------
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=_static_dir / "assets"),
        name="assets",
    )
    # Vite 将 ``public/images`` 拷到 ``dist/images``；必须单独挂载，否则会被下方 SPA 兜底当成路由并返回 index.html，导致平台 PNG 裂图。
    _images_dir = _static_dir / "images"
    if _images_dir.is_dir():
        app.mount(
            "/images",
            StaticFiles(directory=_images_dir),
            name="images",
        )

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(_static_dir / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """SPA 路由兜底：所有非 /api 路径都返回 index.html，由前端路由处理。"""
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        index = _static_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        from fastapi import HTTPException

        raise HTTPException(status_code=404)
else:
    @app.get("/")
    async def root_no_static() -> dict[str, str]:
        return {
            "service": "musichub",
            "version": __version__,
            "note": "frontend not built; visit /docs for OpenAPI",
        }
