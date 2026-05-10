"""
QQ hash33 算法测试。

通过 JS 参考实现得出的若干已知 (输入, 输出) 对验证。
"""

from __future__ import annotations

from app.crypto.qq_hash33 import hash33


def _js_reference(s: str) -> int:
    """
    复刻 JS 简化版（带 32 位 mask 在 (h << 5) 位置）作为参考实现。

    与生产实现 hash33() 在 qrsig 长度（≤ 30 字符 base64）下应当等价；
    本测试同时覆盖更长字符串以增加覆盖度。
    """
    h = 0
    for c in s:
        h += (h << 5) + ord(c)
    return h & 0x7FFFFFFF


def test_empty_string():
    assert hash33("") == 0


def test_single_char():
    # 'A' = 65，循环一次：h = 0 + (0 << 5) + 65 = 65
    assert hash33("A") == 65


def test_two_chars():
    # 'A' (65) -> h = 65
    # 'B' (66) -> h = 65 + (65 << 5) + 66 = 65 + 2080 + 66 = 2211
    assert hash33("AB") == 2211


def test_known_qrsig_like_strings():
    """随机几个 qrsig 风格字符串与参考实现对照。"""
    samples = [
        "abcdef",
        "QRsig_test_01",
        "Aa1Bb2Cc3Dd4Ee5",
        "0_xH4Vq7Tn9wEk",
        "CMTtRWTtAAuq3xRgEyJ_w-LR8XSijEDw**",
    ]
    for s in samples:
        assert hash33(s) == _js_reference(s)


def test_result_in_31bit_range():
    """所有结果必在 [0, 0x7fffffff] 范围内。"""
    for s in ["x", "x" * 50, "abc123", "🙂"]:
        h = hash33(s)
        assert 0 <= h <= 0x7FFFFFFF
