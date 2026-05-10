import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 20000,
})

const LONG_OPERATION_TIMEOUT = 120000
const ACCESS_TOKEN_STORAGE_KEY = 'musichub.access_token'

export const getAccessToken = () => localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY) || ''

export const setAccessToken = (token: string) => {
  localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token)
}

export const clearAccessToken = () => {
  localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
}

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.set('X-MusicHub-Token', token)
  }
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    console.error('[api error]', err?.response?.data ?? err.message)
    if (err?.response?.status === 401) {
      clearAccessToken()
      window.dispatchEvent(new CustomEvent('musichub-auth-required'))
    }
    return Promise.reject(err)
  },
)

export default api

export const accessApi = {
  status: () => api.get<{ authenticated: boolean }>('/access/status').then((r) => r.data),
  login: (password: string) =>
    api.post<{ token: string }>('/access/login', { password }).then((r) => r.data),
  changePassword: (current_password: string, new_password: string) =>
    api.post<{ status: string }>('/access/password', { current_password, new_password }).then((r) => r.data),
  logout: () => api.post<{ status: string }>('/access/logout').then((r) => r.data),
}

export interface AccountStatus {
  platform: 'netease' | 'qq'
  user_id: string | null
  nickname: string | null
  vip_type: number | null
  /** 平台官方下发的 VIP 图标 URL 列表（如 QQ 的 nsvip7.png）。前端直接渲染图片。 */
  vip_icons: string[]
  avatar_url: string | null
  is_valid: boolean
  updated_at: string | null
}

export type QQLoginType = 'qq' | 'wx' | 'mobile'

export interface QRCreateResponse {
  platform: 'netease' | 'qq'
  type: QQLoginType | 'default'
  ticket: string
  qr_url: string
  qr_image_b64: string | null
  created_at_ms: number
}

export interface QRPollResponse {
  platform: 'netease' | 'qq'
  status: 'pending' | 'scanned' | 'success' | 'expired' | 'unknown'
  user_id: string | null
  nickname: string | null
  vip_type: number | null
  vip_icons: string[]
  avatar_url: string | null
  message: string | null
}

export const authApi = {
  status: () => api.get<AccountStatus[]>('/auth/status').then((r) => r.data),
  createQR: (platform: 'netease' | 'qq', type: QQLoginType = 'qq') =>
    api
      .post<QRCreateResponse>(`/auth/qr/${platform}`, null, { params: { type } })
      .then((r) => r.data),
  pollQR: (platform: 'netease' | 'qq', ticket: string) =>
    api
      .get<QRPollResponse>(`/auth/qr/${platform}/poll`, { params: { ticket } })
      .then((r) => r.data),
  logout: (platform: 'netease' | 'qq') =>
    api.delete(`/auth/${platform}`).then((r) => r.data),
  importCookie: (platform: 'netease' | 'qq', cookie: string) =>
    api.post(`/auth/cookie/${platform}`, { cookie }).then((r) => r.data),
  /** 用现有 Cookie 重新拉账号信息（昵称 / VIP / 头像）。 */
  refresh: (platform: 'netease' | 'qq') =>
    api
      .post<{
        platform: string
        user_id: string | null
        nickname: string | null
        vip_type: number | null
        vip_icons: string[]
        avatar_url: string | null
      }>(`/auth/refresh/${platform}`)
      .then((r) => r.data),
}

export const healthApi = {
  ping: () => api.get<{ status: string; version: string }>('/health').then((r) => r.data),
}

// ===== 发现 =====
export interface SongItem {
  platform: 'netease' | 'qq'
  id: string
  name: string
  artists: string[]
  primary_artist: string
  album: string | null
  album_id: string | null
  duration_ms: number
  cover_url: string | null
}

export interface PlaylistDetail {
  platform: 'netease' | 'qq'
  id: string
  name: string
  description: string | null
  cover_url: string | null
  creator: string | null
  track_count: number
  songs: SongItem[]
}

export interface AlbumDetail {
  platform: 'netease' | 'qq'
  id: string
  name: string
  description: string | null
  cover_url: string | null
  artists: string[]
  company: string | null
  track_count: number
  songs: SongItem[]
}

export interface PlaylistBrief {
  platform: 'netease' | 'qq'
  id: string
  name: string
  cover_url: string | null
  description: string | null
  creator: string | null
  track_count: number
  play_count: number
}

