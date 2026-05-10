# 每日推荐歌单上游 API

本文档只记录网易云音乐、QQ 音乐、酷我音乐的官方/站内推荐歌单上游接口，不包含第三方解析或中转库。

## 统一结构建议

```json
{
  "id": "string",
  "name": "string",
  "cover": "string",
  "track_count": 0,
  "play_count": 0,
  "creator": "string",
  "description": "string",
  "source": "netease | qq | kuwo",
  "link": "string",
  "extra": {}
}
```

## 通用请求建议

- 设置浏览器 `User-Agent`，避免部分接口拒绝或返回异常数据。
- 可附加 `X-Forwarded-For`、`X-Real-IP` 为大陆 IP。
- 单个平台失败时不要让整体失败，记录错误后继续请求其他平台。

## 网易云音乐

网易云这里要先区分两个概念：

- 公开推荐歌单：首页/发现页风格的推荐歌单，免登录可用。
- 登录后的每日个性化推荐歌单：需要网易云 Cookie，无 Cookie 会返回 `code=301`。

如果你要严格意义上的“我的每日推荐歌单”，不要用公开推荐接口，要用下面的“登录后每日个性化推荐歌单”接口。

### 公开推荐歌单

#### 请求

```http
POST https://music.163.com/weapi/personalized/playlist
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0 ...
```

请求体不是明文 JSON，而是网易云 `weapi` 加密表单：

```text
params=<二次 AES-CBC 后的 base64 字符串>
encSecKey=<RSA 加密后的 secKey>
```

明文参数：

```json
{
  "limit": 30,
  "total": true,
  "n": 1000
}
```

实测结果：免登录可返回 `code=200` 和 30 个 `result[]` 歌单。

#### weapi 加密规则

常量：

```text
nonce = "0CoJUm6Qyw8W8jud"
iv = "0102030405060708"
pubKey = "010001"
modulus = "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7"
```

算法：

1. 生成 16 位随机 `secKey`，字符集可用 `a-zA-Z0-9`。
2. 用 `AES-128-CBC + PKCS#7 padding` 加密明文 JSON，key 为 `nonce`，iv 为上面的 `iv`，结果做 base64，得到 `first`.
3. 再用同样的 AES-CBC 加密 `first`，key 为随机 `secKey`，iv 不变，结果做 base64，得到 `params`.
4. 把 `secKey` 字符串反转，转 hex，大整数计算 `reversedSecKey^pubKey mod modulus`，左侧补零到 256 位 hex，得到 `encSecKey`.

#### 响应

成功响应顶层：

```json
{
  "code": 200,
  "result": []
}
```

`result[]` 关键字段：

| 上游字段 | 说明 | 归一化字段 |
| --- | --- | --- |
| `id` | 歌单 ID，数字 | `id`，转字符串 |
| `name` | 歌单名 | `name` |
| `picUrl` | 封面 | `cover` |
| `playCount` | 播放量，可能是浮点数 | `play_count`，转整数 |
| `trackCount` | 歌曲数 | `track_count` |
| `copywriter` | 推荐语 | `creator` 和 `description` |
| `alg` | 推荐算法标识 | `extra.alg` |

归一化补充：

```text
source = "netease"
creator = copywriter 非空时用 copywriter，否则用 "网易云推荐"
link = "https://music.163.com/#/playlist?id=" + id
```

### 登录后每日个性化推荐歌单

#### 请求

