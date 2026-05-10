"""
网易云 Linux API 加密测试（确定性算法）。
"""

from __future__ import annotations

import json
import re

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from app.crypto import netease_linux


def test_encrypt_returns_uppercase_hex():
    """输出是大写 hex 字符串。"""
    out = netease_linux.encrypt({"url": "http://music.163.com/api/cloudsearch/pc"})
    assert isinstance(out, str)
    assert re.fullmatch(r"[0-9A-F]+", out)
    assert len(out) % 32 == 0


def test_encrypt_deterministic():
    """同输入输出一致。"""
    payload = {
        "url": "http://music.163.com/api/cloudsearch/pc",
        "params": {"s": "周杰伦 晴天", "type": 10, "offset": 0, "limit": 10},
    }
    a = netease_linux.encrypt(payload)
    b = netease_linux.encrypt(payload)
    assert a == b


def test_encrypted_can_be_decrypted():
    """反向解密能还原 payload。"""
    payload = {"url": "x", "params": {"a": 1}}
    encrypted_hex = netease_linux.encrypt(payload)

    cipher = AES.new(netease_linux._KEY, AES.MODE_ECB)
    decrypted = unpad(cipher.decrypt(bytes.fromhex(encrypted_hex)), AES.block_size).decode("utf-8")
    assert json.loads(decrypted) == payload
