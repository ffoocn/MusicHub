<template>
  <div class="grid grid-cols-12 gap-6">

    <!-- =================== Section 1：All Media =================== -->
    <div class="col-span-12 rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="px-4 py-4 sm:pl-6 sm:pr-4">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">本地音频</h3>
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div class="relative">
            <Search class="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-gray-500 dark:text-gray-400" />
            <input
              v-model="q"
              type="search"
              placeholder="Search..."
              class="h-11 w-full rounded-lg border border-gray-300 bg-transparent py-2.5 pl-[42px] pr-3.5 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 xl:w-[300px]"
              @keyup.enter="applyFilters"
            />
          </div>
          <button
            type="button"
            class="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-3 text-sm font-medium text-white shadow-theme-xs transition hover:bg-brand-600 disabled:opacity-60 sm:w-auto"
            :disabled="loading"
            @click="reloadAll"
          >
            <Plus class="size-5" />
            <span>刷新</span>
          </button>
        </div>
      </div>
      </div>

      <div class="border-t border-gray-100 p-4 dark:border-gray-800 sm:p-6">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6 xl:grid-cols-3">
        <div
          v-for="cat in mediaCards"
          :key="cat.label"
          class="flex items-center justify-between rounded-2xl border border-gray-100 bg-white py-4 pl-4 pr-4 dark:border-gray-800 dark:bg-white/[0.03] xl:pr-5"
        >
          <div class="flex min-w-0 items-center gap-4">
            <span :class="['flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-xl', cat.iconBg]">
              <component :is="cat.icon" :class="['size-5', cat.iconColor]" />
            </span>
            <div class="min-w-0">
              <h4 class="mb-1 truncate text-sm font-medium text-gray-800 dark:text-white/90">{{ cat.label }}</h4>
              <span class="block text-sm text-gray-500 dark:text-gray-400">{{ cat.pct }}% 占比</span>
            </div>
          </div>
          <div class="shrink-0 pl-3">
            <span class="mb-1 block text-right text-sm text-gray-500 dark:text-gray-400">{{ cat.count }} 首</span>
            <span class="block text-right text-sm text-gray-500 dark:text-gray-400">{{ cat.size }}</span>
          </div>
        </div>
      </div>
      </div>
    </div>

    <!-- =================== Section 2：All Folders + Storage Details =================== -->
    <div class="col-span-12 grid grid-cols-12 gap-6">

      <!-- 最新下载的歌手 -->
      <div class="col-span-12 rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03] xl:col-span-8">
        <div class="px-4 py-4 sm:pl-6 sm:pr-4">
        <div class="flex flex-col gap-1">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">最新下载的歌手</h3>
          <p class="text-sm text-gray-500 dark:text-gray-400">展示最近下载内容中出现的歌手概览。</p>
        </div>
        </div>
        <div class="border-t border-gray-100 p-5 dark:border-gray-800 sm:p-6">
        <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-6">
          <div
            v-for="folder in folderCards"
            :key="folder.key"
            class="rounded-2xl border border-gray-100 bg-gray-50 px-6 py-6 dark:border-gray-800 dark:bg-white/[0.03] xl:py-[27px]"
          >
            <div class="mb-6 flex justify-between">
              <div class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-warning-100 text-warning-500 dark:bg-warning-500/15">
                <img
                  v-if="folder.coverUrl"
                  :src="folder.coverUrl"
                  alt=""
                  class="size-full object-cover"
                  @error="onCoverError($event)"
                />
                <span v-else class="text-sm font-semibold text-gray-500 dark:text-gray-400">
                  {{ initial(folder.name) }}
                </span>
              </div>
            </div>
            <h4 class="mb-1 truncate text-sm font-medium text-gray-800 dark:text-white/90">{{ folder.name }}</h4>
            <div class="flex items-center justify-between gap-2">
              <span class="block text-sm text-gray-500 dark:text-gray-400">{{ folder.count }} 首</span>
              <span class="block text-right text-sm text-gray-500 dark:text-gray-400">{{ folder.size }}</span>
            </div>
          </div>
          <div v-if="!folderCards.length" class="col-span-2 py-8 text-center text-sm text-gray-400">
            暂无歌手数据
          </div>
        </div>
        </div>
      </div>

      <!-- Storage Details -->
      <div class="col-span-12 rounded-2xl border border-gray-200 bg-white px-4 pb-6 pt-6 dark:border-gray-800 dark:bg-white/[0.03] sm:px-6 xl:col-span-4">
        <div class="mb-4 flex items-start justify-between">
          <div>
            <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">存储详情</h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ totalSizeText }} 已占用</p>
          </div>
        </div>

        <div class="relative flex items-center justify-center">
          <svg viewBox="0 0 120 120" class="h-[260px] w-[260px] -rotate-90 sm:h-[300px] sm:w-[300px] xl:h-[320px] xl:w-[320px]">
            <circle
              cx="60"
              cy="60"
              r="48"
              fill="none"
              stroke-width="14"
              class="stroke-gray-100 dark:stroke-gray-800"
            />
            <circle
              v-for="seg in donutSegments"
              :key="seg.label"
              cx="60"
              cy="60"
              r="48"
              fill="none"
              stroke-width="14"
              stroke-linecap="butt"
              :stroke="seg.color"
              :stroke-dasharray="`${seg.length} ${donutCircumference}`"
              :stroke-dashoffset="-seg.offset"
            />
          </svg>
          <div class="absolute inset-0 flex flex-col items-center justify-center text-center">
            <p class="text-sm text-gray-500 dark:text-gray-400">总大小</p>
            <p class="mt-1 text-2xl font-bold text-gray-800 dark:text-white/90">{{ totalSizeText }}</p>
            <p class="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{{ data?.total_songs || 0 }} 首</p>
          </div>
        </div>

        <div class="mt-2 flex flex-wrap items-center justify-start gap-x-5 gap-y-3">
          <div v-for="seg in donutLegend" :key="seg.label" class="flex items-center gap-2">
            <span class="size-2 shrink-0 rounded-full" :style="{ background: seg.color }"></span>
            <p class="text-sm text-gray-700 dark:text-gray-300">{{ seg.label }}</p>
          </div>
          <p v-if="!donutLegend.length" class="text-xs text-gray-400">暂无格式数据</p>
        </div>
      </div>

    </div>

    <!-- =================== Section 3：Recent Files =================== -->
    <div class="col-span-12 overflow-hidden rounded-2xl border border-gray-200 bg-white pt-4 dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="mb-4 flex items-center justify-between px-6">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">最近添加</h3>
        <div class="flex items-center gap-3">
          <button
            v-if="selectedCount > 0"
            type="button"
            class="inline-flex h-9 items-center gap-2 rounded-lg border border-error-200 bg-error-50 px-3 text-sm font-medium text-error-600 transition hover:bg-error-100 disabled:opacity-60 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-400 dark:hover:bg-error-500/15"
            :disabled="batchDeleting"
            @click="confirmDeleteSelected"
          >
            <Trash2 class="size-4" />
            删除选中（{{ selectedCount }}）
          </button>
          <select
            v-model="sort"
            class="h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
            @change="applyFilters"
          >
            <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>

      <div v-if="loadingSongs && !rows.length" class="space-y-2 px-5 pb-5 sm:px-6 sm:pb-6">
        <div v-for="idx in pageSize" :key="idx" class="h-12 animate-pulse rounded-lg bg-gray-100 dark:bg-white/5"></div>
      </div>

      <div v-else-if="rows.length" class="max-w-full overflow-x-auto">
        <table class="w-full table-auto border-collapse">
          <thead>
            <tr class="border-t border-gray-200 text-left dark:border-gray-800">
              <th class="w-12 px-6 py-3">
                <input
                  type="checkbox"
                  :checked="allPageSelected"
                  class="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
                  aria-label="选择当前页全部歌曲"
                  @change="toggleAllRows"
                />
              </th>
              <th class="px-6 py-3 text-theme-sm font-medium text-gray-500 dark:text-gray-400">歌曲名</th>
              <th class="px-6 py-3 text-theme-sm font-medium text-gray-500 dark:text-gray-400">格式</th>
              <th class="px-6 py-3 text-theme-sm font-medium text-gray-500 dark:text-gray-400">大小</th>
              <th class="px-6 py-3 text-theme-sm font-medium text-gray-500 dark:text-gray-400">添加时间</th>
              <th class="px-6 py-3 text-center text-theme-sm font-medium text-gray-500 dark:text-gray-400">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id" class="border-t border-gray-100 transition hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-white/[0.02]">
              <td class="px-6 py-[18px]">
                <input
                  type="checkbox"
                  :checked="isSelected(row.id)"
                  class="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
                  :aria-label="`选择 ${row.name}`"
                  @change="toggleRow(row.id)"
                />
              </td>
              <td class="min-w-[260px] px-6 py-[18px] text-sm text-gray-700 dark:text-gray-400">
                <div class="flex items-center gap-3">
                  <div class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 text-gray-400 dark:bg-gray-800">
                    <img
                      v-if="row.has_cover"
                      :src="coverUrlOf(row.id)"
                      alt=""
                      class="size-full object-cover"
                      @error="onCoverError($event)"
                    />
                    <FileMusic v-else class="size-4" />
                  </div>
                  <div class="min-w-0">
                    <p class="truncate text-sm font-medium text-gray-800 dark:text-white/90">{{ row.name }}</p>
                    <p class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">{{ row.artist || '未知歌手' }}</p>
                  </div>
                </div>
              </td>
              <td class="whitespace-nowrap px-6 py-[18px] text-theme-sm text-gray-700 dark:text-gray-400">{{ formatAudio(row) }}</td>
              <td class="whitespace-nowrap px-6 py-[18px] text-theme-sm text-gray-700 dark:text-gray-400">{{ formatSize(row.file_size) }}</td>
              <td class="whitespace-nowrap px-6 py-[18px] text-theme-sm text-gray-700 dark:text-gray-400">{{ formatDate(row.created_at) }}</td>
              <td class="px-6 py-[18px] text-center">
                <div class="inline-flex items-center justify-center gap-2">
                  <button
                    type="button"
                    class="rounded-md p-1.5 text-gray-400 transition hover:bg-error-50 hover:text-error-500 dark:hover:bg-error-500/15 dark:hover:text-error-400"
                    title="删除"
                    @click="confirmDelete(row)"
                  >
                    <Trash2 class="size-4" />
                  </button>
                  <button
                    type="button"
                    class="rounded-md p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-white/5 dark:hover:text-white"
                    title="播放"
                    @click="playLocal(row)"
                  >
                    <Eye class="size-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="px-5 pb-8 sm:px-6">
        <MusicEmpty title="没有匹配的歌曲" description="换个关键词或清空筛选条件再试。" />
      </div>

      <div class="space-y-3 border-t border-gray-100 px-5 py-4 dark:border-gray-800 sm:px-6">
        <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <p class="text-sm text-gray-500 dark:text-gray-400">
            共 {{ total }} 首，当前第 {{ page }} / {{ pageCount }} 页
          </p>
          <p v-if="selectedCount > 0" class="text-sm text-gray-500 dark:text-gray-400">
            已选择 {{ selectedCount }} 首
          </p>
        </div>
        <MusicPagination
          :current-page="page"
          :total-pages="pageCount"
          :loading="loadingSongs || batchDeleting"
          :siblings="1"
          @change="goPage"
        />
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import {
  ArrowRight,
  Disc3,
  Eye,
  FileAudio,
  FileMusic,
  Headphones,
  Music,
  Plus,
  Radio,
  Search,
  Sparkles,
  Trash2,
} from 'lucide-vue-next'
import { libraryApi, statsApi, type LibrarySong, type StatsOverview } from '@/api'
import { usePlayerStore } from '@/stores/player'
import MusicPagination from '@/components/music/MusicPagination.vue'
import MusicEmpty from '@/components/music/MusicEmpty.vue'
import { useMusicToast } from '@/components/music/useMusicToast'