```http
POST https://music.163.com/weapi/v1/discovery/recommend/resource
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <网易云登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

请求体同样是 `weapi` 加密表单：

```text
params=<二次 AES-CBC 后的 base64 字符串>
encSecKey=<RSA 加密后的 secKey>
```

明文参数：

```json
{
  "csrf_token": "<从 Cookie 中的 __csrf 读取；没有可传空字符串>"
}
```

无登录 Cookie 时实测返回：

```json
{
  "code": 301
}
```

#### 响应

登录有效时，歌单列表通常在：

```text
recommend[]
```

常见字段映射：

| 上游字段 | 说明 | 归一化字段 |
| --- | --- | --- |
| `id` | 歌单 ID，数字 | `id`，转字符串 |
| `name` | 歌单名 | `name` |
| `picUrl` / `coverImgUrl` | 封面 | `cover` |
| `playcount` / `playCount` | 播放量 | `play_count` |
| `trackCount` | 歌曲数 | `track_count` |
| `creator.nickname` | 创建者 | `creator` |

归一化补充：

```text
source = "netease"
link = "https://music.163.com/#/playlist?id=" + id
```

## QQ 音乐

### 请求

```http
POST https://u.y.qq.com/cgi-bin/musicu.fcg
Referer: https://y.qq.com/
Content-Type: application/json
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

请求体：

```json
{
  "comm": {
    "ct": 24
  },
  "recomPlaylist": {
    "method": "get_hot_recommend",
    "module": "playlist.HotRecommendServer",
    "param": {
      "async": 1,
      "cmd": 2
    }
  }
}
```

### 响应

成功响应顶层：

```json
{
  "code": 0,
  "recomPlaylist": {
    "data": {
      "v_hot": []
    }
  }
}
```

歌单列表路径：

```text
recomPlaylist.data.v_hot
```

`v_hot[]` 关键字段：

| 上游字段 | 说明 | 归一化字段 |
| --- | --- | --- |
| `content_id` | 歌单 ID，数字 | `id`，转字符串 |
| `title` | 歌单名 | `name` |
| `cover` | 封面 | `cover` |
| `listen_num` | 播放量 | `play_count` |
| `song_cnt` | 歌曲数 | `track_count` |
| `song_count` | 歌曲数备用字段 | `track_count` |
| `username` | 创建者，可能为空 | `creator` |

归一化补充：

```text
source = "qq"
cover = 如果以 "http://" 开头，替换为 "https://"
track_count = song_cnt 非 0 时优先，否则用 song_count
description = ""
link = "https://y.qq.com/n/ryqq/playlist/" + content_id
```

## 酷我音乐

### 请求

```http
GET http://wapi.kuwo.cn/api/pc/classify/playlist/getRcmPlayList?pn=0&rn=30&order=hot
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

固定查询参数：

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `pn` | `0` | 页码，从 0 开始 |
| `rn` | `30` | 返回数量 |
| `order` | `hot` | 热门排序 |

### 响应

成功响应顶层：

```json
{
  "code": 200,
  "data": {
    "data": []
  }
}
```

歌单列表路径：

```text
data.data
```

`data.data[]` 关键字段：

| 上游字段 | 说明 | 归一化字段 |
| --- | --- | --- |
| `id` | 歌单 ID，字符串 | `id` |
| `name` | 歌单名 | `name` |
| `img` | 封面 | `cover` |
| `listencnt` | 播放量，可能是数字或字符串 | `play_count` |
| `songnum` | 歌曲数，可能是数字或字符串 | `track_count` |
| `total` | 歌曲数备用字段 | `track_count` |
| `count` | 歌曲数备用字段 | `track_count` |
| `musicnum` | 歌曲数备用字段 | `track_count` |
| `uname` | 创建者 | `creator` |
| `desc` | 描述 | `description` |

归一化补充：

```text
source = "kuwo"
cover = img 非空且不是 http 开头时，补 "http://"
track_count = 依次尝试 songnum、total、count、musicnum
link = "http://www.kuwo.cn/playlist_detail/" + id
```

## 聚合策略

只请求这三个来源：

```text
netease
qq
kuwo
```

聚合时建议：

1. 三个平台并发请求。
2. 每个平台单独超时、单独捕获错误。
3. 响应码不符合预期时丢弃该平台数据，例如网易云 `code != 200`、QQ `code != 0`、酷我 `code != 200`。
4. 每条记录都补上 `source`，后续请求歌单详情时需要靠 `source + id` 判断平台。
5. QQ 和酷我的歌曲数、播放量字段不稳定，要按上面的备用字段顺序兼容。
