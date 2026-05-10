# QQ 音乐下载 API

本文档只记录 QQ 音乐官方/站内下载接口。高音质下载通常需要登录 Cookie，部分歌曲还需要账号具备 VIP 权限。

## 结论

下载 URL 通过 `musicu.fcg` 的 `music.vkey.GetVkey` 获取：

```http
POST https://u.y.qq.com/cgi-bin/musicu.fcg
```

接口返回的是 `purl`，需要和响应里的 `sip` 域名拼接成真实音频 URL。

## 请求

```http
POST https://u.y.qq.com/cgi-bin/musicu.fcg
Referer: http://y.qq.com
Content-Type: application/json
Cookie: <QQ 音乐登录 Cookie>
User-Agent: Mozilla/5.0 ...
```

请求体示例：

```json
{
  "comm": {
    "cv": 4747474,
    "ct": 24,
    "format": "json",
    "inCharset": "utf-8",
    "outCharset": "utf-8",
    "notice": 0,
    "platform": "yqq.json",
    "needNewCode": 1,
    "uin": 983993
  },
  "req_1": {
    "module": "music.vkey.GetVkey",
    "method": "UrlGetVkey",
    "param": {
      "guid": "1234567890",
      "songmid": [
        "004YZbkL2MNHoY",
        "004YZbkL2MNHoY"
      ],
      "songtype": [0, 0],
      "uin": "983993",
      "loginflag": 1,
      "platform": "20",
      "filename": [
        "M800004YZbkL2MNHoY004YZbkL2MNHoY.mp3",
        "M500004YZbkL2MNHoY004YZbkL2MNHoY.mp3"
      ]
    }
  }
}
```

参数说明：

| 字段 | 说明 |
| --- | --- |
| `guid` | 10 位左右随机数字字符串 |
| `songmid` | 歌曲 MID 数组，和 `filename` 一一对应 |
| `songtype` | 通常填 `0` |
| `uin` | 登录 QQ 号，字符串；也可看到部分实现传 `"0"` |
| `loginflag` | 登录态请求填 `1` |
| `platform` | 常用 `20` |
| `filename` | 请求的目标音质文件名数组 |

## 文件名前缀与音质

文件名格式：

```text
<prefix><songmid><songmid>.<ext>
```

常用前缀：

| prefix | ext | 说明 |
| --- | --- | --- |
| `AI00` | `flac` | 臻品母带/更高规格，需对应权限 |
| `Q001` | `flac` | 臻品/空间音频类，需对应权限 |
| `Q000` | `flac` | 臻品/空间音频类，需对应权限 |
| `F000` | `flac` | FLAC 无损 |
| `O801` | `ogg` | 高码率 OGG，常见约 640k |
| `M800` | `mp3` | 320k MP3 |
| `M500` | `mp3` | 128k MP3 |

推荐尝试顺序：

```text
AI00 -> Q001 -> Q000 -> F000 -> O801 -> M800 -> M500
```

如果只需要常规可下载音质：

```text
M800 -> M500
```

## 响应

关键路径：

```text
req_1.data.midurlinfo[]
req_1.data.sip[]
```

响应示例结构：

```json
{
  "code": 0,
  "req_1": {
    "code": 0,
    "data": {
      "sip": [
        "https://ws.stream.qqmusic.qq.com/",
        "http://ws.stream.qqmusic.qq.com/"
      ],
      "midurlinfo": [
        {
          "filename": "M800004YZbkL2MNHoY004YZbkL2MNHoY.mp3",
          "purl": "M800004YZbkL2MNHoY004YZbkL2MNHoY.mp3?...",
          "errtype": ""
        }
      ]
    }
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `code` | 顶层状态，`0` 表示成功 |
| `req_1.code` | 模块状态，`0` 表示成功 |
| `sip` | 可用音频域名列表 |
| `midurlinfo[].filename` | 对应请求中的文件名 |
| `midurlinfo[].purl` | 真实路径，非完整 URL |
| `midurlinfo[].errtype` | 错误类型，常为空字符串 |

拼接下载 URL：

```text
download_url = sip[0] + purl
```

如果 `purl` 已经是完整 URL，则直接使用 `purl`。

处理规则：

1. 按请求音质顺序遍历 `midurlinfo`。
2. 找到 `filename` 匹配且 `purl` 非空的第一项。
3. 用 `sip[0]` 拼接 `purl` 得到下载地址。
4. 如果所有 `purl` 都为空，说明该账号/歌曲/音质组合不可下载或需要更高权限。

## Cookie 与登录态

请求头透传 QQ 音乐登录 Cookie。常见有效字段包括：

```text
uin
superuin
superkey
supertoken
qqmusic_key
```

不同登录方式下字段可能不同，建议直接透传完整 Cookie。请求体里的 `uin` 可从 Cookie 的 `uin`、`superuin`、`pt2gguin` 等字段取值，去掉前缀 `o` 和前导零后作为数字字符串使用。

## 实测记录

测试 `songmid`：

```text
004YZbkL2MNHoY
```

`GetVkey` 返回：

| 请求前缀 | 是否返回 purl | 说明 |
| --- | --- | --- |
| `AI00` | 否 | 无对应权限或歌曲不支持 |
| `Q001` | 否 | 无对应权限或歌曲不支持 |
| `Q000` | 否 | 无对应权限或歌曲不支持 |
| `F000` | 否 | 无对应权限或歌曲不支持 |
| `O801` | 是 | Range 探测成功，`audio/x-ogg` |
| `M800` | 否 | 无对应权限或歌曲不支持 |
| `M500` | 是 | 返回 MP3 purl |

`O801` 拼接后的音频 URL 实测支持 Range：

```text
HTTP 206
Content-Type: audio/x-ogg
```

## 最小实现流程

1. 准备歌曲 `songmid`。
2. 生成 `guid`。
3. 按目标音质构造 `filename[]`、`songmid[]`、`songtype[]`。
4. 请求 `musicu.fcg` 的 `music.vkey.GetVkey`。
5. 从 `req_1.data.midurlinfo[]` 里找第一个非空 `purl`。
6. 用 `req_1.data.sip[0] + purl` 拼接下载地址。
7. 立即下载；URL 带签名和时效，失败时重新请求 `GetVkey`。
