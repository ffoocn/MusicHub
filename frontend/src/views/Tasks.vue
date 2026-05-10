<template>
  <div class="space-y-6">
    <div class="flex flex-wrap justify-end gap-2">
        <MusicButton variant="outline" :loading="refreshing" @click="refreshTasks">
          <RefreshCw class="size-4" />
          刷新
        </MusicButton>
        <MusicButton
          v-if="selectedRetryableCount"
          variant="outline"
          :loading="retryingSelected"
          @click="retrySelectedTasks"
        >
          <RotateCcw class="size-4" />
          重试选中
        </MusicButton>
        <MusicButton
          v-if="selectedDeletableCount"
          variant="outline"
          @click="openDeleteSelectedConfirm"
        >
          <Trash2 class="size-4" />
          删除选中
        </MusicButton>
        <MusicButton
          v-if="selectedActiveCount"
          variant="outline"
          :loading="cancellingSelected"
          @click="cancelSelectedTasks"
        >
          <Ban class="size-4" />
          取消选中
        </MusicButton>
        <MusicButton
          v-if="activeCount > 0 && store.paused"
          :loading="togglingPause"
          @click="resumeQueue"
        >
          <Play class="size-4" />
          继续队列
        </MusicButton>
        <MusicButton
          v-else-if="activeCount > 0"
          variant="outline"
          :loading="togglingPause"
          @click="pauseQueue"
        >
          <Pause class="size-4" />
          暂停队列
        </MusicButton>
        <MusicButton
          v-if="waitingCount > 0"
          variant="outline"
          @click="showCancelWaitingConfirm = true"
        >
          <Ban class="size-4" />
          全部取消
        </MusicButton>
        <MusicButton
          variant="danger"
          :disabled="!hasFinishedHistory"
          @click="showClearConfirm = true"
        >
          <Trash2 class="size-4" />
          清理历史
        </MusicButton>
    </div>

    <MusicCard :padded="false">
      <div class="border-b border-gray-200 p-5 dark:border-gray-800 sm:p-6">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 class="text-xl font-semibold text-gray-800 dark:text-white/90">Download Activities</h2>
            <p class="mt-1 text-theme-sm font-medium text-gray-500 dark:text-gray-400">
              Track your recent download activities
            </p>
          </div>
          <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div class="flex gap-1 overflow-x-auto rounded-xl bg-gray-100 p-1 dark:bg-gray-800/70">
              <button
                v-for="opt in statusOptions"
                :key="opt.value"
                type="button"
                :class="[
                  'inline-flex shrink-0 items-center rounded-lg px-4 py-2 text-theme-sm font-semibold transition',
                  filterStatus === opt.value
                    ? 'bg-white text-gray-900 shadow-theme-xs dark:bg-gray-900 dark:text-white'
                    : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white/90',
                ]"
                @click="setFilter(opt.value)"
              >
                {{ opt.label }}
              </button>
            </div>
            <div class="relative">
              <SlidersHorizontal class="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-gray-500 dark:text-gray-400" />
              <select
                v-model="filterTarget"
                class="h-11 appearance-none rounded-xl border border-gray-300 bg-white pl-12 pr-10 text-theme-sm font-semibold text-gray-700 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
              >
                <option v-for="opt in targetOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div v-if="pagedTasks.length" class="overflow-x-auto">
        <table class="min-w-[1020px] table-fixed divide-y divide-gray-200 dark:divide-gray-800">
          <colgroup>
            <col class="w-[48px]" />
            <col class="w-[82px]" />
            <col class="w-[33%]" />
            <col class="w-[82px]" />
            <col class="w-[150px]" />
            <col class="w-[170px]" />
            <col class="w-[130px]" />
            <col class="w-[96px]" />
          </colgroup>
          <thead class="bg-gray-50 dark:bg-white/[0.02]">
            <tr>
              <th class="px-3 py-3 text-left">
                <input
                  type="checkbox"
                  :checked="pageSelected"
                  :indeterminate.prop="pagePartiallySelected"
                  class="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
                  aria-label="全选当前页任务"
                  @change="togglePageSelection"
                />
              </th>
              <th
                v-for="column in sortableColumns"
                :key="column.key"
                class="px-3 py-3 text-left"
              >
                <button
                  type="button"
                  class="inline-flex items-center gap-1 text-theme-xs font-medium uppercase text-gray-500 transition hover:text-gray-800 dark:text-gray-400 dark:hover:text-white/90"
                  @click="toggleSort(column.key)"
                >
                  {{ column.label }}
                  <component :is="sortIcon(column.key)" class="size-3.5" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 bg-white dark:divide-gray-800 dark:bg-transparent">
            <tr
              v-for="task in pagedTasks"
              :key="task.id"
              class="transition hover:bg-gray-50 dark:hover:bg-white/[0.03]"
            >
              <td class="px-3 py-3">
                <input
                  type="checkbox"
                  :checked="selectedTaskIds.includes(task.id)"
                  class="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
                  :aria-label="`选择任务 ${task.title || task.id}`"
                  @change="toggleTaskSelection(task.id)"
                />
              </td>
              <td class="whitespace-nowrap px-3 py-3 text-theme-sm font-semibold text-gray-700 dark:text-gray-300">
                #{{ task.id }}
              </td>
              <td class="px-3 py-3">
                <div class="flex items-center gap-2.5">
                  <div class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800">
                    <img v-if="task.cover_url" :src="task.cover_url" alt="" class="size-full object-cover" />
                    <component v-else :is="targetIcon(task.target_type)" class="size-5 text-gray-400" />
                  </div>
                  <div class="min-w-0">
                    <div class="flex min-w-0 items-center gap-2">
                      <p class="truncate text-theme-sm font-semibold text-gray-800 dark:text-white/90">
                        {{ task.title || '-' }}
                      </p>
                      <MusicBadge color="gray" className="shrink-0">{{ targetLabel(task.target_type) }}</MusicBadge>
                    </div>
                    <p class="mt-0.5 truncate text-theme-xs text-gray-500 dark:text-gray-400">
                      {{ task.sub_title || task.target_id }}
                    </p>
                    <p
                      v-if="task.error_msg"
                      class="mt-1 line-clamp-1 text-theme-xs text-error-600 dark:text-error-400"
                      :title="task.error_msg"
                    >
                      {{ task.error_msg }}
                    </p>
                  </div>
                </div>
              </td>
              <td class="px-3 py-3">
                <MusicPlatformIcon :platform="task.platform" size="sm" />
              </td>
              <td class="whitespace-nowrap px-3 py-3 text-theme-sm text-gray-600 dark:text-gray-300">
                <div class="font-medium text-gray-700 dark:text-gray-300">{{ relativeTime(task.updated_at || task.created_at) }}</div>
                <div class="mt-0.5 text-theme-xs text-gray-500 dark:text-gray-400">{{ formatDt(task.updated_at || task.created_at) }}</div>
              </td>
              <td class="px-3 py-3">
                <div class="flex items-center justify-between gap-3">
                  <span class="text-theme-sm font-semibold text-gray-700 dark:text-gray-300">
                    {{ progressValue(task) }}%
                  </span>
                  <span v-if="task.total_count" class="text-theme-xs text-gray-500 dark:text-gray-400">
                    {{ task.success_count + task.fail_count + task.skip_count }}/{{ task.total_count }}
                  </span>
                </div>
                <MusicProgressBar class="mt-2" :value="progressValue(task)" :color="progressColor(task.status)" />
              </td>
              <td class="whitespace-nowrap px-3 py-3 text-theme-sm text-gray-600 dark:text-gray-300">
                <div class="font-medium text-gray-700 dark:text-gray-300">{{ qualityLabel(task) }}</div>
                <div class="mt-0.5 text-theme-xs text-gray-500 dark:text-gray-400">{{ formatSize(task.file_size) }}</div>
              </td>
              <td class="px-3 py-3">
                <MusicBadge :color="statusColor(task.status)" className="min-w-16">
                  {{ statusLabel[task.status] || task.status }}
                </MusicBadge>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="p-5 sm:p-6">
        <MusicEmpty title="暂无任务" description="新的下载任务创建后，会在这里显示队列和进度。" />
      </div>

      <div
        v-if="filteredTasks.length > pageSize"
        class="flex flex-col gap-3 border-t border-gray-200 px-5 py-4 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between"
      >
        <p class="text-theme-sm text-gray-500 dark:text-gray-400">
          第 {{ currentPage }} / {{ totalPages }} 页，共 {{ filteredTasks.length }} 条
          <span v-if="selectedTaskIds.length">，已选择 {{ selectedTaskIds.length }} 条</span>
        </p>
        <div class="flex gap-2">
          <MusicButton variant="outline" size="xs" :disabled="currentPage <= 1" @click="currentPage--">上一页</MusicButton>
          <MusicButton variant="outline" size="xs" :disabled="currentPage >= totalPages" @click="currentPage++">下一页</MusicButton>
        </div>
      </div>
    </MusicCard>

    <MusicConfirmDialog
      :open="showClearConfirm"
      title="清理历史任务"
      message="将从数据库中删除成功、已存在、失败、已取消的任务记录，不会删除本地音乐文件。"
      tone="danger"
      confirmText="清理"
      :loading="clearing"
      @close="showClearConfirm = false"
      @confirm="clearFinished"
    />
    <MusicConfirmDialog
      :open="showCancelWaitingConfirm"
      title="全部取消排队任务"
      :message="`将取消 ${waitingCount} 个尚未开始的任务。运行中的下载不会被中断。`"
      tone="danger"
      confirmText="全部取消"
      :loading="cancellingWaiting"
      @close="showCancelWaitingConfirm = false"
      @confirm="cancelWaitingTasks"
    />
    <MusicConfirmDialog
      :open="showDeleteSelectedConfirm"
      title="删除选中任务"
      :message="deleteSelectedMessage"
      tone="danger"
      confirmText="删除"
      :loading="deletingSelected"
      @close="showDeleteSelectedConfirm = false"
      @confirm="deleteSelectedTasks"
    >
      <label
        v-if="selectedDownloadedCount"
        class="mt-4 flex cursor-pointer select-none items-start gap-3 rounded-xl border border-gray-200 bg-gray-50 p-3 text-theme-sm text-gray-700 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-300"
      >
        <input
          v-model="deleteLocalFiles"
          type="checkbox"
          class="mt-0.5 size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
        />
        <span>
          同时删除本地歌曲
          <span class="mt-0.5 block text-theme-xs text-gray-500 dark:text-gray-400">
            会删除已下载文件，并从本地曲库移除对应歌曲。
          </span>
        </span>
      </label>
    </MusicConfirmDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Album,
  Ban,
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  FolderDown,
  ListMusic,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  SlidersHorizontal,
  Trash2,
} from 'lucide-vue-next'
import { useTasksStore } from '@/stores/tasks'
import { type DownloadTaskItem } from '@/api'
import MusicBadge from '@/components/music/MusicBadge.vue'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import MusicConfirmDialog from '@/components/music/MusicConfirmDialog.vue'
import MusicEmpty from '@/components/music/MusicEmpty.vue'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import MusicProgressBar from '@/components/music/MusicProgressBar.vue'
import { useMusicToast } from '@/components/music/useMusicToast'

