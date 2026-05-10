# 酷我音乐下载 API

本文档只记录酷我官方/站内可直接请求的下载链路。第三方解析 API、聚合解析站、外部代理解析不纳入。

## 结论

可用下载主接口：

```http
GET https://mobi.kuwo.cn/mobi.s
```

能力：

- 免登录可返回部分歌曲的直链。
- 可带酷我 Cookie 走登录态；接口本身只需要把 Cookie 透传到请求头。
- 返回的是真实音频 URL，拿到后可直接下载。
- `128kmp3`、`320kmp3`、`2000kflac` 实测可得到普通音频文件。
- `flac` 参数可能返回 `mgg`，不是普通 FLAC，若不准备处理酷我加密/封装格式，建议跳过。

备用网页版接口：

```http
GET http://www.kuwo.cn/api/v1/www/music/playUrl
```

这个接口需要网页版动态 `Secret`。拿到正确 `Secret` 后也可能对付费内容返回无 URL，因此只能作为备用，不建议作为主下载链路。

## 需要的歌曲 ID

酷我下载使用 `rid`。常见来源：

### 搜索接口

```http
GET http://www.kuwo.cn/search/searchMusicBykeyWord
```

查询参数：

| 参数 | 值 |
| --- | --- |
| `vipver` | `1` |
| `client` | `kt` |
| `ft` | `music` |
| `cluster` | `0` |
| `strategy` | `2012` |
| `encoding` | `utf8` |
| `rformat` | `json` |
| `mobi` | `1` |
| `issubtitle` | `1` |
| `show_copyright_off` | `1` |
| `pn` | `0` |
| `rn` | `10` |
| `all` | 搜索关键词 |

响应位置：

```text
abslist[]
```

字段：

| 字段 | 说明 |
| --- | --- |
| `MUSICRID` | 形如 `MUSIC_228908`，下载时去掉 `MUSIC_` 得到 `rid` |
| `SONGNAME` | 歌名 |
| `ARTIST` | 歌手 |
| `ALBUM` | 专辑 |
| `DURATION` | 秒数 |
| `MINFO` | 可用音质和文件大小信息 |
| `PAY` | 付费/权限信息，主下载接口不直接依赖它 |
| `bitSwitch` | 为 `0` 时通常表示不可用，建议过滤 |

### 歌曲页链接

如果已有链接：

```text
http://www.kuwo.cn/play_detail/<rid>
```

直接提取 `play_detail/` 后面的数字作为 `rid`。

### 歌曲信息接口

只拿元信息时可请求：

```http
GET http://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId=<rid>&httpsStatus=1
```

常用字段：

```text
data.songinfo.songName
data.songinfo.artist
data.songinfo.pic
```

## 主下载接口

### 请求

```http
GET https://mobi.kuwo.cn/mobi.s?f=web&source=kwplayercar_ar_6.0.0.9_B_jiakong_vh.apk&from=PC&type=convert_url_with_sign&br=<br>&rid=<rid>&user=<user>
User-Agent: Mozilla/5.0 ...
Cookie: <可选，登录态 Cookie>
```

查询参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `f` | 是 | 固定 `web` |
| `source` | 是 | 固定 `kwplayercar_ar_6.0.0.9_B_jiakong_vh.apk` |
| `from` | 是 | 固定 `PC` |
| `type` | 是 | 固定 `convert_url_with_sign` |
| `br` | 是 | 音质参数，见下表 |
| `rid` | 是 | 酷我歌曲 ID，不带 `MUSIC_` 前缀 |
| `user` | 是 | 任意客户端用户标识，可用 `C_APK_guanwang_<timestamp><random>` |

音质参数：

| `br` | 预期结果 | 建议 |
| --- | --- | --- |
| `128kmp3` | 128 kbps MP3 | 可用，兼容性最好 |
| `320kmp3` | 320 kbps MP3 | 推荐优先尝试 |
| `flac` | 可能返回 `format=mgg` | 不建议当普通 FLAC 使用 |
| `2000kflac` | 普通 FLAC | 需要无损时优先尝试 |

推荐尝试顺序：

```text
2000kflac -> 320kmp3 -> 128kmp3
```

如果你只需要最大成功率：

```text
320kmp3 -> 128kmp3
```

### 响应

成功响应示例结构：

```json
{
  "code": 200,
  "data": {
    "url": "http://...",
    "bitrate": 320,
    "format": "mp3"
  },
  "msg": "success"
}
```

字段：