export interface RecommendMode {
  id: string
  label: string
}

/**
 * 分页歌单返回结构。直接对应平台原生 API 的分页语义：
 *  - QQ: ``recommend.get_recommend_songlist(page, num)`` 携带 ``has_more``
 *  - 网易云: ``/playlist/list?offset/limit`` 携带 ``more``
 */
export interface PlaylistPage {
  items: PlaylistBrief[]
  page: number
  page_size: number
  has_more: boolean
}

export const discoverApi = {
  search: (q: string, platform: 'netease' | 'qq' | 'all' = 'all', limit = 20) =>
    api
      .get<{ items: SongItem[] }>('/discover/search', { params: { q, platform, limit } })
      .then((r) => r.data.items),
  song: (platform: 'netease' | 'qq', id: string) =>
    api.get<SongItem>(`/discover/song/${platform}/${id}`).then((r) => r.data),
  playlist: (platform: 'netease' | 'qq', id: string) =>
    api.get<PlaylistDetail>(`/discover/playlist/${platform}/${id}`).then((r) => r.data),
  album: (platform: 'netease' | 'qq', id: string) =>
    api.get<AlbumDetail>(`/discover/album/${platform}/${id}`).then((r) => r.data),
  recommendSongs: (platform: 'netease' | 'qq' = 'netease', limit = 30) =>
    api
      .get<{ items: SongItem[] }>('/discover/recommend/songs', { params: { platform, limit } })
      .then((r) => r.data.items),
  recommendSongsByMode: (
    platform: 'netease' | 'qq' = 'netease',
    mode: string = 'default',
    limit = 30,
  ) =>
    api
      .get<{ items: SongItem[] }>('/discover/recommend/songs', { params: { platform, mode, limit } })
      .then((r) => r.data.items),
  /**
   * 推荐歌单（按模式 + 分页）。后端直接把 `page/page_size` 透传给平台原生分页 API。
   */
  recommendPlaylistsByMode: (
    platform: 'netease' | 'qq' = 'netease',
    mode: string = 'default',
    page = 1,
    page_size = 25,
  ) =>
    api
      .get<PlaylistPage>('/discover/recommend/playlists', {
        params: { platform, mode, page, page_size },
      })
      .then((r) => r.data),
  recommendModes: (platform: 'netease' | 'qq' = 'netease') =>
    api
      .get<{ song_modes: RecommendMode[]; playlist_modes: RecommendMode[] }>('/discover/recommend/modes', {
        params: { platform },
      })
      .then((r) => r.data),
  topLists: (platform: 'netease' | 'qq' = 'netease') =>
    api
      .get<{ items: PlaylistBrief[] }>('/discover/toplists', { params: { platform } })
      .then((r) => r.data.items),
  /**
   * 分类热门歌单（分页）。`page` 从 1 开始，`page_size` 由前端按需调整。
   */
  hotPlaylists: (
    platform: 'netease' | 'qq' = 'netease',
    category: string = '全部',
    page = 1,
    page_size = 25,
  ) =>
    api
      .get<PlaylistPage>('/discover/hot/playlists', {
        params: { platform, category, page, page_size },
      })
      .then((r) => r.data),
  /** 动态热门订阅：网易云 / QQ 各自的官方歌单广场分类列表 */
  hotPlaylistCategories: (platform: 'netease' | 'qq' = 'netease') =>
    api
      .get<{ items: string[] }>('/discover/hot/playlist-categories', { params: { platform } })
      .then((r) => r.data.items),
  myPlaylists: (platform: 'netease' | 'qq' = 'netease') =>
    api
      .get<{
        created: PlaylistBrief[]
        collected: PlaylistBrief[]
        logged_in: boolean
        user_id?: string
        nickname?: string
      }>('/discover/my/playlists', { params: { platform } })
      .then((r) => r.data),
  suggest: (
    kind: 'playlist' | 'album' | 'artist',
    q: string,
    platform: 'netease' | 'qq' = 'netease',
    limit = 12,
  ) =>
    api
      .get<{ items: SuggestItem[] }>(`/discover/suggest/${kind}`, {
        params: { q, platform, limit },
      })
      .then((r) => r.data.items),
}

