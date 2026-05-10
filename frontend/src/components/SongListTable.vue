<template>
  <MusicCard :padded="false">
    <template #title>
      <div class="p-5 sm:p-6">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 class="text-base font-semibold text-gray-800 dark:text-white/90">歌曲列表</h2>
            <p class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
              共 {{ songs.length }} 首，已选择 {{ checkedKeys.length }} 首。
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <MusicButton
              variant="outline"
              :disabled="checkedKeys.length === 0"
              :loading="batching"
              @click="batchDownload"
            >
              下载选中（{{ checkedKeys.length }}）
            </MusicButton>
            <MusicButton variant="outline" @click="selectAll">全选</MusicButton>
            <MusicButton variant="ghost" @click="checkedKeys = []">清空</MusicButton>
            <MusicButton :loading="bundling" @click="downloadAllAsBundle">
              整体下载（{{ songs.length }} 首）
            </MusicButton>
          </div>
        </div>
      </div>
    </template>

    <div v-if="songs.length" class="overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
        <thead class="bg-gray-50 dark:bg-white/[0.02]">
          <tr>
            <th class="w-12 px-5 py-3 text-left">
              <input
                type="checkbox"
                :checked="allSelected"
                class="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
                aria-label="全选歌曲"
                @change="toggleAll"
              />
            </th>
            <th class="px-5 py-3 text-left text-theme-xs font-medium uppercase text-gray-500 dark:text-gray-400">
              #
            </th>
            <th class="px-5 py-3 text-left text-theme-xs font-medium uppercase text-gray-500 dark:text-gray-400">
              歌曲
            </th>
            <th class="px-5 py-3 text-left text-theme-xs font-medium uppercase text-gray-500 dark:text-gray-400">
              歌手
            </th>
            <th class="px-5 py-3 text-left text-theme-xs font-medium uppercase text-gray-500 dark:text-gray-400">
              时长
            </th>
            <th class="px-5 py-3 text-left text-theme-xs font-medium uppercase text-gray-500 dark:text-gray-400">
              平台
            </th>
            <th class="px-5 py-3 text-right text-theme-xs font-medium uppercase text-gray-500 dark:text-gray-400">
              操作
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 bg-white dark:divide-gray-800 dark:bg-transparent">
          <tr
            v-for="(song, index) in pagedSongs"
            :key="songKey(song)"
            class="transition hover:bg-gray-50 dark:hover:bg-white/[0.03]"
          >
            <td class="px-5 py-4">
              <input
                type="checkbox"
                :checked="checkedKeys.includes(songKey(song))"
                class="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
                :aria-label="`选择 ${song.name}`"
                @change="toggleSong(song)"
              />
            </td>
            <td class="whitespace-nowrap px-5 py-4 text-theme-sm text-gray-500 dark:text-gray-400">
              {{ index + 1 + (page - 1) * pageSize }}
            </td>
            <td class="min-w-[280px] px-5 py-4">
              <div class="flex items-center gap-3">
                <div class="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-gray-100 text-gray-400 dark:bg-gray-800">
                  <img v-if="song.cover_url" :src="song.cover_url" alt="" class="size-full object-cover" />
                  <span v-else>♪</span>
                </div>
                <div class="min-w-0">
                  <p class="truncate text-theme-sm font-medium text-gray-800 dark:text-white/90">
                    {{ song.name }}
                  </p>
                  <p class="mt-0.5 truncate text-theme-xs text-gray-500 dark:text-gray-400">
                    {{ song.album || '未知专辑' }}
                  </p>
                </div>
              </div>
            </td>
            <td class="max-w-[180px] px-5 py-4">
              <p class="truncate text-theme-sm text-gray-700 dark:text-gray-300">
                {{ song.primary_artist || song.artists.join(' / ') || '-' }}
              </p>
            </td>
            <td class="whitespace-nowrap px-5 py-4 text-theme-sm text-gray-600 dark:text-gray-300">
              {{ formatDuration(song.duration_ms) }}
            </td>
            <td class="px-5 py-4">
              <MusicPlatformIcon :platform="song.platform" size="sm" />
            </td>
            <td class="px-5 py-4 text-right">
              <MusicButton size="xs" variant="outline" @click="doDownload(song)">下载</MusicButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="p-5 sm:p-6">
      <MusicEmpty title="暂无歌曲" description="此歌单或专辑还没有可显示的曲目。" />
    </div>

    <div
      v-if="songs.length > pageSize"
      class="flex flex-col gap-3 border-t border-gray-200 px-5 py-4 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between"
    >
      <p class="text-theme-sm text-gray-500 dark:text-gray-400">
        第 {{ page }} / {{ pageCount }} 页
      </p>
      <div class="flex gap-2">
        <MusicButton variant="outline" size="xs" :disabled="page <= 1" @click="page--">上一页</MusicButton>
        <MusicButton variant="outline" size="xs" :disabled="page >= pageCount" @click="page++">下一页</MusicButton>
      </div>
    </div>
  </MusicCard>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { downloadApi, type SongItem } from '@/api'
