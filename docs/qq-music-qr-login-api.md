# QQ 音乐扫码登录 API 文档

---

## 一、QQ 扫码登录

### 第一步：获取 QR 码

```
GET https://ssl.ptlogin2.qq.com/ptqrshow
```

**Query 参数：**

| 参数 | 值 |
|------|----|
| `appid` | `716027609` |
| `e` | `2` |
| `l` | `M` |
| `s` | `3` |
| `d` | `72` |
| `v` | `4` |
| `t` | 随机小数，通常用 `Math.random()` 风格，如 `0.12345678901234567` |
| `daid` | `383` |
| `pt_3rd_aid` | `100497308` |

**Headers：**

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Referer: https://y.qq.com/
```

**响应：**

- 响应体：PNG 二进制图片，直接展示即可
- 从响应头 `Set-Cookie` 中提取 `qrsig` 保存，后续步骤使用

---

### 第二步：轮询扫码状态

```
GET https://ssl.ptlogin2.qq.com/ptqrlogin
```

**Query 参数：**

| 参数 | 值 |
|------|----|
| `u1` | `https://graph.qq.com/oauth2.0/login_jump` |
| `ptqrtoken` | `hash33(qrsig)`，见下方算法 |
| `ptredirect` | `100` |
| `h` | `1` |
| `t` | `1` |
| `g` | `1` |
| `from_ui` | `1` |
| `ptlang` | `2052` |
| `action` | `0-0-<当前时间戳毫秒>` |
| `js_ver` | `21072115` |
| `js_type` | `1` |
| `login_sig` | （空） |
| `pt_uistyle` | `40` |
| `aid` | `716027609` |
| `daid` | `383` |
| `pt_3rd_aid` | `100497308` |
| `has_onekey` | `1` |
| `pttype` | `1` |
| `service` | `ptqrlogin` |
| `nodirect` | `0` |

**Headers：**

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Referer: https://xui.ptlogin2.qq.com/
Cookie: qrsig=<第一步获取的 qrsig>
```

**ptqrtoken 的 hash33 算法：**

```python
def hash33(s: str) -> int:
    h = 0
    for c in s:
        h += (h << 5) + ord(c)
    return h & 0x7fffffff
```

```javascript
function hash33(s) {
    let h = 0;
    for (const c of s) {
        h += (h << 5) + c.charCodeAt(0);
    }
    return h & 0x7fffffff;
}
```

**响应格式：**

JS 字符串，用正则 `'([^']*)'` 提取字段数组。字段数量可能随页面版本变化，常见成功响应有 6 个字段：

- `[0]` = 状态码
- `[2]` = redirectURL（成功时用于跟随重定向拿 Cookie）
- `[4]` = 消息文本

示例：
```
ptuiCB('0','0','https://...redirect_url...','0','登录成功！','昵称')
```

**状态码说明：**

| 状态码 | 含义 |
|--------|------|
| `0` | 登录成功，需跟随 redirectURL 获取 Cookie |
| `65` | 二维码已过期 |
| `66` | 等待扫码 |
| `67` | 已扫码，等待用户确认 |

**成功后处理：**

跟随 redirectURL 进行最多 8 次重定向，从每次响应头收集所有 `Set-Cookie`。

这个阶段通常先得到 QQ 登录态 Cookie，例如 `uin`、`p_skey`、`ptcz`、`RK` 等。是否能直接得到 QQ 音乐可用 Cookie 取决于重定向链是否完成 QQ 音乐侧授权。

QQ 音乐后续下载/账号接口真正需要的关键字段通常是：`uin`、`qqmusic_key`、`qm_keyst`、`superkey`、`superuin`。如果重定向后没有这些字段，需要继续走 QQ 音乐授权或换票流程，不能只拿 QQ 基础登录态当作 QQ 音乐登录态使用。

---

## 二、微信扫码登录（QQ 音乐绑定微信）

### 第一步：获取微信 QR 页面（取 uuid）

```
GET https://open.weixin.qq.com/connect/qrconnect
```

**Query 参数：**

| 参数 | 值 |
|------|----|
| `appid` | `wx48db31d50e334801` |
| `redirect_uri` | `https://y.qq.com/portal/wx_redirect.html?login_type=2&surl=https://y.qq.com/` |
| `response_type` | `code` |
| `scope` | `snsapi_login` |
| `state` | 随机字符串，防 CSRF，例如 `qqmusic-<random>` |
| `href` | `https://y.qq.com/mediastyle/music_v17/src/css/popup_wechat.css#wechat_redirect` |

**Headers：**

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Referer: https://y.qq.com/
```

**响应处理：**

响应是 HTML，用正则从中提取 uuid：

```
connect/l/qrconnect\?uuid=([A-Za-z0-9_-]+)
```

QR 码图片 URL 直接拼接：

```
https://open.weixin.qq.com/connect/qrcode/<uuid>
```

---

### 第二步：轮询微信扫码状态

```
GET https://lp.open.weixin.qq.com/connect/l/qrconnect
```

**Query 参数：**

| 参数 | 值 |
|------|----|
| `uuid` | 第一步提取的 uuid |
| `_` | 当前时间戳毫秒 |

**Headers：**

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Referer: https://open.weixin.qq.com/connect/qrconnect
```

**响应格式：**

JS 赋值字符串，解析两个变量：

```javascript
wx_errcode = '405';
wx_code = 'xxxxxx';
```

**状态码说明：**

| 状态码 | 含义 |
|--------|------|
| `405` | 登录成功，`wx_code` 有值，进入第三步 |
| `402` | 二维码已过期 |
| `404` | 已扫码，等待用户确认 |
| `408` | 等待扫码 |

---

### 第三步：用 wx_code 换取 QQ 音乐 Cookie

```
POST https://u.y.qq.com/cgi-bin/musicu.fcg
```

失败时依次重试：
- `https://szu.y.qq.com/cgi-bin/musicu.fcg`
- `https://shu.y.qq.com/cgi-bin/musicu.fcg`

**Headers：**

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Referer: https://y.qq.com/portal/wx_redirect.html?login_type=2&surl=https://y.qq.com/
Origin: https://y.qq.com
Content-Type: application/json
Cookie: login_type=2
```

**Body（JSON）：**

```json
{
  "comm": {
    "tmeAppID": "qqmusic",
    "tmeLoginType": "1",
    "g_tk": 5381,
    "platform": "yqq",
    "ct": 24,
    "cv": 0
  },
  "req": {
    "module": "music.login.LoginServer",
    "method": "Login",
    "param": {
      "strAppid": "wx48db31d50e334801",
      "code": "<wx_code>"
    }
  }
}
```

**响应字段映射（从 `req.data` 提取）：**

| 响应字段 | Cookie 名 |
|----------|-----------|
| `musicid` | `musicid` |
| `musickey` / `qqmusic_key` | `qqmusic_key`、`qm_keyst` |
| `openid` / `wxopenid` | `wxopenid` |
| `unionid` / `wxunionid` | `wxunionid` |
| `refresh_key` | `refresh_key` |
| `refresh_token` | `refresh_token` |
| `access_token` / `wxaccess_token` | `wxaccess_token` |

**成功判断：** 外层 `code == 0` 且 `req.code == 0`
