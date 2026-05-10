# 歌单歌曲列表 API

本文只记录平台站内接口，用于“拿到歌单或账号歌单后，展开歌曲列表”。下载串联时建议流程：

1. 先通过推荐歌单、账号收藏歌单或搜索接口拿到歌单 ID。
2. 用本文接口展开歌单内歌曲列表。
3. 对每首歌再调用歌曲详情、歌词、封面和下载 URL 接口。

相关文档：

- 推荐/每日歌单：[daily-playlist-api.md](./daily-playlist-api.md)
- 账号收藏/创建歌单：[account-playlist-api.md](./account-playlist-api.md)
- 歌曲详情、封面、歌词、专辑：[media-metadata-api.md](./media-metadata-api.md)
- 下载 URL：[netease-download-api.md](./netease-download-api.md)、[qq-download-api.md](./qq-download-api.md)、[kuwo-download-api.md](./kuwo-download-api.md)

## 网易云音乐

### 1. 歌单详情

```text
POST https://music.163.com/weapi/v3/playlist/detail
Content-Type: application/x-www-form-urlencoded
Referer: https://music.163.com/
Cookie: <可选，私密歌单或账号相关歌单需要登录态>
```

请求体使用 `weapi` 加密后提交：

```json
{
  "id": "<playlist_id>",
  "n": 0,
  "csrf_token": ""
}
```

表单字段：

```text
params=<weapi_params>&encSecKey=<weapi_encSecKey>
```

关键返回：

```json
{
  "code": 200,
  "playlist": {
    "id": 123,
    "name": "歌单名",
    "coverImgUrl": "https://...",
    "description": "...",
    "playCount": 1000,
    "trackCount": 200,
    "creator": {
      "nickname": "创建者"
    },
    "trackIds": [
      { "id": 111 },
      { "id": 222 }
    ]
  }
}
```

这里重点使用 `playlist.trackIds[].id`。`n=0` 可以只拿完整 ID 列表，后续再批量取歌曲详情。

### 2. 批量歌曲详情

```text
POST https://music.163.com/weapi/v3/song/detail
Content-Type: application/x-www-form-urlencoded
Referer: https://music.163.com/
Cookie: <可选>
```

请求体使用 `weapi` 加密后提交：

```json
{
  "c": "[{\"id\":111},{\"id\":222}]",
  "ids": "[\"111\",\"222\"]"
}
```

建议批量大小：`500` 首以内一批。

关键返回：

```json
{
  "songs": [
    {
      "id": 111,
      "name": "歌曲名",
      "ar": [{ "id": 1, "name": "歌手" }],
      "al": {
        "id": 10,
        "name": "专辑名",
        "picUrl": "https://..."
      },
      "dt": 245000
    }
  ]
}
```

字段映射：

```text
song_id = songs[].id
song_name = songs[].name
artists = songs[].ar[].name
album_id = songs[].al.id
album_name = songs[].al.name
cover = songs[].al.picUrl
duration_ms = songs[].dt
```

## QQ 音乐

QQ 歌单分两类处理：

- 普通歌单：推荐歌单、搜索歌单、收藏的公开歌单，使用 `disstid`。
- 账号目录歌单：从个人资产接口返回的 `dirid`，例如“我喜欢/自建目录”一类，使用 `plcloud` 目录接口。

### 普通歌单详情

```text
GET https://i.y.qq.com/qzone-music/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg
```

备用域名：

```text
GET http://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg
```

Query 参数：

```text
type=1
json=1
utf8=1
onlysong=0
disstid=<playlist_id>
format=json
g_tk=5381
loginUin=0
hostUin=0
inCharset=utf8
outCharset=utf-8
notice=0
platform=yqq
needNewCode=0
```

Headers：

```text
Referer: https://y.qq.com/
User-Agent: Mozilla/5.0 ...
Cookie: <可选，私密/账号相关歌单需要登录态>
```

关键返回：

```json
{
  "code": 0,
  "subcode": 0,
  "cdlist": [
    {
      "dissname": "歌单名",
      "logo": "https://...",
      "nickname": "创建者",
      "desc": "...",
      "visitnum": 1000,
      "songnum": 50,
      "songlist": [
        {
          "songid": 123,
          "songmid": "003...",
          "songname": "歌曲名",
          "albumname": "专辑名",
          "albummid": "002...",
          "interval": 245,
          "size128": 1234567,
          "size320": 3456789,
          "sizeflac": 23456789,
          "pay": { "payplay": 1 },
          "singer": [{ "name": "歌手" }]
        }
      ]
    }
  ]
}
```

