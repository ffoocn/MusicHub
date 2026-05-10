# 账号歌单 API

本文档只记录网易云音乐、QQ 音乐的官方/站内账号歌单接口，包括创建歌单、收藏歌单、我喜欢的歌曲等。接口通常需要登录 Cookie。

## 网易云音乐

### 账号信息

先取账号信息，得到 `userId`：

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
| `profile.nickname` | 昵称 |
| `profile.vipType` | 会员类型 |

### 我的歌单

```http
POST https://music.163.com/weapi/user/playlist
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <网易云登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

请求体是 `weapi` 加密表单。

明文参数：

```json
{
  "uid": 123456,
  "limit": 30,
  "offset": 0,
  "includeVideo": true,
  "csrf_token": "<Cookie 中的 __csrf；没有时可传空字符串>"
}
```

响应路径：

```text
playlist[]
```

字段映射：

| 上游字段 | 说明 |
| --- | --- |
| `id` | 歌单 ID |
| `name` | 歌单名 |
| `coverImgUrl` | 封面 |
| `trackCount` | 歌曲数量 |
| `playCount` | 播放量 |
| `description` | 描述 |
| `subscribed` | `false` 通常为自己创建，`true` 通常为收藏/订阅 |
| `creator.nickname` | 创建者昵称 |

实测结果：

```text
account: code=200, vipType=110
user playlists: code=200, count=6
subscribed=true count=4
```

### 每日个性化推荐歌单

```http
POST https://music.163.com/weapi/v1/discovery/recommend/resource
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <网易云登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

明文参数：

```json
{
  "csrf_token": "<Cookie 中的 __csrf；没有时可传空字符串>"
}
```

响应路径：

```text
recommend[]
```

实测结果：

```text
code=200, count=10
```

无登录 Cookie 时该接口会返回 `code=301`。

## QQ 音乐

### UIN 处理

账号歌单接口需要 `uin`。可从 Cookie 里的这些字段读取：

```text
uin
superuin
pt2gguin
p_uin
```

处理方式：

```text
o0000983993 -> 983993
```

即去掉开头的 `o` 和前导零。

### 我喜欢的歌曲

```http
GET https://c.y.qq.com/fav/fcgi-bin/fcg_get_profile_order_asset.fcg
Referer: https://y.qq.com/
Cookie: <QQ 音乐登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

查询参数：

| 参数 | 值 |
| --- | --- |
| `format` | `json` |
| `inCharset` | `utf8` |
| `outCharset` | `utf-8` |
| `platform` | `yqq.json` |
| `needNewCode` | `0` |
| `loginUin` | 当前账号 UIN |
| `hostUin` | `0` |
| `notice` | `0` |
| `g_tk` | `5381` |
| `ct` | `20` |
| `cid` | `205360956` |
| `userid` | 当前账号 UIN |
| `reqtype` | `1` |
| `sin` | 起始下标 |
| `ein` | 结束下标 |

响应字段：

| 字段 | 说明 |
| --- | --- |
| `code` | `0` 表示成功 |
| `data.totalsong` | 我喜欢歌曲总数 |
| `data.songlist[]` | 歌曲列表 |

实测结果：

```text
code=0, totalsong=2
```

### 创建的歌单

```http
GET https://c.y.qq.com/rsc/fcgi-bin/fcg_user_created_diss
Referer: https://y.qq.com/
Cookie: <QQ 音乐登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

查询参数：

| 参数 | 值 |
| --- | --- |
| `hostuin` | 当前账号 UIN |
| `sin` | 起始下标 |
| `size` | 返回数量 |
| `format` | `json` |
| `inCharset` | `utf8` |
| `outCharset` | `utf-8` |

响应路径：

```text
data.disslist[]
```

常见字段：

| 字段 | 说明 |
| --- | --- |
| `dissid` / `tid` | 普通歌单 ID |
| `dirid` | 目录型列表 ID，例如 QZone 背景音乐 |
| `diss_name` / `title` | 名称 |
| `diss_cover` / `cover` | 封面 |
| `song_cnt` / `song_num` / `song_count` | 歌曲数量 |
| `listen_num` / `visitnum` | 播放/访问量 |

实测结果：

```text
code=0, count=1
first item: dirid=205, name=QZone背景音乐
```

注意：只有 `dirid`、没有 `dissid` 的条目不是普通歌单详情，要走目录型列表取歌接口。

### 目录型列表取歌

```http
GET http://s.plcloud.music.qq.com/fcgi-bin/fcg_musiclist_getinfo.fcg
Referer: https://y.qq.com/w/myalbum.html
Cookie: <QQ 音乐登录 Cookie>
User-Agent: Mozilla/5.0 (iPhone...)
```

查询参数：

| 参数 | 值 |
| --- | --- |
| `uin` | 当前账号 UIN |
| `dirid` | 创建歌单接口返回的 `dirid` |
| `new` | `0` |
| `dirinfo` | `1` |
| `miniportal` | `1` |
| `fromDir2Diss` | `1` |
| `mobile` | `1` |
| `from` | `0` |
| `to` | 最大歌曲下标 |
| `format` | `json` |
| `g_tk` | `5381` |

实测结果：

```text
dirid=205, code=0, songCount=0
```

### 收藏的歌单

```http
GET https://c.y.qq.com/fav/fcgi-bin/fcg_get_profile_order_asset.fcg
Referer: https://y.qq.com/
Cookie: <QQ 音乐登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

查询参数与“我喜欢的歌曲”基本一致，但：

```text
reqtype=3
```

响应路径：

```text
data.cdlist[]
```

字段：

| 字段 | 说明 |
| --- | --- |
| `dissid` | 歌单 ID |
| `dissname` | 歌单名 |
| `songnum` | 歌曲数量 |
| `listennum` | 播放量 |
| `logo` | 封面 |
| `nickname` | 创建者昵称 |
| `uin` | 创建者 UIN |

实测结果：

```text
code=0, count=2
```

### 热门推荐歌单

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

响应路径：

```text
recomPlaylist.data.v_hot[]
```

实测结果：

```text
code=0, count=12
```
