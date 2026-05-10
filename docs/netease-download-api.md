# 网易云音乐下载 API

本文档只记录网易云音乐官方/站内下载接口。高音质下载通常需要登录 Cookie，部分歌曲还需要账号具备 VIP 权限。

## 结论

优先使用 `eapi` 高音质接口：

```http
POST https://interface3.music.163.com/eapi/song/enhance/player/url/v1
```

可作为兜底的普通 `weapi` 接口：

```http
POST http://music.163.com/weapi/song/enhance/player/url
```

建议策略：

1. 登录态存在时优先请求 `eapi`。
2. 按 `lossless -> hires -> exhigh -> standard` 或业务指定音质依次尝试。
3. `eapi` 无 URL 时再兜底 `weapi`。
4. 返回 URL 后再单独下载音频文件。

## 登录态与 VIP 判断

### 账号信息接口

```http
POST https://music.163.com/weapi/nuser/account/get
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <网易云登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

请求体是 `weapi` 加密表单：

```text
params=<encrypted>
encSecKey=<encrypted>
```

明文参数：

```json
{
  "csrf_token": "<Cookie 中的 __csrf；没有时可传空字符串>"
}
```

响应字段：

| 字段 | 说明 |
| --- | --- |
| `code` | `200` 表示成功 |
| `profile.userId` | 用户 ID |
| `profile.vipType` | 非 `0` 通常表示账号具备会员身份 |

## eapi 高音质下载接口

### 请求

```http
POST https://interface3.music.163.com/eapi/song/enhance/player/url/v1
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <网易云登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

请求体：

```text
params=<eapi encrypted hex>
```

明文 payload：

```json
{
  "ids": [3344811140],
  "level": "exhigh",
  "encodeType": "flac",
  "header": "{\"os\":\"pc\",\"appver\":\"\",\"osver\":\"\",\"deviceId\":\"pyncm!\",\"requestId\":\"12345678\"}"
}
```

参数说明：

| 字段 | 说明 |
| --- | --- |
| `ids` | 歌曲 ID 数组，元素为数字 |
| `level` | 目标音质，见下表 |
| `encodeType` | 通常传 `flac`；服务端会按实际可用格式返回 |
| `header` | JSON 字符串，不是对象 |

常用 `level`：

| level | 预期音质 |
| --- | --- |
| `standard` | 标准音质，常见 128k MP3 |
| `exhigh` | 极高音质，常见 320k MP3 |
| `lossless` | 无损，常见 FLAC |
| `hires` | Hi-Res；不可用时可能降级到 `lossless` |

### eapi 加密规则

接口路径：

```text
/eapi/song/enhance/player/url/v1
```

签名时先把路径中的 `/eapi/` 替换为 `/api/`：

```text
/api/song/enhance/player/url/v1
```

常量：

```text
salt = "36cd479b6b5"
key = "e82ckenh8dichen8"
```

算法：

1. `payload` 是明文 JSON 字符串。
2. 计算 MD5：

```text
md5("nobody" + apiPath + "use" + payload + "md5forencrypt")
```

3. 拼接待加密文本：

```text
apiPath + "-36cd479b6b5-" + payload + "-36cd479b6b5-" + md5
```

4. 使用 `AES-128-ECB + PKCS#7 padding` 加密，key 为 `e82ckenh8dichen8`。
5. 加密结果转小写 hex，作为表单字段 `params`。

### 响应

成功响应结构：

```json
{
  "code": 200,
  "data": [
    {
      "id": 3344811140,
      "url": "https://...",
      "br": 320000,
      "size": 3458925,
      "md5": "...",
      "code": 200,
      "type": "mp3",
      "level": "exhigh",
      "fee": 8
    }
  ]
}
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `data[0].code` | 单曲状态，`200` 表示拿到播放/下载 URL |
| `data[0].url` | 真实音频 URL |
| `data[0].br` | 实际码率 |
| `data[0].size` | 文件大小 |
| `data[0].type` | 实际格式，如 `mp3`、`flac` |
| `data[0].level` | 实际返回音质，可能低于请求音质 |
| `data[0].fee` | 版权/付费标识 |

处理规则：

- `url` 为空时视为该音质失败，继续尝试下一档。
- `level` 可能降级，例如请求 `hires` 返回 `lossless`。
- 下载扩展名以 `type` 为准。
- 返回的音频 URL 有时效性，建议获取后立即下载。

## weapi 普通下载接口

### 请求

```http
POST http://music.163.com/weapi/song/enhance/player/url
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <可选；登录后成功率更高>
User-Agent: Mozilla/5.0 ...
```

请求体：

```text
params=<weapi params>
encSecKey=<weapi encSecKey>
```

明文参数：

```json
{
  "ids": ["3344811140"],
  "br": 320000
}
```

`br` 常见值：

| br | 说明 |
| --- | --- |
| `128000` | 128k |
| `192000` | 192k |
| `320000` | 320k |

### weapi 加密规则

常量：

```text
nonce = "0CoJUm6Qyw8W8jud"
iv = "0102030405060708"
pubKey = "010001"
modulus = "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7"
```

算法：

1. 生成 16 位随机 `secKey`，字符集可用 `a-zA-Z0-9`。
2. 用 `AES-128-CBC + PKCS#7 padding` 加密明文 JSON，key 为 `nonce`，iv 为上面的 `iv`，结果 base64，得到 `first`。
3. 再用 AES-CBC 加密 `first`，key 为随机 `secKey`，iv 不变，结果 base64，得到 `params`。
4. 把 `secKey` 反转，转 hex，大整数计算 `reversedSecKey^pubKey mod modulus`，左侧补零到 256 位 hex，得到 `encSecKey`。

### 响应

```json
{
  "code": 200,
  "data": [
    {
      "id": 3344811140,
      "url": "http://...",
      "br": 320000,
      "code": 200
    }
  ]
}
```

处理规则：

- `data[0].url` 为空时表示该接口未拿到可用地址。
- 对 VIP/高音质歌曲，优先使用 `eapi`，`weapi` 更适合作为普通音质兜底。

## 实测记录

测试歌曲：

```text
id = 3344811140
```

账号接口返回：

```text
code = 200
profile.vipType = 110
```

`eapi` 下载接口返回：

| 请求 level | data.code | 是否有 URL | 实际 level | type | br |
| --- | --- | --- | --- | --- | --- |
| `hires` | `200` | 是 | `lossless` | `flac` | `822223` |
| `lossless` | `200` | 是 | `lossless` | `flac` | `822223` |
| `exhigh` | `200` | 是 | `exhigh` | `mp3` | `320000` |
| `standard` | `200` | 是 | `standard` | `mp3` | `128000` |

注意：接口返回的 CDN URL 可能带时间和访问限制。文档关注的是官方拿 URL 的接口和解析规则，下载端仍需处理 URL 过期、403、重试和重新取 URL。