// 通用建议项（用于订阅添加自动补全）
export interface SuggestItem {
  platform: 'netease' | 'qq'
  id: string
  name: string
  cover_url?: string | null
  // 歌单
  creator?: string | null
  track_count?: number
  play_count?: number
  // 专辑
  artists?: string[]
  publish_date?: string | null
  // 歌手
  alias?: string[]
  song_count?: number
  album_count?: number
  fans_count?: number
}

// ===== 下载 =====
export interface DownloadResponse {
  success: boolean
  skipped_dup: boolean
  error: string | null
  file_path: string | null
  audio_format: string | null
  bitrate: number | null
  quality: string | null
  file_size: number | null
  has_cover: boolean
  has_lyric: boolean
  song: {
    name: string
    artists: string[]
    album: string | null
    duration_ms: number
    cover_url: string | null
  }
}

export const downloadApi = {
  /** 异步入队（默认） */
  song: (platform: 'netease' | 'qq', id: string) =>
    api.post<{ task_id: number; song_name: string }>('/download/song', { platform, id }).then((r) => r.data),
  /** 同步下载（一次返回结果，不进任务列表） */
  songSync: (platform: 'netease' | 'qq', id: string) =>
    api
      .post<DownloadResponse>('/download/song', { platform, id }, { params: { sync: true } })
      .then((r) => r.data),
  songs: (platform: 'netease' | 'qq', ids: string[]) =>
    api
      .post<{ task_ids: number[]; enqueued: number; skipped_lookup: number }>(
        '/download/songs',
        { platform, ids },
      )
      .then((r) => r.data),
  playlist: (platform: 'netease' | 'qq', id: string) =>
    api
      .post<{ parent_task_id: number; child_task_ids: number[]; playlist_name: string; song_count: number }>(
        '/download/playlist',
        { platform, id },
      )
      .then((r) => r.data),
  album: (platform: 'netease' | 'qq', id: string) =>
    api
      .post<{ parent_task_id: number; child_task_ids: number[]; album_name: string; song_count: number }>(
        '/download/album',
        { platform, id },
      )
      .then((r) => r.data),
}

