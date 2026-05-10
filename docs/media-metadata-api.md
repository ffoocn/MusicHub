# 歌曲信息、封面、歌词、专辑 API

本文档只记录网易云音乐、QQ 音乐、酷我音乐的官方/站内接口，覆盖歌曲信息、封面、歌词、专辑搜索与专辑详情。

## 通用结构建议

歌曲：

```json
{
  "id": "string",
  "name": "string",
  "artist": "string",
  "album": "string",
  "album_id": "string",
  "duration": 0,
  "cover": "string",
  "source": "netease | qq | kuwo",
  "link": "string",
  "extra": {}
}
```

专辑：

```json
{
  "id": "string",
  "name": "string",
  "cover": "string",
  "track_count": 0,
  "creator": "string",
  "description": "string",
  "source": "netease | qq | kuwo",
  "link": "string",
  "extra": {}
}
```

## 网易云音乐

网易接口多数使用 `weapi` 加密。`weapi` 加密规则见 [daily-playlist-api.md](./daily-playlist-api.md) 或 [netease-download-api.md](./netease-download-api.md)。

### 歌曲详情

```http
POST https://music.163.com/weapi/v3/song/detail
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

明文参数：

```json
{
  "c": "[{\"id\":\"3344811140\"}]",
  "ids": "[\"3344811140\"]"
}
```

响应路径：

```text
songs[]
```

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 歌曲 ID |
| `name` | 歌曲名 |
| `ar[].name` | 歌手 |
| `al.name` | 专辑名 |
| `al.id` | 专辑 ID |
| `al.picUrl` | 封面 |
| `dt` | 时长，毫秒 |

### 封面

歌曲详情、专辑详情、歌单详情都会返回封面 URL：

```text
songs[].al.picUrl
album.picUrl
playlist.coverImgUrl
```

网易封面 URL 可直接 GET。需要不同尺寸时，可在已有图片 URL 后追加参数：

```text
?param=300y300
?param=500y500
?param=1000y1000
```

### 歌词

```http
POST https://music.163.com/weapi/song/lyric
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

明文参数：

```json
{
  "csrf_token": "",
  "id": "3344811140",
  "lv": -1,
  "tv": -1,
  "rv": -1,
  "yv": -1
}
```

字段：

| 字段 | 说明 |
| --- | --- |
| `code` | `200` 表示成功 |
| `lrc.lyric` | 普通 LRC 歌词 |
| `yrc.lyric` | 逐字歌词 |
| `tlyric.lyric` | 翻译歌词 |
| `romalrc.lyric` | 罗马音歌词 |

实测：

```text
code=200, lrc.lyric 非空
```

### 专辑搜索

```http
POST http://music.163.com/api/linux/forward
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

表单字段：

```text
eparams=<linux api encrypted hex>
```

明文结构：

```json
{
  "url": "http://music.163.com/api/cloudsearch/pc",
  "params": {
    "s": "周杰伦 晴天",
    "type": 10,
    "offset": 0,
    "limit": 10
  }
}
```

`type=10` 表示专辑搜索。

Linux API 加密：

```text
AES-128-ECB + PKCS#7 padding
key(hex) = 7246674226682325323F5E6544673A51
输出大写 hex
```

响应路径：

```text
result.albums[]
```

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 专辑 ID |
| `name` | 专辑名 |
| `picUrl` | 封面 |
| `size` | 歌曲数量 |
| `company` | 发行公司 |
| `description` / `briefDesc` | 描述 |
| `publishTime` | 发布时间戳 |
| `artist.name` / `artists[].name` | 歌手 |

### 专辑详情与歌曲

```http
POST https://music.163.com/weapi/v1/album/<album_id>
Referer: http://music.163.com/
Content-Type: application/x-www-form-urlencoded
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

明文参数：

```json
{
  "csrf_token": ""
}
```

响应字段：

| 字段 | 说明 |
| --- | --- |
| `album.id` | 专辑 ID |
| `album.name` | 专辑名 |
| `album.picUrl` | 封面 |
| `album.size` | 歌曲数量 |
| `album.artist.name` | 歌手 |
| `album.company` | 发行公司 |
| `album.publishTime` | 发布时间 |
| `songs[]` | 专辑歌曲列表 |

实测：

```text
album detail: code=200, songs=1
```

## QQ 音乐

### 歌曲详情

