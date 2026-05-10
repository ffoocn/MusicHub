"""应用访问密码鉴权路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services import access_auth_service

router = APIRouter(prefix="/api/access", tags=["access"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


async def require_access_token(
    x_musichub_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    """需要已登录访问 token 的接口依赖。"""
    if not await access_auth_service.is_token_valid(session, x_musichub_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或会话已失效",
        )


@router.get("/status")
async def access_status(
    x_musichub_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    return {
        "authenticated": await access_auth_service.is_token_valid(session, x_musichub_token),
    }


@router.post("/login")
async def access_login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    token = await access_auth_service.login(session, body.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访问密码错误",
        )
    return {"token": token}


@router.post("/password", dependencies=[Depends(require_access_token)])
async def change_access_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    ok = await access_auth_service.change_password(
        session,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误",
        )
    return {"status": "ok"}


@router.post("/logout")
async def access_logout(session: AsyncSession = Depends(get_session)):
    await access_auth_service.logout(session)
    return {"status": "logged_out"}
