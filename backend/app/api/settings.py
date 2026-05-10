"""
设置路由：读取/更新全局配置。

历史遗留的「语种分类」功能已下线（识别准确率低，目录布局也不再用语种顶层），
只保留下载偏好、目录命名、m3u 等键值对设置。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    items: dict[str, Any]


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session)):
    return await settings_service.get_all(session)


@router.put("")
async def update_settings(
    body: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    await settings_service.set_many(session, body.items)
    return await settings_service.get_all(session)