// ===== fmt =====
const formatSize = (b?: number | null) => {
  if (!b) return '-'
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}
const formatTotalSize = (b: number) => {
  if (!b) return '0 B'
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`
}
const formatAudio = (row: LibrarySong) => {
  if (!row.audio_format) return '-'
  const k = row.bitrate ? Math.round(row.bitrate / 1000) : null
  return `${row.audio_format.toUpperCase()}${k ? ` · ${k}k` : ''}`
}
const formatDate = (s: string) => {
  if (!s) return '-'
  const d = new Date(s)
  if (isNaN(d.getTime())) return s
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
const initial = (s: string) => (s || '?').trim().slice(0, 1).toUpperCase()
const coverUrlOf = (id: number) => libraryApi.coverUrl(id)
const onCoverError = (e: Event) => {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

// ===== state =====
const player = usePlayerStore()
const toast = useMusicToast()
const data = ref<StatsOverview | null>(null)
const loading = ref(false)
const loadingSongs = ref(false)
const batchDeleting = ref(false)

const q = ref('')
const sort = ref<'latest' | 'name' | 'duration'>('latest')
const rows = ref<LibrarySong[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 8                       // 限制下高度，对齐原版
const selectedIds = ref<Set<number>>(new Set())

const sortOptions = [
  { label: '最新优先', value: 'latest' },
  { label: '按歌名', value: 'name' },
  { label: '按时长', value: 'duration' },
] as const

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const selectedCount = computed(() => selectedIds.value.size)
const allPageSelected = computed(
  () => rows.value.length > 0 && rows.value.every((row) => selectedIds.value.has(row.id)),
)

// 用于导出"最新下载的歌手"和卡片头像（独立于分页/筛选）
const recentSongs = ref<LibrarySong[]>([])

// ===== load =====
const loadSongs = async () => {
  loadingSongs.value = true
  try {
    const r = await libraryApi.songs({
      q: q.value || undefined,
      sort: sort.value,
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    })
    rows.value = r.items
    total.value = r.total
    selectedIds.value = new Set([...selectedIds.value].filter((id) => r.items.some((row) => row.id === id)))
  } catch {
    rows.value = []
    total.value = 0
    selectedIds.value = new Set()
  } finally {
    loadingSongs.value = false
  }
}
const loadStats = async () => {
  try {
    data.value = await statsApi.overview()
  } catch {
    data.value = null
  }
}
const loadRecentForArtists = async () => {
  try {
    const r = await libraryApi.songs({ sort: 'latest', limit: 30 })
    recentSongs.value = r.items
  } catch {
    recentSongs.value = []
  }
}
const reloadAll = async () => {
  loading.value = true
  await Promise.all([loadStats(), loadSongs(), loadRecentForArtists()])
  loading.value = false
}
const applyFilters = async () => {
  page.value = 1
  selectedIds.value = new Set()
  await loadSongs()
}
const goPage = async (next: number) => {
  page.value = Math.max(1, Math.min(pageCount.value, next))
  selectedIds.value = new Set()
  await loadSongs()
}
const playLocal = (row: LibrarySong) => player.playLocal(row)

const isSelected = (id: number) => selectedIds.value.has(id)
const toggleRow = (id: number) => {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}
const toggleAllRows = () => {
  if (allPageSelected.value) {
    selectedIds.value = new Set()
    return
  }
  selectedIds.value = new Set(rows.value.map((row) => row.id))
}

const confirmDelete = async (row: LibrarySong) => {
  if (!window.confirm(`确定删除「${row.name}」？文件和库记录都会移除。`)) return
  try {
    await libraryApi.deleteSong(row.id)
    const next = new Set(selectedIds.value)
    next.delete(row.id)
    selectedIds.value = next
    toast.success(`已删除：${row.name}`)
    await Promise.all([loadStats(), loadSongs(), loadRecentForArtists()])
  } catch (e: any) {
    toast.error(`删除失败：${e?.response?.data?.detail || e?.message || e}`)
  }
}

const confirmDeleteSelected = async () => {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!window.confirm(`确定删除选中的 ${ids.length} 首歌曲？文件和库记录都会移除。`)) return
  batchDeleting.value = true
  const failed: string[] = []
  try {
    for (const id of ids) {
      const row = rows.value.find((item) => item.id === id)
      try {
        await libraryApi.deleteSong(id)
      } catch (e: any) {
        failed.push(row?.name || String(id))
      }
    }
    const deletedCount = ids.length - failed.length
    if (rows.value.length <= deletedCount && page.value > 1) page.value -= 1
    selectedIds.value = new Set()
    await Promise.all([loadStats(), loadSongs(), loadRecentForArtists()])
    if (failed.length) {
      toast.error(`已删除 ${deletedCount} 首，${failed.length} 首删除失败：${failed.slice(0, 3).join('、')}`)
    } else {
      toast.success(`已删除 ${deletedCount} 首歌曲`)
    }
  } finally {
    batchDeleting.value = false
  }
}

// ===== Section 1: All Media（永远 6 张卡片） =====
interface MediaCard {
  label: string
  count: number
  pct: number
  size: string
  icon: Component
  iconBg: string
  iconColor: string
}

const mediaCards = computed<MediaCard[]>(() => {
  const d = data.value
  if (!d || !d.total_songs) return []
  const totalCount = d.total_songs
  const totalBytes = d.total_size_bytes
  const palette: { iconBg: string; iconColor: string; icon: Component }[] = [
    { iconBg: 'bg-blue-light-50 dark:bg-blue-light-500/15', iconColor: 'text-blue-light-600 dark:text-blue-light-400', icon: Music },
    { iconBg: 'bg-success-50 dark:bg-success-500/15',       iconColor: 'text-success-600 dark:text-success-500',     icon: FileAudio },
    { iconBg: 'bg-warning-50 dark:bg-warning-500/15',       iconColor: 'text-warning-600 dark:text-orange-400',      icon: Disc3 },
    { iconBg: 'bg-error-50 dark:bg-error-500/15',           iconColor: 'text-error-600 dark:text-error-500',         icon: Radio },
    { iconBg: 'bg-brand-50 dark:bg-brand-500/15',           iconColor: 'text-brand-600 dark:text-brand-400',         icon: Headphones },
    { iconBg: 'bg-orange-100 dark:bg-orange-500/15',        iconColor: 'text-orange-600 dark:text-orange-400',       icon: Sparkles },
  ]
  const cards: MediaCard[] = []

  // 1) Top 3 音频格式
  const fmtArr = Object.entries(d.by_format).sort((a, b) => b[1] - a[1])
  fmtArr.slice(0, 3).forEach(([label, count], idx) => {
    const pct = Math.round((count / totalCount) * 100)
    const size = formatTotalSize(Math.round(totalBytes * (count / totalCount)))
    const tone = palette[idx]
    cards.push({
      label: (label || '未知').toUpperCase(),
      count,
      pct,
      size,
      icon: tone.icon,
      iconBg: tone.iconBg,
      iconColor: tone.iconColor,
    })
  })

  // 2) 含封面
  cards.push({
    label: '含封面',
    count: d.has_cover,
    pct: Math.round((d.has_cover / totalCount) * 100),
    size: formatTotalSize(Math.round(totalBytes * (d.has_cover / totalCount))),
    icon: palette[3].icon,
    iconBg: palette[3].iconBg,
    iconColor: palette[3].iconColor,
  })

  // 3) 含歌词
  cards.push({
    label: '含歌词',
    count: d.has_lyric,
    pct: Math.round((d.has_lyric / totalCount) * 100),
    size: formatTotalSize(Math.round(totalBytes * (d.has_lyric / totalCount))),
    icon: palette[4].icon,
    iconBg: palette[4].iconBg,
    iconColor: palette[4].iconColor,
  })

  // 4) 无损音质（lossless / hires）凑满第 6 张
  const losslessCount = (d.by_quality?.lossless || 0) + (d.by_quality?.hires || 0)
  cards.push({
    label: '无损音质',
    count: losslessCount,
    pct: Math.round((losslessCount / totalCount) * 100),
    size: formatTotalSize(Math.round(totalBytes * (losslessCount / totalCount))),
    icon: palette[5].icon,
    iconBg: palette[5].iconBg,
    iconColor: palette[5].iconColor,
  })

  return cards.slice(0, 6)
})

// ===== Section 2: 最新下载的歌手（按 created_at 去重 top4） =====
interface FolderCard {
  key: string
  name: string
  count: number
  size: string
  coverUrl: string | null
}
const folderCards = computed<FolderCard[]>(() => {
  const d = data.value
  if (!recentSongs.value.length) return []
  const totalSongs = d?.total_songs || 0
  const totalBytes = d?.total_size_bytes || 0
  const seen = new Map<string, FolderCard>()
  for (const song of recentSongs.value) {
    const name = (song.artist || '未知歌手').trim()
    if (seen.has(name)) {
      const existing = seen.get(name)!
      existing.count += 1
      continue
    }
    seen.set(name, {
      key: name,
      name,
      count: 1,
      size: '',
      coverUrl: song.has_cover ? libraryApi.coverUrl(song.id) : null,
    })
    if (seen.size >= 4) break
  }
  // 估算单歌手占用大小（按比例）
  const arr = Array.from(seen.values())
  arr.forEach((it) => {
    it.size = totalSongs
      ? formatTotalSize(Math.round(totalBytes * (it.count / totalSongs)))
      : '-'
  })
  return arr
})

// ===== Section 2: Storage Details =====
const totalSizeText = computed(() => (data.value ? formatTotalSize(data.value.total_size_bytes) : '0 B'))

const PALETTE = ['#7a5af8', '#fb6514', '#fdb022', '#12b76a', '#36bffa', '#465fff']

interface DonutSeg {
  label: string
  color: string
  length: number
  offset: number
}
const DONUT_R = 48
const donutCircumference = 2 * Math.PI * DONUT_R

const donutLegend = computed(() => {
  const d = data.value
  if (!d) return []
  const arr = Object.entries(d.by_format).sort((a, b) => b[1] - a[1])
  return arr.map(([label], idx) => ({
    label: (label || '未知').toUpperCase(),
    color: PALETTE[idx % PALETTE.length],
  }))
})

const donutSegments = computed<DonutSeg[]>(() => {
  const d = data.value
  if (!d) return []
  const arr = Object.entries(d.by_format).sort((a, b) => b[1] - a[1])
  const total = arr.reduce((s, x) => s + x[1], 0) || 1
  let cum = 0
  return arr.map(([label, count], idx) => {
    const pct = count / total
    const len = pct * donutCircumference
    const seg: DonutSeg = {
      label: (label || '未知').toUpperCase(),
      color: PALETTE[idx % PALETTE.length],
      length: len,
      offset: cum,
    }
    cum += len
    return seg
  })
})

onMounted(reloadAll)
</script>