| 字段 | 说明 |
| --- | --- |
| `code` | 成功通常是 `200` |
| `data.url` | 真实音频下载地址 |
| `data.bitrate` | 实际码率 |
| `data.format` | 实际格式，例如 `mp3`、`flac`、`mgg` |

处理规则：

1. `data.url` 为空时视为失败，换下一个 `br`。
2. 如果 `br=flac` 返回 `format=mgg`，且业务只接受普通音频，应跳过。
3. 拿到 `data.url` 后再发起文件下载；建议支持重定向、Range、超时。
4. 下载文件扩展名以 `data.format` 为准；`format=mgg` 不要命名成 `.flac`。

## 登录态

主接口支持透传 Cookie：

```http
Cookie: <酷我登录 Cookie>
```

实现上无需额外签名。免登录请求和登录请求的 URL、参数相同，只是请求头多了 Cookie。是否能拿到高音质或付费内容取决于 Cookie 对应账号权限和酷我服务端策略。

## 备用网页版接口

### 请求

```http
GET http://www.kuwo.cn/api/v1/www/music/playUrl?mid=<rid>&type=music&httpsStatus=1&reqId=<uuid>&plat=web_www&from=
User-Agent: Mozilla/5.0 ...
Referer: http://www.kuwo.cn/play_detail/<rid>
Cookie: Hm_Iuvt_cdb524f42f23cer9b268564v7y735ewrq2324=<value>; <可选登录 Cookie>
Secret: <由 Cookie 动态生成>
```

重要：`Secret` 不是固定字符串。网页版前端会读取 Cookie：

```text
Hm_Iuvt_cdb524f42f23cer9b268564v7y735ewrq2324
```

然后用该 Cookie 值和 Cookie 名动态计算 `Secret`。

### Secret 算法

伪代码：

```js
function makeSecret(cookieValue, cookieName) {
  let n = ""
  for (let i = 0; i < cookieName.length; i++) {
    n += cookieName.charCodeAt(i).toString()
  }

  const o = Math.floor(n.length / 5)
  const r = parseInt(n.charAt(o) + n.charAt(2 * o) + n.charAt(3 * o) + n.charAt(4 * o) + n.charAt(5 * o))
  const c = Math.ceil(cookieName.length / 2)
  const l = Math.pow(2, 31) - 1
  if (r < 2) return null

  let d = Math.round(1e9 * Math.random()) % 1e8
  n += d
  while (n.length > 10) {
    n = (parseInt(n.substring(0, 10)) + parseInt(n.substring(10))).toString()
  }
  n = (r * n + c) % l

  let h = ""
  for (let i = 0; i < cookieValue.length; i++) {
    const f = parseInt(cookieValue.charCodeAt(i) ^ Math.floor((n / l) * 255))
    h += f < 16 ? "0" + f.toString(16) : f.toString(16)
    n = (r * n + c) % l
  }

  d = d.toString(16)
  while (d.length < 8) d = "0" + d
  return h + d
}
```

### 响应

成功时通常返回：

```json
{
  "code": 200,
  "data": {
    "url": "http://..."
  }
}
```

限制：

- 没有动态 `Secret` 会返回 `The request is illegal!`。
- 即使 `Secret` 正确，也可能返回 `code=-1` 和“该歌曲为付费内容，请下载酷我音乐客户端后付费收听”。
- 该接口无法选择 `br`，不如 `mobi.s` 主接口稳定。

## 实测记录

测试歌曲：

```text
周杰伦 - 晴天
rid = 228908
```

主接口实测：

| `br` | `data.bitrate` | `data.format` | 文件探测 |
| --- | --- | --- | --- |
| `128kmp3` | `128` | `mp3` | HTTP 206，`audio/mpeg` |
| `320kmp3` | `320` | `mp3` | HTTP 206，`audio/mpeg` |
| `flac` | `22000` | `mgg` | HTTP 206，`application/octet-stream` |
| `2000kflac` | `2000` | `flac` | HTTP 206，`audio/x-flac` |

备用网页版接口：

- 无 `Secret`：返回 `The request is illegal!`
- 动态 `Secret` 正确：该测试歌曲返回 `code=-1`，提示付费内容，无下载 URL

## 最小实现流程

1. 搜索或解析歌曲链接，得到 `rid`。
2. 如果需要元信息，请求 `newh5/singles/songinfoandlrc`。
3. 依次请求 `mobi.s` 主下载接口的目标音质。
4. 跳过空 URL、错误 code、`format=mgg`。
5. 拿到 `data.url` 后直接下载音频。
6. 如果有酷我登录 Cookie，就原样透传到搜索、元信息、下载接口请求头。
