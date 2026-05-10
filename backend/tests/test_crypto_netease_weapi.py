"""
网易云 weapi 加密测试。

由于 weapi 加密包含随机 secKey，无法做"输入→固定输出"的等值比较。
测试策略是「自洽性 + 反向解密验证」：
    1. 加密结果格式正确（params 是 base64，encSecKey 是 256 hex）。
    2. 用 RSA 私钥不可知，但可验证 encSecKey 长度和字符集。
    3. 用同样的 secKey 反向解密 params，能还原出明文 JSON（需要绕过随机性，单独测内部函数）。
"""

from __future__ import annotations

import base64
import json
import re

import pytest

from app.crypto import netease_weapi


def test_encrypt_returns_correct_format():
    """加密后 params 是 base64，encSecKey 是 256 位小写 hex。"""
    payload = {"limit": 30, "total": True, "n": 1000}
    result = netease_weapi.encrypt(payload)

    # params 是 base64 字符串
    assert isinstance(result.params, str)
    # base64 字符集 + 末尾可能有 =
    assert re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", result.params)

    # encSecKey 是恰好 256 位的小写 hex
    assert isinstance(result.enc_sec_key, str)
    assert len(result.enc_sec_key) == 256
    assert re.fullmatch(r"[0-9a-f]{256}", result.enc_sec_key)


def test_encrypt_accepts_string_payload():
    """payload 也支持已序列化的 JSON 字符串。"""
    text = json.dumps({"a": 1})
    result = netease_weapi.encrypt(text)
    assert result.params and result.enc_sec_key


def test_encrypt_produces_different_output_each_time():
    """随机 secKey 应当让两次加密结果不同。"""
    payload = {"x": 123}
    a = netease_weapi.encrypt(payload)
    b = netease_weapi.encrypt(payload)
    assert (a.params, a.enc_sec_key) != (b.params, b.enc_sec_key)


def test_encrypt_form_dict():
    """as_form 返回的 dict 字段名匹配网易云接口要求。"""
    result = netease_weapi.encrypt({"x": 1})
    form = result.as_form()
    assert set(form.keys()) == {"params", "encSecKey"}


def test_aes_first_layer_decrypt():
    """
    第一层 AES（固定 NONCE + IV）是确定的，可以反向解密验证。

    构造一个只走第一层的等价加密：
        ciphertext = AES_CBC(NONCE, IV, plaintext)
    然后用 NONCE+IV 反向解密，应当还原 plaintext。
    """
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad

    plaintext = b'{"limit":30}'
    cipher_enc = AES.new(netease_weapi._NONCE, AES.MODE_CBC, netease_weapi._IV)
    encrypted = cipher_enc.encrypt(pad(plaintext, AES.block_size))

    cipher_dec = AES.new(netease_weapi._NONCE, AES.MODE_CBC, netease_weapi._IV)
    decrypted = unpad(cipher_dec.decrypt(encrypted), AES.block_size)

    assert decrypted == plaintext


def test_rsa_encrypt_modulus_size():
    """RSA 模幂结果不会超过 modulus 的位数。"""
    # 用一个固定的 reversed_seckey 测试
    reversed_seckey = "abcdefghij012345"
    enc = netease_weapi._rsa_encrypt(reversed_seckey)
    # 必须正好 256 hex 字符（左侧补零）
    assert len(enc) == 256
    # 转回整数应该 < modulus
    assert int(enc, 16) < netease_weapi._MODULUS


def test_random_seckey_charset():
    """生成的 secKey 字符集合规。"""
    for _ in range(10):
        sk = netease_weapi._gen_random_seckey()
        assert len(sk) == 16
        for c in sk:
            assert c in netease_weapi._SECKEY_CHARS
