<template>
  <MusicCard title="全平台搜索" description="搜索歌曲，试听确认版本后加入下载队列。">
    <!-- 搜索栏 -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative min-w-0 flex-1">
        <span class="pointer-events-none absolute inset-y-0 left-3.5 flex items-center">
          <svg class="h-4 w-4 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z" />
          </svg>
        </span>
        <input
          v-model="keyword"
          type="search"
          placeholder="搜索歌曲（如：周杰伦 晴天）"
          class="h-11 w-full rounded-lg border border-gray-300 bg-transparent py-2.5 pl-10 pr-4 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
          @keyup.enter="doSearch"
        />
      </div>
      <div class="inline-flex shrink-0 rounded-lg border border-gray-200 bg-gray-50 p-1 dark:border-gray-800 dark:bg-white/[0.03]">
        <button
          v-for="p in platformOptions"
          :key="p.value"
          type="button"
          :class="[
            'rounded-md px-3 py-1.5 text-sm font-medium transition',
            platform === p.value
              ? 'bg-white text-brand-600 shadow-theme-xs dark:bg-gray-800 dark:text-brand-400'
              : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
          ]"
          @click="platform = p.value"
        >
          {{ p.label }}
        </button>
      </div>
      <MusicButton :loading="loading" @click="doSearch">搜索</MusicButton>
    </div>

    <!-- 选择栏（仅在有结果时） -->
    <div v-if="items.length" class="mt-4 flex flex-wrap items-center gap-3 border-t border-gray-100 pt-4 dark:border-gray-800">
      <label class="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
        <input
          type="checkbox"
          :checked="allSelected"
          class="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
          @change="toggleAll"
        />
        全选 <span class="text-gray-400 dark:text-gray-500">（共 {{ items.length }} 首）</span>
      </label>
      <span v-if="checkedKeys.length" class="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
        已选 {{ checkedKeys.length }}
      </span>
      <MusicButton
        v-if="checkedKeys.length"
        size="xs"
        class="ml-auto"
        :loading="batching"
        @click="batchDownload"
      >
        批量下载
      </MusicButton>
    </div>

    <!-- 结果列表 -->
    <div class="mt-4">
      <div v-if="loading && !items.length" class="space-y-2">
        <div v-for="idx in 6" :key="idx" class="h-14 animate-pulse rounded-xl bg-gray-100 dark:bg-white/5"></div>
      </div>

      <ul v-else-if="items.length" class="divide-y divide-gray-100 dark:divide-gray-800">
        <li
          v-for="row in items"
          :key="rowKey(row)"
          class="group flex items-center gap-3 py-2.5 transition hover:bg-gray-50/50 dark:hover:bg-white/[0.02]"
        >
          <input
            type="checkbox"
            :checked="checkedKeys.includes(rowKey(row))"
            class="size-4 shrink-0 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
            @change="toggleRow(row)"
          />
          <!-- 封面 -->
          <div class="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 text-gray-400 dark:bg-gray-800">
            <img v-if="row.cover_url" :src="row.cover_url" alt="" class="size-full object-cover" />
            <svg v-else class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M18 3a1 1 0 0 0-1.196-.98l-10 2A1 1 0 0 0 6 5v6.499A3.001 3.001 0 1 0 8 14V8.68l8-1.6V11.5A3.001 3.001 0 1 0 18 13V3Z"/></svg>
          </div>
          <!-- 主文本 -->
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-gray-800 dark:text-white/90">{{ row.name }}</p>
            <div class="mt-0.5 flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
              <MusicPlatformIcon :platform="row.platform" size="xs" />
              <span class="truncate">{{ row.primary_artist || '未知歌手' }}</span>
              <span v-if="row.album || row.album_id" class="text-gray-300 dark:text-gray-600">·</span>
              <button
                v-if="row.album_id"
                type="button"
                class="truncate text-brand-500 hover:text-brand-600 dark:text-brand-400"
                @click="router.push(`/album/${row.platform}/${row.album_id}`)"
              >
                {{ row.album || '查看专辑' }}
              </button>
              <span v-else-if="row.album" class="truncate">{{ row.album }}</span>
            </div>
          </div>
          <!-- 时长 -->
          <span class="hidden shrink-0 text-xs tabular-nums text-gray-500 dark:text-gray-400 sm:inline">
            {{ formatDuration(row.duration_ms) }}
          </span>
          <!-- 操作 -->
          <div class="flex shrink-0 items-center gap-1">
            <MusicButton variant="ghost" size="xs" @click="play(row)">试听</MusicButton>
            <MusicButton size="xs" :loading="downloadingMap[rowKey(row)]" @click="doDownload(row)">下载</MusicButton>
          </div>
        </li>
      </ul>

      <MusicEmpty v-else title="输入关键词搜索歌曲" description="支持网易云和 QQ 音乐并发搜索。" />
    </div>
  </MusicCard>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { discoverApi, downloadApi, type SongItem } from '@/api'