const store = useTasksStore()
const message = useMusicToast()
const filterStatus = ref<string>('all')
const filterTarget = ref<string>('all')
const showClearConfirm = ref(false)
const showCancelWaitingConfirm = ref(false)
const showDeleteSelectedConfirm = ref(false)
const refreshing = ref(false)
const clearing = ref(false)
const cancellingWaiting = ref(false)
const cancellingSelected = ref(false)
const deletingSelected = ref(false)
const retryingSelected = ref(false)
const togglingPause = ref(false)
const deleteLocalFiles = ref(false)
const pageSize = 30
const currentPage = ref(1)
const selectedTaskIds = ref<number[]>([])

type SortKey = 'id' | 'track' | 'platform' | 'updated' | 'progress' | 'quality' | 'status'

const sortKey = ref<SortKey>('id')
const sortDirection = ref<'asc' | 'desc'>('desc')

const sortableColumns: Array<{ label: string; key: SortKey }> = [
  { label: 'Task ID', key: 'id' },
  { label: 'Track', key: 'track' },
  { label: 'Platform', key: 'platform' },
  { label: 'Updated', key: 'updated' },
  { label: 'Progress', key: 'progress' },
  { label: 'Quality', key: 'quality' },
  { label: 'Status', key: 'status' },
]

const statusOptions = [
  { label: '全部', value: 'all' },
  { label: '排队中', value: 'queued' },
  { label: '运行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '已存在', value: 'skipped_dup' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' },
]

