"""
网易云 eapi 加密。

参考文档：docs/netease-download-api.md

eapi 用于高音质下载等内部接口，加密流程：
    1. 把请求路径中的 /eapi/ 替换为 /api/，得到 sign_path。
    2. 计算 MD5：md5("nobody" + sign_path + "use" + payload + "md5forencrypt")
    3. 拼接：sign_path + "-36cd479b6b5-" + payload + "-36cd479b6b5-" + md5
    4. 用 AES-128-ECB + PKCS#7 加密，key="e82ckenh8dichen8"。
    5. 加密结果转小写 hex 作为表单字段 params。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ----- 加密常量（来自网易云客户端） -----
_KEY = b"e82ckenh8dichen8"
_SALT = "36cd479b6b5"


def _to_api_path(eapi_path: str) -> str:
    """把 eapi 请求路径转换为参与签名的 api 路径。"""
    if eapi_path.startswith("/eapi/"):
        return "/api/" + eapi_path[len("/eapi/"):]
    return eapi_path


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def encrypt(eapi_path: str, payload: dict[str, Any] | str) -> str:
    """
    对 eapi 请求做加密。

    Args:
        eapi_path: 接口路径，例如 "/eapi/song/enhance/player/url/v1"。
        payload: 明文 payload。

    Returns:
        加密后的小写 hex 字符串，作为表单字段 params 的值。
    """
    api_path = _to_api_path(eapi_path)

    text = payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    digest = _md5("nobody" + api_path + "use" + text + "md5forencrypt")

    plain = f"{api_path}-{_SALT}-{text}-{_SALT}-{digest}"

    cipher = AES.new(_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(plain.encode("utf-8"), AES.block_size, style="pkcs7"))

    return encrypted.hex()
