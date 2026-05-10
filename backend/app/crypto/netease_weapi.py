"""
网易云 weapi 加密。

参考文档：docs/netease-qr-login-api.md、docs/daily-playlist-api.md

加密流程：
    1. 生成 16 位随机 secKey。
    2. 第一层 AES-128-CBC：key=NONCE，iv=IV，明文=JSON 字符串，结果 base64 → first。
    3. 第二层 AES-128-CBC：key=secKey，iv=IV，明文=first，结果 base64 → params。
    4. 把 secKey 反转后转 hex，做 RSA: encSecKey = pow(reversed_int, e, modulus)，
       结果转小写 hex 并左侧补零至 256 字符。
    5. 最终表单：params=<params>&encSecKey=<encSecKey>。
"""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ----- 加密常量（来自网易云客户端） -----
_NONCE = b"0CoJUm6Qyw8W8jud"
_IV = b"0102030405060708"
_PUB_KEY = 0x010001  # RSA 公钥指数 e
_MODULUS = int(
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725"
    "152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312"
    "ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424"
    "d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7",
    16,
)

# 随机 secKey 字符集
_SECKEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _aes_cbc_b64(plaintext: bytes, key: bytes) -> bytes:
    """AES-128-CBC 加密 + PKCS#7 填充 + base64 编码。"""
    cipher = AES.new(key, AES.MODE_CBC, _IV)
    encrypted = cipher.encrypt(pad(plaintext, AES.block_size, style="pkcs7"))
    return base64.b64encode(encrypted)


def _gen_random_seckey(length: int = 16) -> str:
    """生成随机 secKey（字符集见常量）。"""
    return "".join(secrets.choice(_SECKEY_CHARS) for _ in range(length))


def _rsa_encrypt(reversed_seckey: str) -> str:
    """RSA 加密 secKey（反转后转 int 做模幂运算）。返回左补零至 256 hex。"""
    n = int(reversed_seckey.encode("utf-8").hex(), 16)
    encrypted = pow(n, _PUB_KEY, _MODULUS)
    return format(encrypted, "x").zfill(256)


@dataclass
class WeapiPayload:
    """weapi 加密结果，可作为表单字段提交。"""

    params: str
    enc_sec_key: str

    def as_form(self) -> dict[str, str]:
        """转换成 application/x-www-form-urlencoded 表单数据。"""
        return {"params": self.params, "encSecKey": self.enc_sec_key}


def encrypt(payload: dict[str, Any] | str) -> WeapiPayload:
    """
    对明文 payload 做 weapi 加密。

    Args:
        payload: 明文，dict 或已序列化的 JSON 字符串。

    Returns:
        WeapiPayload，包含 params 和 encSecKey 两个字段。
    """
    text = payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    plaintext = text.encode("utf-8")

    # 第一层：固定 NONCE 加密
    first = _aes_cbc_b64(plaintext, _NONCE)

    # 第二层：随机 secKey 加密
    sec_key = _gen_random_seckey(16)
    params = _aes_cbc_b64(first, sec_key.encode("utf-8")).decode("utf-8")

    # RSA 加密 secKey（反转后）
    reversed_sec_key = sec_key[::-1]
    enc_sec_key = _rsa_encrypt(reversed_sec_key)

    return WeapiPayload(params=params, enc_sec_key=enc_sec_key)
