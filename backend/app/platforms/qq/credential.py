"""
QQ Music cookie / Credential 转换工具。
"""

from __future__ import annotations

from typing import Any

from qqmusic_api.models.request import Credential


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def cookie_to_credential(cookie: dict[str, str]) -> Credential:
    """
    将当前项目持久化的 cookie 结构转换为 qqmusic_api 的 Credential。
    """
    musicid = _to_int(cookie.get("musicid") or cookie.get("uin") or cookie.get("qqmusic_uin"), 0)
    musickey = cookie.get("qm_keyst") or cookie.get("qqmusic_key") or ""
    login_type = _to_int(cookie.get("login_type"), 0)
    if login_type not in (1, 2):
        # qqmusic_api: 1=wx, 2=qq；默认按 QQ 处理
        login_type = 2

    return Credential(
        musicid=musicid,
        str_musicid=str(musicid) if musicid else "",
        musickey=musickey,
        openid=cookie.get("wxopenid") or cookie.get("openid") or "",
        refresh_token=cookie.get("refresh_token") or "",
        refresh_key=cookie.get("refresh_key") or "",
        access_token=cookie.get("wxaccess_token") or cookie.get("access_token") or "",
        unionid=cookie.get("wxunionid") or cookie.get("unionid") or "",
        encryptUin=cookie.get("encryptUin") or cookie.get("encrypt_uin") or "",
        loginType=login_type,
    )


def credential_to_cookie(
    credential: Credential,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    将 qqmusic_api Credential 转回项目 cookie 持久化结构。
    """
    out: dict[str, str] = {}
    if credential.musicid:
        out["musicid"] = str(credential.musicid)
        out["uin"] = str(credential.musicid)
        out["qqmusic_uin"] = str(credential.musicid)
    if credential.str_musicid:
        out["str_musicid"] = credential.str_musicid
    if credential.musickey:
        out["qm_keyst"] = credential.musickey
        out["qqmusic_key"] = credential.musickey
    if credential.openid:
        out["wxopenid"] = credential.openid
        out["openid"] = credential.openid
    if credential.unionid:
        out["wxunionid"] = credential.unionid
        out["unionid"] = credential.unionid
    if credential.refresh_token:
        out["refresh_token"] = credential.refresh_token
    if credential.refresh_key:
        out["refresh_key"] = credential.refresh_key
    if credential.access_token:
        out["wxaccess_token"] = credential.access_token
        out["access_token"] = credential.access_token
    if credential.encrypt_uin:
        out["encryptUin"] = credential.encrypt_uin
    if credential.login_type:
        out["login_type"] = str(credential.login_type)

    if extra:
        out.update(extra)
    return out

