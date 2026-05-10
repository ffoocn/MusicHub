"""
认证路由（M1 阶段：扫码登录）。

接口：
    POST   /api/auth/qr/{platform}              创建二维码
        网易云：           type 参数无效，固定走 weapi 扫码
        QQ 音乐：          type=qq（默认）QQ 扫码，type=wx 微信扫码，type=mobile QQ音乐APP扫码
    GET    /api/auth/qr/{platform}/poll         轮询状态（携带 ticket）
    GET    /api/auth/status                     账号状态汇总
    DELETE /api/auth/{platform}                 登出
"""

from __future__ import annotations

import base64
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account
from app.db.session import get_session
from app.platforms.base import LoginQRCode, PlatformID
from app.platforms.netease import NeteaseClient
from app.platforms.qq import QQClient

router = APIRouter(prefix="/api/auth", tags=["auth"])


# 进程内缓存：ticket -> client，保留扫码会话期间产生的 cookie
_qr_clients: dict[str, NeteaseClient | QQClient] = {}


def _make_client(platform: PlatformID, cookie: dict[str, str] | None = None):
    if platform == PlatformID.NETEASE:
        return NeteaseClient(cookie=cookie)
    if platform == PlatformID.QQ:
        return QQClient(cookie=cookie)
    raise HTTPException(status_code=400, detail=f"unknown platform: {platform}")


@router.post("/qr/{platform}")
async def create_qr(
    platform: Literal["netease", "qq"],
    type: Literal["qq", "wx", "mobile"] = Query(
        default="qq",
        description="QQ 音乐扫码方式：qq=QQ 扫码，wx=微信扫码，mobile=QQ音乐APP扫码。其他平台忽略此参数。",
    ),
):
    """创建扫码登录二维码。"""
    pid = PlatformID(platform)
    cli = _make_client(pid)
    if pid is PlatformID.QQ and type in {"wx", "mobile"}:
        assert isinstance(cli, QQClient)
        if type == "wx":
            qr = await cli.create_wx_qr_login()
        else:
            qr = await cli.create_mobile_qr_login()
    else:
        qr = await cli.create_qr_login()
    _qr_clients[qr.ticket] = cli
    return {
        "platform": platform,
        "type": type if pid is PlatformID.QQ else "default",
        "ticket": qr.ticket,
        "qr_url": qr.qr_url,
        "qr_image_b64": (
            base64.b64encode(qr.qr_image_png).decode("ascii")
            if qr.qr_image_png
            else None
        ),
        "created_at_ms": qr.created_at_ms,
    }


@router.get("/qr/{platform}/poll")
async def poll_qr(
    platform: Literal["netease", "qq"],
    ticket: str = Query(..., description="create_qr 返回的 ticket"),
    session: AsyncSession = Depends(get_session),
):
    """轮询扫码状态。登录成功时把 Cookie 持久化到 accounts 表。"""
    pid = PlatformID(platform)
    cli = _qr_clients.get(ticket)
    if cli is None:
        raise HTTPException(status_code=404, detail="ticket not found or expired")

    qr_obj = LoginQRCode(platform=pid, ticket=ticket, qr_url="")
    # ticket 前缀区分 qq/wx/mobile 三种扫码会话
    if pid is PlatformID.QQ and ticket.startswith("wx:"):
        assert isinstance(cli, QQClient)
        result = await cli.poll_wx_qr_login(qr_obj)
    elif pid is PlatformID.QQ and ticket.startswith("mobile:"):
        assert isinstance(cli, QQClient)
        result = await cli.poll_mobile_qr_login(qr_obj)
    else:
        result = await cli.poll_qr_login(qr_obj)

    if result.status.value == "success":
        existing = await session.scalar(select(Account).where(Account.platform == platform))
        if existing:
            existing.cookie_json = result.cookie
            existing.user_id = result.user_id
            existing.nickname = result.nickname
            existing.vip_type = result.vip_type
            existing.vip_icons = result.vip_icons or None
            existing.avatar_url = result.avatar_url
            existing.is_valid = True
        else:
            session.add(
                Account(
                    platform=platform,
                    cookie_json=result.cookie,
                    user_id=result.user_id,
                    nickname=result.nickname,
                    vip_type=result.vip_type,
                    vip_icons=result.vip_icons or None,
                    avatar_url=result.avatar_url,
                    is_valid=True,
                )
            )
        await session.commit()
        _qr_clients.pop(ticket, None)

    return {
        "platform": platform,
        "status": result.status.value,
        "user_id": result.user_id,
        "nickname": result.nickname,
        "vip_type": result.vip_type,
        "vip_icons": result.vip_icons or [],
        "avatar_url": result.avatar_url,
        "message": result.raw_message,
    }