```http
GET https://c.y.qq.com/v8/fcg-bin/fcg_play_single_song.fcg?songmid=<songmid>&format=json
Referer: http://m.y.qq.com
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

响应路径：

```text
data[]
```

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 数字歌曲 ID，歌词接口需要 |
| `mid` | 歌曲 MID，下载接口需要 |
| `name` | 歌曲名 |
| `singer[].name` | 歌手 |
| `album.id` | 专辑数字 ID |
| `album.mid` | 专辑 MID |
| `album.name` | 专辑名 |
| `interval` | 时长，秒 |

### 封面

QQ 封面通常由 `albummid` 拼接：

```text
https://y.gtimg.cn/music/photo_new/T002R300x300M000<albummid>.jpg
```

常见尺寸可替换 `R300x300`：

```text
T002R150x150M000<albummid>.jpg
T002R300x300M000<albummid>.jpg
T002R500x500M000<albummid>.jpg
T002R800x800M000<albummid>.jpg
```

### 歌词

```http
POST https://u.y.qq.com/cgi-bin/musicu.fcg
Referer: https://y.qq.com/portal/player.html
Content-Type: application/json
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

请求体：

```json
{
  "comm": {
    "ct": 11,
    "cv": "1003006",
    "v": "1003006",
    "os_ver": "15",
    "phonetype": "24122RKC7C",
    "rom": "Redmi/miro/miro:15/AE3A.240806.005/OS2.0.105.0.VOMCNXM:user/release-keys",
    "tmeAppID": "qqmusiclight",
    "nettype": "NETWORK_WIFI",
    "udid": "0",
    "uid": "0",
    "sid": "",
    "loginUin": "0",
    "platform": "yqq.json",
    "needNewCode": 0
  },
  "request": {
    "method": "GetPlayLyricInfo",
    "module": "music.musichallSong.PlayLyricInfo",
    "param": {
      "albumName": "<base64 album name>",
      "crypt": 1,
      "ct": 19,
      "cv": 2111,
      "interval": 260,
      "lrc_t": 0,
      "qrc": 1,
      "qrc_t": 0,
      "roma": 1,
      "roma_t": 0,
      "singerName": "<base64 singer name>",
      "songID": 301956826,
      "songName": "<base64 song name>",
      "trans": 1,
      "trans_t": 0,
      "type": 0
    }
  }
}
```

响应路径：

```text
request.data
```

字段：

| 字段 | 说明 |
| --- | --- |
| `lyric` | 原文歌词，`crypt=1` 时通常是 QRC 加密 hex |
| `trans` | 翻译歌词，通常也是 QRC 加密 hex |
| `roma` | 罗马音歌词，通常也是 QRC 加密 hex |
| `lrc_t` / `qrc_t` / `trans_t` / `roma_t` | 更新时间戳 |

注意：

- `songID` 是数字 ID，不是 `songmid`。
- `songName`、`singerName`、`albumName` 需要 base64。
- `crypt=1` 返回的 QRC 需要解密后再解析。

实测：

```text
code=0, request.code=0, lyric/trans/roma 非空
```

### 专辑搜索

```http
GET http://c.y.qq.com/soso/fcgi-bin/search_for_qq_cp?format=json&p=1&n=10&w=<keyword>&t=8
Referer: https://y.qq.com/portal/search.html
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

`t=8` 表示专辑搜索。

响应路径：

```text
data.album.list[]
```

字段：

| 字段 | 说明 |
| --- | --- |
| `albumID` | 专辑数字 ID |
| `albumMID` | 专辑 MID |
| `albumName` | 专辑名 |
| `publicTime` | 发布时间 |
| `singerName` | 歌手 |

### 专辑详情

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
    "ct": 24,
    "cv": 0
  },
  "album": {
    "module": "music.musichallAlbum.AlbumInfoServer",
    "method": "GetAlbumDetail",
    "param": {
      "albumMid": "<albumMID>"
    }
  }
}
```

响应路径：

```text
album.data
```

字段：

| 字段 | 说明 |
| --- | --- |
| `basicInfo.albumID` | 专辑数字 ID |
| `basicInfo.albumMid` | 专辑 MID |
| `basicInfo.albumName` | 专辑名 |
| `basicInfo.publishDate` | 发布时间 |
| `basicInfo.desc` | 描述 |
| `company.name` | 发行公司 |
| `singer.singerList[].name` | 歌手 |

### 专辑歌曲列表

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
    "ct": 24,
    "cv": 0
  },
  "album": {
    "module": "music.musichallAlbum.AlbumSongList",
    "method": "GetAlbumSongList",
    "param": {
      "albumMid": "<albumMID>",
      "begin": 0,
      "num": 100,
      "order": 2
    }
  }
}
```

响应路径：

```text
album.data.songList[].songInfo
```

字段：

| 字段 | 说明 |
| --- | --- |
| `mid` | 歌曲 MID |
| `name` | 歌曲名 |
| `interval` | 时长，秒 |
| `singer[].name` | 歌手 |
| `album.mid` | 专辑 MID |
| `album.name` | 专辑名 |
| `file.size_128mp3` | 128k 文件大小 |
| `file.size_320mp3` | 320k 文件大小 |
| `file.size_flac` | FLAC 文件大小 |
| `pay.pay_play` | 播放/版权权限标识 |

实测：

```text
album detail: code=0, album.code=0
album songs: total=11, count=10
```

## 酷我音乐

### 歌曲信息与普通歌词

```http
GET http://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId=<rid>&httpsStatus=1
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

