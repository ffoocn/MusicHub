"""
网易云 eapi 加密测试。

eapi 是确定性加密（无随机），所以可以做「固定输入 → 固定输出」对照。
"""

from __future__ import annotations

import hashlib
import json
import re

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from app.crypto import netease_eapi


def test_encrypt_returns_lowercase_hex():
    """eapi 输出是小写 hex 字符串。"""
    out = netease_eapi.encrypt("/eapi/song/enhance/player/url/v1", {"ids": [1], "level": "exhigh"})
    assert isinstance(out, str)
    assert re.fullmatch(r"[0-9a-f]+", out)
    # 每个 AES 块 16 字节 = 32 hex，长度必为 32 的倍数
    assert len(out) % 32 == 0


def test_encrypt_deterministic():
    """同样输入应得到完全相同的输出（无随机源）。"""
    a = netease_eapi.encrypt("/eapi/foo", {"x": 1})
    b = netease_eapi.encrypt("/eapi/foo", {"x": 1})
    assert a == b


def test_encrypt_path_replacement_affects_signature():
    """eapi 路径中 /eapi/ 会被替换为 /api/ 参与签名，不同路径必须产生不同结果。"""
    a = netease_eapi.encrypt("/eapi/path/a", {"x": 1})
    b = netease_eapi.encrypt("/eapi/path/b", {"x": 1})
    assert a != b


def test_encrypt_payload_difference_changes_output():
    """payload 不同必然产生不同输出。"""
    a = netease_eapi.encrypt("/eapi/foo", {"x": 1})
    b = netease_eapi.encrypt("/eapi/foo", {"x": 2})
    assert a != b


def test_encrypted_can_be_decrypted_and_validates_md5():
    """
    把 encrypt 的结果反向解密，验证：
      1) 内部结构 = api_path + "-SALT-" + payload + "-SALT-" + md5
      2) md5 = md5("nobody" + api_path + "use" + payload + "md5forencrypt")
    """
    eapi_path = "/eapi/song/enhance/player/url/v1"
    payload_obj = {"ids": [3344811140], "level": "exhigh", "encodeType": "flac"}

    encrypted_hex = netease_eapi.encrypt(eapi_path, payload_obj)
    cipher = AES.new(netease_eapi._KEY, AES.MODE_ECB)
    decrypted = unpad(cipher.decrypt(bytes.fromhex(encrypted_hex)), AES.block_size).decode("utf-8")

    # 内部结构
    salt = netease_eapi._SALT
    parts = decrypted.split(f"-{salt}-")
    assert len(parts) == 3, f"unexpected structure: {decrypted!r}"
    api_path, payload_text, md5_hex = parts

    # 路径在签名时已替换 /eapi/ 为 /api/
    assert api_path == "/api/song/enhance/player/url/v1"

    # payload 还原
    assert json.loads(payload_text) == payload_obj

    # md5 验证
    expected = hashlib.md5(
        ("nobody" + api_path + "use" + payload_text + "md5forencrypt").encode("utf-8")
    ).hexdigest()
    assert md5_hex == expected


def test_path_without_eapi_prefix_is_used_as_is():
    """非 /eapi/ 开头的路径不替换，原样进入签名。"""
    out_a = netease_eapi.encrypt("/api/raw/path", {"x": 1})
    out_b = netease_eapi.encrypt("/eapi/raw/path", {"x": 1})
    # /eapi/raw/path 会被替换为 /api/raw/path，所以两者应相等
    assert out_a == out_b