const targetOptions = [
  { label: '全部类型', value: 'all' },
  { label: '单曲', value: 'song' },
  { label: '歌单', value: 'playlist' },
  { label: '专辑', value: 'album' },
]

const statusLabel: Record<string, string> = {
  queued: '排队中',
  pending: '排队中',
  running: '下载中',
  success: '成功',
  failed: '失败',
  skipped_dup: '已存在',
  cancelled: '已取消',
}

const waitingCount = computed(() => (store.summary.queued || 0) + (store.summary.pending || 0))
const activeCount = computed(() => waitingCount.value + (store.summary.running || 0))
const finishedCount = computed(
  () =>
    (store.summary.success || 0) +
    (store.summary.failed || 0) +
    (store.summary.skipped_dup || 0) +
    (store.summary.cancelled || 0),
)

const countOf = (status: string) => {
  if (status === 'all') return store.allTasks.length
  return store.summary[status] || 0
}

const filteredTasks = computed(() => {
  const rows = store.allTasks.filter((t) => {
    if (filterStatus.value !== 'all' && t.status !== filterStatus.value) return false
    if (filterTarget.value !== 'all' && t.target_type !== filterTarget.value) return false
    return true
  })
  return rows.sort((a, b) => {
    const left = sortValue(a, sortKey.value)
    const right = sortValue(b, sortKey.value)
    const result =
      typeof left === 'number' && typeof right === 'number'
        ? left - right
        : String(left).localeCompare(String(right), 'zh-CN')
    return sortDirection.value === 'asc' ? result : -result
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredTasks.value.length / pageSize)))
const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})

