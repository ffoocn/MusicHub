<template>
  <section class="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-theme-xs dark:border-gray-800 dark:bg-white/[0.03] lg:h-full">

    <header class="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 px-5 py-4 dark:border-gray-800 sm:px-6">
      <div class="min-w-0">
        <h2 class="text-base font-semibold text-gray-800 dark:text-white/90">{{ modeLabel }}</h2>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          {{ subtitle }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <MusicButton variant="outline" size="xs" :loading="loading" @click="reload">刷新</MusicButton>
        <MusicButton variant="outline" size="xs" :loading="subBusy" @click="subscribeDaily">
          {{ dailySubscribed ? '已订阅每日推荐' : '订阅每日推荐' }}
        </MusicButton>
        <MusicButton v-if="isSongMode" size="xs" :disabled="!songs.length" @click="batchDownloadAll">
          全部下载（{{ songs.length }}）
        </MusicButton>
      </div>
    </header>

    <!-- 选中操作区（仅歌曲模式） -->
    <div
      v-if="isSongMode && checkedKeys.length"
      class="flex flex-wrap items-center gap-3 border-b border-gray-100 px-5 py-3 dark:border-gray-800 sm:px-6"
    >
      <span class="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
        已选 {{ checkedKeys.length }} 首
      </span>
      <MusicButton size="xs" class="ml-auto" @click="batchDownloadSelected">下载选中</MusicButton>
    </div>

    <!-- 内容区 -->
    <div class="min-h-0 flex-1 overflow-y-auto px-5 py-3 sm:px-6">
      <template v-if="isSongMode">
        <div v-if="loading" class="space-y-2 py-3">
          <div v-for="idx in 5" :key="idx" class="h-14 animate-pulse rounded-xl bg-gray-100 dark:bg-white/5"></div>
        </div>
        <MusicEmpty
          v-else-if="!songs.length"
          title="暂无推荐内容"
          description="该模式当前没有数据。可能未登录、或平台接口此刻没有为你推荐结果。"
        />
        <ul v-else class="divide-y divide-gray-100 dark:divide-gray-800">
          <li
            v-for="song in songs"
            :key="songKey(song)"
            class="group flex items-center gap-3 py-2.5 transition hover:bg-gray-50/50 dark:hover:bg-white/[0.02]"
          >
            <input
              type="checkbox"
              :checked="checkedKeys.includes(songKey(song))"
              class="size-4 shrink-0 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
              @change="toggleSong(song)"
            />
            <div class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 text-gray-400 dark:bg-gray-800">
              <img v-if="song.cover_url" :src="song.cover_url" alt="" class="size-full object-cover" />
              <svg v-else class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M18 3a1 1 0 0 0-1.196-.98l-10 2A1 1 0 0 0 6 5v6.499A3.001 3.001 0 1 0 8 14V8.68l8-1.6V11.5A3.001 3.001 0 1 0 18 13V3Z"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-gray-800 dark:text-white/90">{{ song.name }}</p>
              <p class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">{{ song.artists?.join(' / ') || song.primary_artist || '-' }}</p>
            </div>
            <span class="hidden shrink-0 text-xs tabular-nums text-gray-500 dark:text-gray-400 sm:inline">
              {{ fmtDuration(song.duration_ms || 0) }}
            </span>
            <div class="flex shrink-0 items-center gap-1">
              <MusicButton variant="ghost" size="xs" @click="play(song)">试听</MusicButton>
              <MusicButton size="xs" @click="downloadOne(song)">下载</MusicButton>
            </div>
          </li>
        </ul>
      </template>

      <template v-else>
        <PlaylistGrid
          :items="playlists"
          :loading="loading"
          empty-text="该模式当前没有推荐歌单"
        />
      </template>
    </div>

    <!-- Footer：分页器（仅推荐歌单模式 + 至少有过数据时显示） -->
    <footer
      v-if="!isSongMode && (playlists.length > 0 || playlistPage > 1)"
      class="border-t border-gray-100 bg-white px-5 py-3 dark:border-gray-800 dark:bg-transparent sm:px-6"
    >
      <MusicPagination
        :current-page="playlistPage"
        :has-more="hasMore"
        :loading="loading"
        :siblings="1"
        @change="onPlaylistPageChange"
      />
    </footer>

    <SubscribeOptionsDialog
      :open="showDailySubscribeOptions"
      title="订阅每日推荐"
      :message="`订阅 ${props.platform === 'netease' ? '网易云' : 'QQ 音乐'} 每日推荐并每天自动同步。`"
      :loading="subBusy"
      @close="showDailySubscribeOptions = false"
      @confirm="confirmSubscribeDaily"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { discoverApi, downloadApi, subscriptionsApi, type PlaylistBrief, type SongItem } from '@/api'
import { usePlayerStore } from '@/stores/player'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicEmpty from '@/components/music/MusicEmpty.vue'
import MusicPagination from '@/components/music/MusicPagination.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import PlaylistGrid from '@/components/PlaylistGrid.vue'
import SubscribeOptionsDialog from '@/components/SubscribeOptionsDialog.vue'

type PlatformId = 'netease' | 'qq'
type ModeKind = 'song' | 'playlist'

const props = defineProps<{
  platform: PlatformId
  modeKind: ModeKind
  modeId: string
  modeLabel: string
}>()

const toast = useMusicToast()
const player = usePlayerStore()

const songs = ref<SongItem[]>([])
const playlists = ref<PlaylistBrief[]>([])
const loading = ref(false)
const checkedKeys = ref<string[]>([])
const dailySubscribed = ref(false)
const subBusy = ref(false)
const showDailySubscribeOptions = ref(false)

const PLAYLIST_PAGE_SIZE = 25
const playlistPage = ref(1)
const hasMore = ref(false)

const isSongMode = computed(() => props.modeKind === 'song')

const subtitle = computed(() => {
  const platformLabel = props.platform === 'netease' ? '网易云' : 'QQ 音乐'
  return isSongMode.value
    ? `${platformLabel} · 推荐歌曲`
    : `${platformLabel} · 推荐歌单`
})

const songKey = (song: SongItem) => `${song.platform}-${song.id}`

const fmtDuration = (ms: number) => {
  const seconds = Math.floor(ms / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

const toggleSong = (song: SongItem) => {
  const key = songKey(song)
  checkedKeys.value = checkedKeys.value.includes(key)
    ? checkedKeys.value.filter((item) => item !== key)
    : [...checkedKeys.value, key]
}

const play = async (song: SongItem) => {
  try {
    await player.playRemote(song.platform, song.id)
  } catch (e: any) {
    toast.error(`试听失败：${e?.message || e}`)
  }
}

const downloadOne = async (song: SongItem) => {
  try {
    await downloadApi.song(song.platform, song.id)
    toast.success(`已加入下载：${song.name}`)
  } catch (e: any) {
    toast.error(`下载失败：${e?.message || e}`)
  }
}

const batchDownloadSelected = async () => {
  const selected = songs.value.filter((song) => checkedKeys.value.includes(songKey(song)))
  await batchDownload(selected)
}

const batchDownloadAll = async () => {
  await batchDownload(songs.value)
}

const batchDownload = async (list: SongItem[]) => {
  if (!list.length) return
  const groups: Record<string, string[]> = {}
  list.forEach((song) => {
    if (!groups[song.platform]) groups[song.platform] = []
    groups[song.platform].push(song.id)
  })
  try {
    for (const [pf, ids] of Object.entries(groups)) {
      await downloadApi.songs(pf as PlatformId, ids)
    }
    toast.success(`已加入下载队列：${list.length} 首`)
    checkedKeys.value = []
  } catch (e: any) {
    toast.error(`批量下载失败：${e?.message || e}`)
  }
}

const checkDailySubscribed = async () => {
  try {
    const list = await subscriptionsApi.list()
    dailySubscribed.value = list.some(
      (item) => item.platform === props.platform && item.target_type === 'daily',
    )
  } catch {
    dailySubscribed.value = false
  }
}

const subscribeDaily = () => {
  if (subBusy.value) return
  if (dailySubscribed.value) {
    toast.info('已订阅，可在「订阅与自动化」管理')
    return
  }
  showDailySubscribeOptions.value = true
}

const confirmSubscribeDaily = async (generateM3u: boolean) => {
  subBusy.value = true
  try {
    await subscriptionsApi.add({
      platform: props.platform,
      target_type: 'daily',
      id: 'daily',
      generate_m3u: generateM3u,
    })
    dailySubscribed.value = true
    showDailySubscribeOptions.value = false
    toast.success(`已订阅 ${props.platform === 'netease' ? '网易云' : 'QQ 音乐'} 每日推荐`)
  } catch (e: any) {
    if (e?.response?.status === 409) {
      dailySubscribed.value = true
      showDailySubscribeOptions.value = false
      toast.info('已订阅')
    } else {
      toast.error(`订阅失败：${e?.response?.data?.detail || e?.message || e}`)
    }
  } finally {
    subBusy.value = false
  }
}

/**
 * 首屏 / 主条件变更时调用：拉取当前 playlistPage 对应的一页（推荐歌单模式）。
 *
 * 用户切换平台 / 模式时通过 watch 重置 playlistPage = 1，再调用本函数。
 */
const loadData = async () => {
  loading.value = true
  checkedKeys.value = []
  hasMore.value = false
  try {
    if (isSongMode.value) {
      playlists.value = []
      songs.value = await discoverApi.recommendSongsByMode(props.platform, props.modeId, 30)
      return
    }
    songs.value = []
    const resp = await discoverApi.recommendPlaylistsByMode(
      props.platform,
      props.modeId,
      playlistPage.value,
      PLAYLIST_PAGE_SIZE,
    )
    playlists.value = resp.items
    playlistPage.value = resp.page
    hasMore.value = resp.has_more
  } catch (e: any) {
    toast.error(`加载推荐失败：${e?.message || e}`)
    if (isSongMode.value) songs.value = []
    else playlists.value = []
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

/**
 * 推荐歌单分页：用户点了 Previous / 1 / 2 / Next，跳到目标页并 **替换** 当前列表。
 */
const onPlaylistPageChange = (target: number) => {
  if (loading.value || isSongMode.value) return
  if (target === playlistPage.value) return
  playlistPage.value = target
  loadData()
}

const reload = () => {
  playlistPage.value = 1
  loadData()
}

watch(
  () => [props.platform, props.modeKind, props.modeId] as const,
  () => {
    playlistPage.value = 1
    loadData()
    checkDailySubscribed()
  },
)

onMounted(() => {
  loadData()
  checkDailySubscribed()
})
</script>