字段映射：

```text
playlist_name = cdlist[0].dissname
playlist_cover = cdlist[0].logo
song_id = cdlist[0].songlist[].songid
songmid = cdlist[0].songlist[].songmid
song_name = cdlist[0].songlist[].songname
artists = cdlist[0].songlist[].singer[].name
album_name = cdlist[0].songlist[].albumname
albummid = cdlist[0].songlist[].albummid
cover = https://y.gtimg.cn/music/photo_new/T002R300x300M000<albummid>.jpg
duration_sec = cdlist[0].songlist[].interval
pay_play = cdlist[0].songlist[].pay.payplay
```

下载接口需要 `songmid` 和文件前缀；歌词接口通常需要数字 `songid`。

### 账号目录歌单详情

用于账号歌单接口返回的 `profile:dir:<dirid>` 或等价 `dirid`。

```text
GET http://s.plcloud.music.qq.com/fcgi-bin/fcg_musiclist_getinfo.fcg
```

Query 参数：

```text
uin=<qq_uin>
dirid=<dirid>
new=0
dirinfo=1
miniportal=1
fromDir2Diss=1
mobile=1
from=0
to=500
format=json
g_tk=5381
```

Headers：

```text
Referer: https://y.qq.com/w/myalbum.html
User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148
Cookie: <必须，账号目录歌单依赖登录态>
```

关键返回：

```json
{
  "code": 0,
  "Title": "目录名",
  "NickName": "昵称",
  "PicUrl": "https://...",
  "Desc": "...",
  "DirID": 205,
  "SongCount": 20,
  "TotalSongNum": 20,
  "SongList": [
    {
      "songid": 123,
      "songmid": "003...",
      "songname": "歌曲名",
      "albummid": "002...",
      "albumname": "专辑名",
      "interval": 245,
      "singer": [{ "name": "歌手" }]
    }
  ]
}
```

分页说明：

```text
from=0&to=500
from=500&to=1000
```

实际实现时建议按 `SongCount` 或 `TotalSongNum` 判断是否继续翻页。

## 酷我音乐

### 歌单详情

```text
GET http://nplserver.kuwo.cn/pl.svc
```

Query 参数：

```text
op=getlistinfo
pid=<playlist_id>
pn=0
rn=100
encode=utf8
keyset=pl2012
identity=kuwo
pcmp4=1
vipver=1
newver=1
```

Headers：

```text
User-Agent: Mozilla/5.0 ...
Cookie: <可选>
```

关键返回：

```json
{
  "musiclist": [
    {
      "id": "123",
      "name": "歌曲名",
      "song_name": "歌曲名",
      "artist": "歌手",
      "artist_name": "歌手",
      "album": "专辑名",
      "albumpic": "img1.kuwo.cn/...",
      "duration": "245"
    }
  ]
}
```

字段映射：

```text
rid = musiclist[].id
song_name = musiclist[].name 或 musiclist[].song_name
artist = musiclist[].artist 或 musiclist[].artist_name
album_name = musiclist[].album
cover = musiclist[].albumpic
duration_sec = musiclist[].duration
song_link = http://www.kuwo.cn/play_detail/<rid>
```

封面处理：

```text
如果 albumpic 没有 http 前缀，补 http://
如果 URL 中有 _100.、_120.、_150.，可替换为 _500. 获取更大图
```

分页说明：

```text
pn=0&rn=100
pn=1&rn=100
```

不同歌单返回是否分页完整不稳定；下载器实现里建议：

- 第一页返回数量小于 `rn` 时停止。
- 若响应里有总数类字段，优先按总数判断。
- 对 `rid` 去重，避免不同页重复。

## 串联实现建议

统一中间结构建议至少保留：

```json
{
  "platform": "netease|qq|kuwo",
  "playlist_id": "...",
  "song_id": "...",
  "songmid": "...",
  "rid": "...",
  "name": "...",
  "artists": ["..."],
  "album_id": "...",
  "album_name": "...",
  "cover": "...",
  "duration": 245000,
  "pay_or_vip_hint": true
}
```

平台对应下载关键字段：

```text
网易：song_id
QQ：songmid；歌词可额外保留 song_id
酷我：rid
```

失败策略：

- 歌单详情失败：先重试 1-2 次，再标记整个歌单失败。
- 单首歌曲详情失败：跳过该歌曲，保留失败原因。
- 下载 URL 失败：按音质优先级降级重试。
- 账号相关歌单：遇到权限错误时刷新登录态或跳过，不要改用第三方解析。