响应字段：

| 字段 | 说明 |
| --- | --- |
| `status` | `200` 表示成功 |
| `data.songinfo.songName` | 歌曲名 |
| `data.songinfo.artist` | 歌手 |
| `data.songinfo.pic` | 封面 |
| `data.lrclist[]` | 普通逐行歌词 |
| `data.lrclist[].time` | 时间，秒字符串 |
| `data.lrclist[].lineLyric` | 歌词文本 |

实测：

```text
status=200, lrclist=63
```

### 新歌词接口

```http
GET http://newlyric.kuwo.cn/newlyric.lrc?<encoded_params>
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

明文参数：

```text
user=12345,web,web,web&requester=localhost&req=1&rid=MUSIC_<rid>&lrcx=1
```

编码规则：

1. 明文参数按字节与 key 循环异或。
2. key：

```text
yeelion
```

3. 异或结果做 base64，作为查询串。

响应解码：

1. 响应以 `tp=content` 开头。
2. 找到 `\\r\\n\\r\\n` 后的 payload。
3. 对 payload 做 zlib inflate。
4. 如果请求带 `lrcx=1`，inflate 后内容还需要 compact base64 decode，再与 `yeelion` 循环异或。
5. 最终按 GB18030 解码为文本。

### 封面

酷我接口中常见封面字段：

```text
data.songinfo.pic
hts_img
img
pic120
web_albumpic_short
```

处理规则：

- 如果封面不以 `http` 开头，补 `http://`。
- 部分小图 URL 可把 `_100.`、`_120.`、`_150.` 替换成 `_500.` 或 `_700.` 获取更大图。

### 专辑搜索

```http
GET http://search.kuwo.cn/r.s
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

查询参数：

| 参数 | 值 |
| --- | --- |
| `all` | 搜索关键词 |
| `ft` | `album` |
| `itemset` | `web_2013` |
| `client` | `kt` |
| `pcmp4` | `1` |
| `geo` | `c` |
| `vipver` | `1` |
| `pn` | `0` |
| `rn` | `10` |
| `rformat` | `json` |
| `encoding` | `utf8` |

响应路径：

```text
albumlist[]
```

字段：

| 字段 | 说明 |
| --- | --- |
| `albumid` / `id` | 专辑 ID |
| `name` | 专辑名 |
| `artist` / `aartist` | 歌手 |
| `hts_img` / `img` | 封面 |
| `musiccnt` | 歌曲数量 |
| `info` | 描述 |
| `company` | 发行公司 |
| `pub` | 发布时间 |
| `PLAYCNT` | 播放量 |

### 专辑详情与歌曲

```http
GET http://search.kuwo.cn/r.s
Cookie: <可选>
User-Agent: Mozilla/5.0 ...
```

查询参数：

| 参数 | 值 |
| --- | --- |
| `pn` | 页码，从 `0` 开始 |
| `rn` | `100` |
| `stype` | `albuminfo` |
| `albumid` | 专辑 ID |
| `sortby` | `0` |
| `alflac` | `1` |
| `show_copyright_off` | `1` |
| `pcmp4` | `1` |
| `encoding` | `utf8` |

响应字段：

| 字段 | 说明 |
| --- | --- |
| `albumid` / `id` | 专辑 ID |
| `name` | 专辑名 |
| `hts_img` / `img` | 封面 |
| `songnum` | 歌曲数量 |
| `aartist` / `artist` | 歌手 |
| `info` | 描述 |
| `company` | 发行公司 |
| `pub` | 发布时间 |
| `lang` | 语言 |
| `musiclist[]` | 歌曲列表 |
| `musiclist[].id` / `musicrid` | 歌曲 rid |
| `musiclist[].name` / `songname` | 歌曲名 |
| `musiclist[].artist` / `aartist` | 歌手 |
| `musiclist[].album` | 专辑名 |
| `musiclist[].duration` | 时长 |
| `musiclist[].MINFO` | 音质和大小信息 |
| `musiclist[].pic120` / `web_albumpic_short` | 歌曲封面 |

备用方案：

```http
GET https://www.kuwo.cn/album_detail/<albumid>
```

当 `search.kuwo.cn/r.s?stype=albuminfo` 返回空列表时，可解析专辑页面中的 HTML/内嵌数据作为兜底。
