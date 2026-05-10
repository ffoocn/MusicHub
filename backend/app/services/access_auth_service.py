"""
应用访问密码鉴权服务。

单用户自托管场景下，不引入完整用户体系；只用 settings 表保存：
    - 访问密码哈希
    - 当前有效会话 token

密码使用 PBKDF2-HMAC-SHA256 哈希，避免明文落库。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting

PASSWORD_HASH_KEY = "access.password_hash"
SESSION_TOKEN_KEY = "access.session_token"
DEFAULT_ACCESS_PASSWORD = "musichub"

_HASH_ALGO = "pbkdf2_sha256"
_HASH_ITERATIONS = 200_000


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    """生成可持久化的密码哈希串。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _HASH_ITERATIONS,
    )
    return f"{_HASH_ALGO}${_HASH_ITERATIONS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    """常量时间比较密码。"""
    if not stored_hash:
        return False
    try:
        algo, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if algo != _HASH_ALGO:
            return False
        iterations = int(iterations_raw)
        salt = _decode(salt_raw)
        expected = _decode(digest_raw)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


async def _get_setting(session: AsyncSession, key: str) -> Any:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    return None if row is None else row.value


async def _set_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))


async def ensure_access_defaults(session: AsyncSession) -> None:
    """首次启动时初始化默认访问密码。"""
    current_hash = await _get_setting(session, PASSWORD_HASH_KEY)
    if not current_hash:
        await _set_setting(session, PASSWORD_HASH_KEY, hash_password(DEFAULT_ACCESS_PASSWORD))
        await _set_setting(session, SESSION_TOKEN_KEY, None)
        await session.commit()


async def login(session: AsyncSession, password: str) -> str | None:
    """密码正确时生成并保存新的会话 token。"""
    stored_hash = await _get_setting(session, PASSWORD_HASH_KEY)
    if not verify_password(password, stored_hash):
        return None
    token = secrets.token_urlsafe(32)
    await _set_setting(session, SESSION_TOKEN_KEY, token)
    await session.commit()
    return token


async def is_token_valid(session: AsyncSession, token: str | None) -> bool:
    if not token:
        return False
    stored_token = await _get_setting(session, SESSION_TOKEN_KEY)
    return bool(stored_token) and hmac.compare_digest(str(stored_token), token)


async def change_password(
    session: AsyncSession,
    current_password: str,
    new_password: str,
) -> bool:
    """校验旧密码后更新新密码，并使旧 token 失效。"""
    stored_hash = await _get_setting(session, PASSWORD_HASH_KEY)
    if not verify_password(current_password, stored_hash):
        return False
    await _set_setting(session, PASSWORD_HASH_KEY, hash_password(new_password))
    await _set_setting(session, SESSION_TOKEN_KEY, secrets.token_urlsafe(32))
    await session.commit()
    return True


async def logout(session: AsyncSession) -> None:
    await _set_setting(session, SESSION_TOKEN_KEY, None)
    await session.commit()