// ===== 任务 =====
export interface DownloadTaskItem {
  id: number
  parent_task_id: number | null
  target_type: 'song' | 'playlist' | 'album'
  target_id: string
  platform: 'netease' | 'qq'
  source_subscription_id: number | null
  sync_run_id: number | null
  source_type: string | null
  source_subscription_ids: number[]
  sync_run_ids: number[]
  source_types: string[]
  title: string | null
  sub_title: string | null
  cover_url: string | null
  status:
    | 'queued'
    | 'pending'
    | 'running'
    | 'success'
    | 'failed'
    | 'skipped_dup'
    | 'cancelled'
  priority: number
  progress: number
  total_count: number
  success_count: number
  fail_count: number
  skip_count: number
  error_msg: string | null
  file_path: string | null
  audio_format: string | null
  bitrate: number | null
  quality: string | null
  file_size: number | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export const tasksApi = {
  list: (params?: { status?: string; target_type?: string; parent_only?: boolean; limit?: number; offset?: number }) =>
    api.get<{ items: DownloadTaskItem[]; total: number }>('/tasks', { params }).then((r) => r.data),
  summary: () => api.get<Record<string, number>>('/tasks/summary').then((r) => r.data),
  control: () => api.get<{ paused: boolean; concurrency: number; queue_size: number }>('/tasks/control').then((r) => r.data),
  detail: (id: number) =>
    api.get<{ task: DownloadTaskItem; children: DownloadTaskItem[] }>(`/tasks/${id}`).then((r) => r.data),
  cancel: (id: number) => api.delete(`/tasks/${id}`).then((r) => r.data),
  cancelSelected: (ids: number[]) =>
    api.post<{ requested: number; cancelled: number }>('/tasks/cancel', { ids }).then((r) => r.data),
  cancelWaiting: () => api.post<{ cancelled: number }>('/tasks/cancel-waiting').then((r) => r.data),
  retrySelected: (ids: number[]) =>
    api.post<{ requested: number; retried: number }>('/tasks/retry', { ids }).then((r) => r.data),
  deleteSelected: (ids: number[], deleteLocalFiles = false) =>
    api
      .post<{
        requested: number
        deleted: number
        files_deleted: number
        songs_deleted: number
        kept_for_file_errors: number
        file_errors: Array<{ file_path: string; error: string }>
      }>(
        '/tasks/delete',
        { ids, delete_local_files: deleteLocalFiles },
        { timeout: LONG_OPERATION_TIMEOUT },
      )
      .then((r) => r.data),
  pause: () => api.post<{ paused: boolean; concurrency: number; queue_size: number }>('/tasks/pause').then((r) => r.data),
  resume: () => api.post<{ paused: boolean; concurrency: number; queue_size: number }>('/tasks/resume').then((r) => r.data),
  clear: (status: string) => api.delete('/tasks', { params: { status } }).then((r) => r.data),
}

// ===== 订阅 =====
export type SubscriptionTargetType =
  | 'playlist'
  | 'album'
  | 'artist'
  | 'daily'
  | 'meta_my_created'
  | 'meta_my_collected'
  | 'meta_toplists'
  | 'meta_hot_category'

export type QuickSubscribeKind =
  | 'daily'
  | 'toplists_all'
  | 'follow_my_created'
  | 'follow_my_collected'

export interface SubscriptionItem {
  id: number
  platform: 'netease' | 'qq'
  target_type: SubscriptionTargetType
  platform_playlist_id: string
  name: string
  description: string | null
  creator: string | null
  cover_url: string | null
  auto_added: boolean
  parent_subscription_id: number | null
  enabled: boolean
  sync_interval_hours: number
  generate_m3u: boolean
  cross_platform: boolean
  cross_platform_id: string | null
  last_sync_at: string | null
  last_sync_track_count: number
  last_sync_new_count: number
  last_error: string | null
  m3u_file_path: string | null
  created_at: string
  /** meta_hot_category 等：{ categories, pick_mode, top_n, pool_size } 或旧版 category */
  meta_config?: Record<string, unknown> | null
}

export interface SyncReport {
  subscription_id: number
  name: string
  remote_count: number
  new_count: number
  enqueued: number
  already_queued?: number
  skipped_local: number
  task_ids?: number[]
  error: string | null
  m3u_generated?: boolean
  m3u_error?: string | null
}

export interface SyncBatch {
  id: string
  status: 'running' | 'completed' | 'failed'
  total: number
  completed: number
  enqueued: number
  already_queued?: number
  error: string | null
  reports: SyncReport[]
  started_at: string
  finished_at: string | null
}

export const subscriptionsApi = {
  list: () => api.get<{ items: SubscriptionItem[] }>('/subscriptions').then((r) => r.data.items),
  add: (params: {
    platform: 'netease' | 'qq'
    target_type: SubscriptionTargetType
    id: string
    sync_interval_hours?: number
    enabled?: boolean
    generate_m3u?: boolean
    cross_platform?: boolean
    cross_platform_id?: string
  }) =>
    api
      .post<SubscriptionItem>('/subscriptions', params, { timeout: LONG_OPERATION_TIMEOUT })
      .then((r) => r.data),
  quickAdd: (params: {
    kind: QuickSubscribeKind
    platform: 'netease' | 'qq'
    sync_interval_hours?: number
    enabled?: boolean
    generate_m3u?: boolean
  }) =>
    api
      .post<SubscriptionItem>('/subscriptions/quick', params, { timeout: LONG_OPERATION_TIMEOUT })
      .then((r) => r.data),
  /** 分类热门 TopN：每个父订阅维护一个分类的热门子歌单。 */
  addHotCategory: (params: {
    platform: 'netease' | 'qq'
    categories: string[]
    pick_mode?: 'top_play_count' | 'random'
    drop_policy?: 'strict' | 'keep_history'
    top_n?: number
    pool_size?: number
    sync_interval_hours?: number
    enabled?: boolean
    generate_m3u?: boolean
  }) =>
    api
      .post<SubscriptionItem>('/subscriptions/hot-category', params, { timeout: LONG_OPERATION_TIMEOUT })
      .then((r) => r.data),
  bulkAdd: (params: {
    items: Array<{
      platform: 'netease' | 'qq'
      target_type?: SubscriptionTargetType
      id: string
      name?: string
      cover_url?: string | null
      creator?: string | null
    }>
    sync_interval_hours?: number
    enabled?: boolean
    generate_m3u?: boolean
  }) =>
    api
      .post<{ created: SubscriptionItem[]; skipped: any[] }>('/subscriptions/bulk', params, {
        timeout: LONG_OPERATION_TIMEOUT,
      })
      .then((r) => r.data),
  update: (
    id: number,
    params: {
      sync_interval_hours?: number
      enabled?: boolean
      generate_m3u?: boolean
      cross_platform?: boolean
      cross_platform_id?: string
    },
  ) =>
    api.put<SubscriptionItem>(`/subscriptions/${id}`, params).then((r) => r.data),
  remove: (id: number, childAction: 'delete' | 'promote' = 'delete') =>
    api.delete(`/subscriptions/${id}`, { params: { child_action: childAction } }).then((r) => r.data),
  syncNow: (id: number) =>
    api.post<SyncReport>(`/subscriptions/${id}/sync`).then((r) => r.data),
  syncAll: () =>
    api.post<SyncBatch>('/subscriptions/sync_all').then((r) => r.data),
  syncAllStatus: (batchId: string) =>
    api.get<SyncBatch>(`/subscriptions/sync_all/${batchId}`).then((r) => r.data),
  generateM3UAll: () =>
    api
      .post<{ generated: number }>('/m3u/generate', null, { timeout: LONG_OPERATION_TIMEOUT })
      .then((r) => r.data),
  generateM3UOne: (id: number) =>
    api.post<{ file_path: string | null }>(`/m3u/generate/${id}`).then((r) => r.data),
}

// ===== 试听 =====
export interface PreviewInfo {
  url: string
  audio_format: string
  bitrate: number
  quality: string | null
  name: string
  artists: string[]
  primary_artist: string
  album: string | null
  duration_ms: number
  cover_url: string | null
}

export const previewApi = {
  song: (platform: 'netease' | 'qq', id: string, quality: string = 'standard') =>
    api
      .get<PreviewInfo>(`/preview/song/${platform}/${id}`, { params: { quality } })
      .then((r) => r.data),
}

// ===== 本地库 =====
export interface LibrarySong {
  id: number
  name: string
  artist: string
  album: string | null
  duration_ms: number
  audio_format: string | null
  bitrate: number | null
  file_size: number | null
  has_cover: boolean
  has_lyric: boolean
  file_path: string | null
  created_at: string
  sources: { platform: string; platform_song_id: string }[]
}

export const libraryApi = {
  songs: (params?: {
    q?: string
    artist?: string
    album?: string
    sort?: 'latest' | 'name' | 'duration'
    limit?: number
    offset?: number
  }) =>
    api
      .get<{ items: LibrarySong[]; total: number; limit: number; offset: number }>(
        '/library/songs',
        { params },
      )
      .then((r) => r.data),
  artists: () =>
    api
      .get<{ items: { name: string; key: string; song_count: number }[] }>('/library/artists')
      .then((r) => r.data.items),
  albums: () =>
    api
      .get<{ items: { name: string; artist: string; song_count: number }[] }>('/library/albums')
      .then((r) => r.data.items),
  song: (id: number) => api.get<LibrarySong>(`/library/song/${id}`).then((r) => r.data),
  deleteSong: (id: number) => api.delete<{ ok: boolean }>(`/library/song/${id}`).then((r) => r.data),
  /** 本地音频流 URL（直接给 audio.src 用） */
  streamUrl: (id: number) => `/api/library/stream/${id}`,
  /** 本地封面 URL（直接给 img.src 用） */
  coverUrl: (id: number) => `/api/library/cover/${id}`,
}

// ===== 统计 =====
export interface StatsOverview {
  total_songs: number
  total_size_bytes: number
  total_duration_ms: number
  has_lyric: number
  has_cover: number
  by_format: Record<string, number>
  by_platform: Record<string, number>
  by_quality: Record<string, number>
  by_task_status: Record<string, number>
  daily_recent: { date: string; count: number }[]
}

export const statsApi = {
  overview: () => api.get<StatsOverview>('/stats/overview').then((r) => r.data),
}

// ===== 设置 =====
export type AppSettings = Record<string, any>

export const settingsApi = {
  get: () => api.get<AppSettings>('/settings').then((r) => r.data),
  update: (items: Record<string, any>) =>
    api.put<AppSettings>('/settings', { items }).then((r) => r.data),
}