@router.get("/status")
async def status(session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(Account))).all()
    return [
        {
            "platform": r.platform,
            "user_id": r.user_id,
            "nickname": r.nickname,
            "vip_type": r.vip_type,
            "vip_icons": r.vip_icons or [],
            "avatar_url": r.avatar_url,
            "is_valid": r.is_valid,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


@router.post("/refresh/{platform}")
async def refresh_profile(
    platform: Literal["netease", "qq"],
    session: AsyncSession = Depends(get_session),
):
    """
    用现有 Cookie 重新拉一次账号信息（昵称 / VIP / 头像）并写回数据库。

    使用场景：
        - 老账号在加 `avatar_url` 字段前登录的，数据库里没有头像，调一次就能补齐。
        - QQ 登录后偶发拿不到昵称的情况，用户在前端点"刷新"重新尝试。
    """
    existing = await session.scalar(select(Account).where(Account.platform == platform))
    if not existing or not existing.cookie_json:
        raise HTTPException(status_code=404, detail="未登录")

    pid = PlatformID(platform)
    cli = _make_client(pid, existing.cookie_json)
    result = await cli.check_login()
    if result.status.value != "success":
        raise HTTPException(
            status_code=400,
            detail=f"Cookie 已失效：{result.raw_message or result.status.value}",
        )

    # 仅在拿到真值时才覆盖，避免把已有的有效字段刷成 None
    if result.cookie:
        existing.cookie_json = result.cookie
    if result.user_id:
        existing.user_id = result.user_id
    if result.nickname:
        existing.nickname = result.nickname
    if result.vip_type is not None:
        existing.vip_type = result.vip_type
    if result.vip_icons:
        existing.vip_icons = result.vip_icons
    if result.avatar_url:
        existing.avatar_url = result.avatar_url
    existing.is_valid = True
    await session.commit()
    return {
        "platform": platform,
        "user_id": existing.user_id,
        "nickname": existing.nickname,
        "vip_type": existing.vip_type,
        "vip_icons": existing.vip_icons or [],
        "avatar_url": existing.avatar_url,
    }


@router.delete("/{platform}")
async def logout(
    platform: Literal["netease", "qq"],
    session: AsyncSession = Depends(get_session),
):
    existing = await session.scalar(select(Account).where(Account.platform == platform))
    if existing:
        await session.delete(existing)
        await session.commit()
    return {"platform": platform, "status": "logged_out"}


# ==================================================================
# Cookie 字符串导入（兜底登录方案）
# ==================================================================
class CookieImportRequest(BaseModel):
    """从浏览器 F12 复制的整段 Cookie 字符串。"""

    cookie: str


@router.post("/cookie/{platform}")
async def import_cookie(
    platform: Literal["netease", "qq"],
    body: CookieImportRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    用浏览器 cookie 字符串完成登录。

    优势：扫码无法换到关键 cookie 时（如 QQ 音乐 musicid/qm_keyst），
    用户可以登录 y.qq.com / music.163.com 后从 F12 复制 cookie 进来。
    """
    pid = PlatformID(platform)
    parsed = _parse_cookie_string(body.cookie)
    if not parsed:
        raise HTTPException(status_code=400, detail="cookie 字符串解析失败，请检查格式")

    cli = _make_client(pid, parsed)
    result = await cli.check_login()
    if result.status.value != "success":
        raise HTTPException(
            status_code=400,
            detail=f"cookie 无效或缺少关键字段：{result.raw_message or result.status.value}",
        )

    existing = await session.scalar(select(Account).where(Account.platform == platform))
    if existing:
        existing.cookie_json = result.cookie or parsed
        existing.user_id = result.user_id
        existing.nickname = result.nickname
        existing.vip_type = result.vip_type
        existing.vip_icons = result.vip_icons or None
        existing.avatar_url = result.avatar_url
        existing.is_valid = True
    else:
        session.add(
            Account(
                platform=platform,
                cookie_json=result.cookie or parsed,
                user_id=result.user_id,
                nickname=result.nickname,
                vip_type=result.vip_type,
                vip_icons=result.vip_icons or None,
                avatar_url=result.avatar_url,
                is_valid=True,
            )
        )
    await session.commit()
    return {
        "platform": platform,
        "status": "success",
        "user_id": result.user_id,
        "nickname": result.nickname,
        "vip_type": result.vip_type,
        "vip_icons": result.vip_icons or [],
        "avatar_url": result.avatar_url,
    }


def _parse_cookie_string(cookie: str) -> dict[str, str]:
    """支持 'a=1; b=2; c=3' 或 'a=1\\nb=2' 格式。"""
    parts = cookie.replace("\n", ";").split(";")
    out: dict[str, str] = {}
    for p in parts:
        p = p.strip()
        if not p or "=" not in p:
            continue
        k, _, v = p.partition("=")
        k = k.strip()
        v = v.strip()
        if k and v:
            out[k] = v
    return out