import { usePlayerStore } from '@/stores/player'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import MusicEmpty from '@/components/music/MusicEmpty.vue'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import { useMusicToast } from '@/components/music/useMusicToast'

const router = useRouter()
const route = useRoute()
const player = usePlayerStore()
const toast = useMusicToast()

const keyword = ref('')
const platform = ref<'netease' | 'qq' | 'all'>('all')
const items = ref<SongItem[]>([])
const loading = ref(false)
const downloadingMap = ref<Record<string, boolean>>({})
const checkedKeys = ref<string[]>([])
const batching = ref(false)

const platformOptions = [
  { value: 'all' as const, label: '全部' },
  { value: 'netease' as const, label: '网易云' },
  { value: 'qq' as const, label: 'QQ' },
]

const allSelected = computed(() => items.value.length > 0 && checkedKeys.value.length === items.value.length)
const rowKey = (row: SongItem) => `${row.platform}-${row.id}`
const formatDuration = (ms: number) => {
  if (!ms) return '-'
  const total = Math.round(ms / 1000)
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`
}

const doSearch = async () => {
  const q = keyword.value.trim()
  if (!q) {
    toast.warning('请输入关键词')
    return
  }
  loading.value = true
  checkedKeys.value = []
  try {
    items.value = await discoverApi.search(q, platform.value, 50)
    if (!items.value.length) toast.info('无搜索结果')
  } catch (e: any) {
    toast.error(`搜索失败：${e?.message ?? e}`)
  } finally {
    loading.value = false
  }
}

const toggleAll = () => {
  checkedKeys.value = allSelected.value ? [] : items.value.map(rowKey)
}

const toggleRow = (row: SongItem) => {
  const key = rowKey(row)
  checkedKeys.value = checkedKeys.value.includes(key)
    ? checkedKeys.value.filter((item) => item !== key)
    : [...checkedKeys.value, key]
}

const play = async (row: SongItem) => {
  try {
    await player.playRemote(row.platform, row.id)
  } catch (e: any) {
    toast.error(`试听失败：${e?.response?.data?.detail || e?.message || e}`)
  }
}

const doDownload = async (row: SongItem) => {
  const key = rowKey(row)
  if (downloadingMap.value[key]) return
  downloadingMap.value[key] = true
  try {
    await downloadApi.song(row.platform, row.id)
    toast.success(`已加入下载队列：${row.name}`)
  } catch (e: any) {
    toast.error(`入队失败：${e?.message ?? e}`)
  } finally {
    downloadingMap.value[key] = false
  }
}

/**
 * 当外部（顶栏搜索）通过 URL ?q=... 触发本面板时，把 query 同步到关键词并立即搜索。
 * 仅在 query.q 实际变化时执行，避免在用户清空搜索框后被反复回填。
 */
const syncFromQuery = async () => {
  const q = ((route.query.q as string) || '').trim()
  if (!q) return
  if (q === keyword.value && items.value.length > 0) return
  keyword.value = q
  await doSearch()
}

onMounted(syncFromQuery)
watch(() => route.query.q, syncFromQuery)

const batchDownload = async () => {
  if (checkedKeys.value.length === 0) return
  const grouped: Record<'netease' | 'qq', string[]> = { netease: [], qq: [] }
  for (const key of checkedKeys.value) {
    const row = items.value.find((item) => rowKey(item) === key)
    if (row) grouped[row.platform].push(row.id)
  }
  batching.value = true
  try {
    let total = 0
    for (const p of ['netease', 'qq'] as const) {
      if (!grouped[p].length) continue
      const result = await downloadApi.songs(p, grouped[p])
      total += result.enqueued
    }
    toast.success(`已批量入队 ${total} 首，可在「任务」页查看进度`)
    checkedKeys.value = []
  } catch (e: any) {
    toast.error(`批量入队失败：${e?.message ?? e}`)
  } finally {
    batching.value = false
  }
}
</script>
