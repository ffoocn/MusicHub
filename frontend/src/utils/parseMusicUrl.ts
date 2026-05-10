/**
 * 解析网易云 / QQ 音乐的网页链接，提取平台、资源类型与 ID。
 *
 * 支持的格式：
 *   - 网易云：``music.163.com/#/song?id=...`` / ``...playlist?id=...`` / ``...album?id=...``
 *   - QQ 音乐：``y.qq.com/n/ryqq/songDetail/<mid>`` / ``...playlist/<id>`` / ``...album/<mid>``
 *
 * 在「顶栏智能搜索框」与「链接导入面板」中复用，避免两处各自维护正则。
 */
export interface ParsedMusicUrl {
  platform: 'netease' | 'qq'
  kind: 'song' | 'playlist' | 'album'
  id: string
}

/** 资源类型在 UI 上的中文标签。 */
export const KIND_LABEL: Record<ParsedMusicUrl['kind'], string> = {
  song: '歌曲',
  playlist: '歌单',
  album: '专辑',
}

/** 平台在 UI 上的中文标签。 */
export const PLATFORM_LABEL: Record<ParsedMusicUrl['platform'], string> = {
  netease: '网易云',
  qq: 'QQ 音乐',
}

/**
 * 解析音乐链接。无法识别时返回 ``null``。
 *
 * 解析规则：
 *   1) 含 ``music.163.com`` ⇒ 网易云。
 *      - 末尾 ``id=<digits>`` 取出 ID；
 *      - 路径含 ``playlist`` / ``album`` 分别归类，否则视为单曲。
 *   2) 含 ``y.qq.com`` 或 ``qq.com/n/ryqq`` ⇒ QQ 音乐。
 *      - 用 ``/(songDetail|playlist|album)/<id>`` 抓出资源类型与 ID。
 *
 * @param raw 用户粘贴的原始字符串（前后空格会被忽略）。
 */
export const parseMusicUrl = (raw: string): ParsedMusicUrl | null => {
  const value = raw.trim()
  if (!value) return null

  if (/music\.163\.com/.test(value)) {
    const idMatch = value.match(/[?&]id=(\d+)/)
    if (!idMatch) return null
    const id = idMatch[1]
    if (/playlist/.test(value)) return { platform: 'netease', kind: 'playlist', id }
    if (/album/.test(value)) return { platform: 'netease', kind: 'album', id }
    return { platform: 'netease', kind: 'song', id }
  }

  if (/y\.qq\.com/.test(value) || /qq\.com\/n\/ryqq/.test(value)) {
    const match = value.match(/\/(song(?:Detail)?|playlist|album)\/([\w]+)/i)
    if (!match) return null
    const kindRaw = match[1].toLowerCase()
    const kind: ParsedMusicUrl['kind'] = kindRaw.startsWith('song')
      ? 'song'
      : kindRaw === 'album'
        ? 'album'
        : 'playlist'
    return { platform: 'qq', kind, id: match[2] }
  }

  return null
}

/** ``true`` 表示字符串看起来像 HTTP/HTTPS URL，可作为 URL 模式的快速预判。 */
export const looksLikeUrl = (raw: string): boolean => /^https?:\/\//i.test(raw.trim())
