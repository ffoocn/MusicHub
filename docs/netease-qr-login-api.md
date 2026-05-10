# 网易云音乐扫码登录 API 文档

---

## 加密说明（weapi 通用）

网易云所有 weapi 接口的请求体均需加密，流程如下：

### 加密常量（固定值）

```
AES 第一层密钥：  0CoJUm6Qyw8W8jud
AES 初始向量：    0102030405060708
RSA 模数 n：      00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7
RSA 公钥指数 e：  010001
```

### 加密流程

每次请求生成一个随机 16 位字符串作为 `randomKey`：

```
randomKey 字符集：abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789
```

**生成 `params`（双层 AES-128-CBC）：**

```
text      = JSON.stringify(请求数据)
step1     = AES_CBC_Base64(text,  key=AES_KEY_1,  iv=AES_IV)
step2     = AES_CBC_Base64(step1, key=randomKey,  iv=AES_IV)
params    = step2
```

**生成 `encSecKey`（RSA 加密随机密钥）：**

```
reversed  = randomKey 字符串反转
encSecKey = RSA(reversed, e=RSA_EXPONENT, n=RSA_MODULUS)
            结果补零至 256 个十六进制字符
```

**最终 Body 格式（application/x-www-form-urlencoded）：**

```
params=<第二层 AES 的 base64 结果>&encSecKey=<RSA 加密结果>
```

注意：`params` 本身不要手动重复 URL 编码；最终交给 `application/x-www-form-urlencoded` 表单编码即可。

---

## 通用 Headers

```
Content-Type: application/x-www-form-urlencoded
Referer: http://music.163.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

---

## 第一步：获取 QR 码 key

```
POST https://music.163.com/weapi/login/qrcode/unikey?csrf_token=
```

**明文请求数据（加密前）：**

```json
{"type": "1"}
```

**响应：**

```json
{
  "code": 200,
  "unikey": "aca65293-5459-40ed-899d-7c597a613d52"
}
```

---

## 第二步：生成二维码

无需请求网络，直接用 `unikey` 拼接二维码内容：

```
https://music.163.com/login?codekey=<unikey>
```

将这个 URL 用任意 QR 码库渲染成图片展示给用户扫描。

---

## 第三步：轮询扫码状态

```
POST https://music.163.com/weapi/login/qrcode/client/login?csrf_token=
```

**明文请求数据（加密前）：**

```json
{"type": "1", "unikey": "<第一步获取的 unikey>"}
```

**每次轮询需重新生成 randomKey**，建议间隔 **3 秒**。

**状态码说明：**

| code | 含义 |
|------|------|
| `800` | 二维码已过期 |
| `801` | 等待扫码 |
| `802` | 已扫码，等待用户确认 |
| `803` | 登录成功，响应头含 Cookie |

**code=803 时的响应示例：**

```json
{
  "code": 803,
  "message": "授权登陆成功",
  "cookie": "MUSIC_U=xxx; __csrf=xxx; NMTID=xxx; ..."
}
```

---

## Cookie 提取

登录成功（code=803）后，Cookie 来源：

1. **响应体** `cookie` 字段（字符串，分号分隔）
2. **响应头** `Set-Cookie`（多条）

关键字段：

| Cookie 名 | 说明 |
|-----------|------|
| `MUSIC_U` | 用户身份凭证，最重要 |
| `__csrf` | CSRF 防护令牌，后续请求需附带 |
| `NMTID` | 客户端标识 |
| `MUSIC_R_U` | 刷新登录态时可能出现 |
| `MUSIC_A_T` / `MUSIC_R_T` | 部分登录响应或刷新链路可能出现 |

**验证 Cookie 是否有效：**

```
POST https://music.163.com/weapi/w/nuser/account/get?csrf_token=<__csrf值>
Cookie: MUSIC_U=<值>; __csrf=<值>
```

明文请求数据：`{"csrf_token": "<__csrf值>"}`

响应 `code: 200` 则有效。