import MusicBadge from '@/components/music/MusicBadge.vue'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import MusicEmpty from '@/components/music/MusicEmpty.vue'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import { useMusicToast } from '@/components/music/useMusicToast'

const props = defineProps<{
  songs: SongItem[]
  bundle?: {
    type: 'playlist' | 'album'
    platform: 'netease' | 'qq'
    id: string
  }
}>()

const toast = useMusicToast()
const checkedKeys = ref<string[]>([])
const batching = ref(false)
const bundling = ref(false)
const page = ref(1)
const pageSize = 50

const pageCount = computed(() => Math.max(1, Math.ceil(props.songs.length / pageSize)))
const pagedSongs = computed(() => {
  const start = (page.value - 1) * pageSize
  return props.songs.slice(start, start + pageSize)
})
const allSelected = computed(
  () => props.songs.length > 0 && checkedKeys.value.length === props.songs.length,
)

const songKey = (song: SongItem) => `${song.platform}-${song.id}`

const formatDuration = (ms: number) => {
  if (!ms) return '-'
  const total = Math.round(ms / 1000)
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`
}

const selectAll = () => {
  checkedKeys.value = props.songs.map(songKey)
}

const toggleAll = () => {
  if (allSelected.value) checkedKeys.value = []
  else selectAll()
}

const toggleSong = (song: SongItem) => {
  const key = songKey(song)
  if (checkedKeys.value.includes(key)) {
    checkedKeys.value = checkedKeys.value.filter((item) => item !== key)
  } else {
    checkedKeys.value = [...checkedKeys.value, key]
  }
}

const batchDownload = async () => {
  if (checkedKeys.value.length === 0) return
  const grouped: Record<'netease' | 'qq', string[]> = { netease: [], qq: [] }
  for (const key of checkedKeys.value) {
    const row = props.songs.find((song) => songKey(song) === key)
    if (row) grouped[row.platform].push(row.id)
  }
  batching.value = true
  try {
    let total = 0
    for (const platform of ['netease', 'qq'] as const) {
      if (grouped[platform].length === 0) continue
      const result = await downloadApi.songs(platform, grouped[platform])
      total += result.enqueued
    }
    toast.success(`已加入 ${total} 首到下载队列`)
    checkedKeys.value = []
  } catch (e: any) {
    toast.error(`入队失败：${e?.message ?? e}`)
  } finally {
    batching.value = false
  }
}

const downloadAllAsBundle = async () => {
  bundling.value = true
  try {
    if (props.bundle) {
      if (props.bundle.type === 'playlist') {
        const result = await downloadApi.playlist(props.bundle.platform, props.bundle.id)
        toast.success(`歌单已入队：${result.playlist_name}（${result.song_count} 首）`)
      } else {
        const result = await downloadApi.album(props.bundle.platform, props.bundle.id)
        toast.success(`专辑已入队：${result.album_name}（${result.song_count} 首）`)
      }
    } else {
      selectAll()
      await batchDownload()
    }
  } catch (e: any) {
    toast.error(`入队失败：${e?.message ?? e}`)
  } finally {
    bundling.value = false
  }
}

const doDownload = async (song: SongItem) => {
  try {
    await downloadApi.song(song.platform, song.id)
    toast.success(`已加入下载队列：${song.name}`)
  } catch (e: any) {
    toast.error(`入队失败：${e?.message ?? e}`)
  }
}

watch(
  () => props.songs,
  () => {
    checkedKeys.value = []
    page.value = 1
  },
)
</script>
