"""
QQ 扫码登录 ptqrtoken hash33 算法。

参考文档：docs/qq-music-qr-login-api.md

JavaScript 原版：

```javascript
function hash33(s) {
    let h = 0;
    for (const c of s) {
        h += (h << 5) + c.charCodeAt(0);
    }
    return h & 0x7fffffff;
}
```

实现说明：
- 文档中给定的 Python 版本与 JS 在 qrsig 长度（通常 ≤30 字符的 base64）下结果一致，
  因为 `(h << 5)` 在每一步累加值有限，最终 `& 0x7fffffff` 截断到 31 位无符号。
- 与 JS 直接对照，无需额外的 32 位 mask。
"""

from __future__ import annotations


def hash33(s: str, h: int = 0) -> int:
    """计算 hash33。

    用途：
        - 计算 ptqrtoken：`hash33(qrsig)` （初始值 h=0）
        - 计算 g_tk：`hash33(p_skey, 5381)` 或 `hash33(musickey, 5381)`

    Args:
        s: 输入字符串。
        h: 初始哈希值（默认 0；计算 g_tk 时传 5381）。

    Returns:
        31 位无符号整数（范围 0..0x7fffffff）。

    Notes:
        与 QQMusicApi 项目兼容。`(h << 5) + h` 等价于 `h * 33`，
        所以原写法 `h += (h << 5) + ord(c)` ≡ `h = (h << 5) + h + ord(c)`，
        两种等价，QQMusicApi 用后者更直观。
    """
    for c in s:
        h = (h << 5) + h + ord(c)
    return h & 0x7FFFFFFF