const hasFinishedHistory = computed(() => finishedCount.value > 0)
const selectedTasks = computed(() => {
  const ids = new Set(selectedTaskIds.value)
  return store.allTasks.filter((task) => ids.has(task.id))
})
const selectedActiveTasks = computed(() =>
  selectedTasks.value.filter((task) => task.status === 'queued' || task.status === 'pending' || task.status === 'running'),
)
const selectedDeletableTasks = computed(() =>
  selectedTasks.value.filter((task) => ['success', 'skipped_dup', 'failed', 'cancelled'].includes(task.status)),
)
const selectedRetryableTasks = computed(() =>
  selectedTasks.value.filter((task) => task.status === 'failed' || task.status === 'cancelled'),
)
const selectedDownloadedTasks = computed(() =>
  selectedTasks.value.filter((task) => task.status === 'success' || task.status === 'skipped_dup'),
)
const selectedActiveCount = computed(() => selectedActiveTasks.value.length)
const selectedDeletableCount = computed(() => selectedDeletableTasks.value.length)
const selectedRetryableCount = computed(() => selectedRetryableTasks.value.length)
const selectedDownloadedCount = computed(() => selectedDownloadedTasks.value.length)
const deleteSelectedMessage = computed(() => {
  const count = selectedDeletableCount.value
  const downloaded = selectedDownloadedCount.value
  if (downloaded) return `将删除 ${count} 条任务记录，其中 ${downloaded} 条有关联的本地歌曲。`
  return `将删除 ${count} 条任务记录。`
})
const pageSelected = computed(
  () => pagedTasks.value.length > 0 && pagedTasks.value.every((task) => selectedTaskIds.value.includes(task.id)),
)
const pagePartiallySelected = computed(
  () => pagedTasks.value.some((task) => selectedTaskIds.value.includes(task.id)) && !pageSelected.value,
)

const setFilter = (status: string) => {
  filterStatus.value = status
  currentPage.value = 1
}

const toggleSort = (key: SortKey) => {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = key
  sortDirection.value = key === 'id' || key === 'updated' || key === 'progress' ? 'desc' : 'asc'
}

const sortIcon = (key: SortKey) => {
  if (sortKey.value !== key) return ChevronsUpDown
  return sortDirection.value === 'asc' ? ChevronUp : ChevronDown
}

const statusColor = (status: string) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'info'
  if (status === 'queued' || status === 'pending') return 'brand'
  if (status === 'skipped_dup') return 'warning'
  return 'gray'
}

const progressColor = (status: string) => {
  if (status === 'success' || status === 'skipped_dup') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'queued' || status === 'pending') return 'warning'
  if (status === 'running') return 'info'
  return 'brand'
}

const targetLabel = (targetType: string) => {
  if (targetType === 'playlist') return '歌单'
  if (targetType === 'album') return '专辑'
  return '单曲'
}

const targetIcon = (targetType: string) => {
  if (targetType === 'playlist') return ListMusic
  if (targetType === 'album') return Album
  return FolderDown
}

const progressValue = (task: DownloadTaskItem) => Math.round(Math.max(0, Math.min(1, task.progress || 0)) * 100)

