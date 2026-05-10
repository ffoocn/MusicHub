"""
网易云 Linux API 加密。

参考文档：docs/media-metadata-api.md（专辑搜索）

加密流程：
    1. 序列化 JSON 字符串。
    2. AES-128-ECB + PKCS#7 加密，key=固定 hex。
    3. 输出大写 hex 作为表单字段 eparams 的值。
"""

from __future__ import annotations

import json
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# 固定 key（hex 字符串转 bytes）
_KEY = bytes.fromhex("7246674226682325323F5E6544673A51")


def encrypt(payload: dict[str, Any] | str) -> str:
    """
    Linux api 加密。

    Args:
        payload: 明文（含 url 和 params 的内层结构）。

    Returns:
        大写 hex 字符串。
    """
    text = payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    cipher = AES.new(_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(text.encode("utf-8"), AES.block_size, style="pkcs7"))
    return encrypted.hex().upper()