const formatSize = (bytes: number | null) => {
  if (!bytes) return '-'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

const qualityLabel = (task: DownloadTaskItem) => {
  if (!task.audio_format) return '-'
  const bitKbps = task.bitrate ? Math.round(task.bitrate / 1000) : null
  return `${task.audio_format.toUpperCase()}${bitKbps ? ` · ${bitKbps}k` : ''}`
}

const sortValue = (task: DownloadTaskItem, key: SortKey) => {
  if (key === 'id') return task.id
  if (key === 'track') return `${task.title || ''} ${task.sub_title || ''}`
  if (key === 'platform') return task.platform
  if (key === 'updated') return parseTaskTime(task.updated_at || task.created_at)?.getTime() || 0
  if (key === 'progress') return progressValue(task)
  if (key === 'quality') return `${task.audio_format || ''} ${task.bitrate || 0} ${task.file_size || 0}`
  return statusLabel[task.status] || task.status
}

const parseTaskTime = (s: string | null) => {
  if (!s) return null
  const value = /(?:Z|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const formatDt = (s: string | null) => {
  const date = parseTaskTime(s)
  if (!date) return '-'
  return date.toLocaleString('zh-CN')
}

const relativeTime = (s: string | null) => {
  const date = parseTaskTime(s)
  if (!date) return '-'
  const t = date.getTime()
  const diff = Date.now() - t
  if (diff < 0) return '刚刚'
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec} 秒前`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return date.toLocaleDateString('zh-CN')
}

const toggleTaskSelection = (taskId: number) => {
  if (selectedTaskIds.value.includes(taskId)) {
    selectedTaskIds.value = selectedTaskIds.value.filter((id) => id !== taskId)
    return
  }
  selectedTaskIds.value = [...selectedTaskIds.value, taskId]
}

const togglePageSelection = () => {
  const ids = pagedTasks.value.map((task) => task.id)
  if (pageSelected.value) {
    selectedTaskIds.value = selectedTaskIds.value.filter((id) => !ids.includes(id))
    return
  }
  selectedTaskIds.value = Array.from(new Set([...selectedTaskIds.value, ...ids]))
}

const openDeleteSelectedConfirm = () => {
  deleteLocalFiles.value = false
  showDeleteSelectedConfirm.value = true
}

const refreshTasks = async () => {
  refreshing.value = true
  try {
    await store.refresh()
  } finally {
    refreshing.value = false
  }
}

const pauseQueue = async () => {
  togglingPause.value = true
  try {
    await store.pauseQueue()
    message.success('队列已暂停，运行中的任务会自然完成')
  } catch (e: any) {
    message.error(`暂停失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    togglingPause.value = false
  }
}

const resumeQueue = async () => {
  togglingPause.value = true
  try {
    await store.resumeQueue()
    await store.refresh()
    message.success('队列已继续')
  } catch (e: any) {
    message.error(`继续失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    togglingPause.value = false
  }
}

const cancelWaitingTasks = async () => {
  cancellingWaiting.value = true
  try {
    await store.cancelWaiting()
    showCancelWaitingConfirm.value = false
    message.success('已取消所有未开始任务')
  } catch (e: any) {
    message.error(`全部取消失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    cancellingWaiting.value = false
  }
}

const cancelSelectedTasks = async () => {
  cancellingSelected.value = true
  try {
    await store.cancelSelected(selectedActiveTasks.value.map((task) => task.id))
    selectedTaskIds.value = []
    message.success('已取消未开始的选中任务')
  } catch (e: any) {
    message.error(`取消失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    cancellingSelected.value = false
  }
}

const retrySelectedTasks = async () => {
  retryingSelected.value = true
  try {
    await store.retrySelected(selectedRetryableTasks.value.map((task) => task.id))
    selectedTaskIds.value = []
    message.success('已重新加入下载队列')
  } catch (e: any) {
    message.error(`重试失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    retryingSelected.value = false
  }
}

const deleteSelectedTasks = async () => {
  deletingSelected.value = true
  try {
    await store.deleteSelected(
      selectedDeletableTasks.value.map((task) => task.id),
      deleteLocalFiles.value,
    )
    selectedTaskIds.value = []
    showDeleteSelectedConfirm.value = false
    message.success(deleteLocalFiles.value ? '已删除任务和本地歌曲' : '已删除任务记录')
  } catch (e: any) {
    message.error(`删除失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    deletingSelected.value = false
  }
}

const clearFinished = async () => {
  clearing.value = true
  try {
    for (const status of ['success', 'skipped_dup', 'failed', 'cancelled']) {
      await store.clearTaskByStatus(status)
    }
    showClearConfirm.value = false
  } finally {
    clearing.value = false
  }
}

watch([filteredTasks, filterTarget], () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

watch([filterStatus, filterTarget], () => {
  currentPage.value = 1
})

onMounted(() => {
  store.refresh()
})
</script>
