<template>
  <!--
    顶栏「通知」铃铛 + 下拉面板。参考 TailAdmin Notification Dropdown：
      - 圆形按钮 + 铃铛 icon + 右上角 ping 红点（仅在有"未读"任务时显示）；
      - 下拉宽 360px，列出最近的下载任务作为通知（最多 6 条），点击跳 /tasks；
      - 红点的"未读"判定：本组件维护 lastSeenTaskId；只要存在 id 大于 lastSeenTaskId 的任务即视为新通知，
        用户打开下拉时把 lastSeenTaskId 抬到当前最大值，红点立即消失。
  -->
  <div class="relative" ref="rootRef">
    <button
      type="button"
      class="relative flex h-11 w-11 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-500 transition hover:bg-gray-100 hover:text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white"
      aria-label="通知"
      @click="toggle"
    >
      <BellIcon />
      <!-- 红点位置 / 大小对齐 TailAdmin 原版：right-0 top-0.5，2x2 ping 圆点 -->
      <span
        v-if="hasUnread"
        class="absolute right-0 top-0.5 z-10 h-2 w-2 rounded-full bg-orange-400"
        aria-hidden="true"
      >
        <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-orange-400 opacity-75"></span>
      </span>
    </button>

    <div
      v-if="open"
      class="absolute right-0 z-9999 mt-3 w-[360px] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark"
    >
      <!-- header -->
      <div class="flex items-center justify-between border-b border-gray-100 px-5 py-3 dark:border-gray-800">
        <h5 class="text-base font-semibold text-gray-800 dark:text-white">通知</h5>
        <button
          type="button"
          class="flex size-7 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-white/[0.04] dark:hover:text-gray-200"
          aria-label="关闭"
          @click="close"
        >
          <svg class="size-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M6.293 6.293a1 1 0 0 1 1.414 0L10 8.586l2.293-2.293a1 1 0 1 1 1.414 1.414L11.414 10l2.293 2.293a1 1 0 0 1-1.414 1.414L10 11.414l-2.293 2.293a1 1 0 0 1-1.414-1.414L8.586 10 6.293 7.707a1 1 0 0 1 0-1.414Z"/>
          </svg>
        </button>
      </div>

      <!-- list -->
      <ul class="max-h-[420px] overflow-y-auto">
        <li
          v-if="!notifications.length"
          class="px-5 py-12 text-center text-theme-sm text-gray-400 dark:text-gray-500"
        >
          暂时没有通知
        </li>

        <li
          v-for="t in notifications"
          :key="t.id"
          class="border-b border-gray-50 last:border-b-0 dark:border-gray-800"
        >
          <router-link
            to="/tasks"
            class="flex gap-3 px-4.5 py-3 transition hover:bg-gray-50 dark:hover:bg-white/[0.02]"
            @click="close"
          >
            <!-- 任务封面 / 默认音乐 icon + 状态色徽章 -->
            <span class="relative flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-gray-100 dark:bg-white/[0.05]">
              <img
                v-if="t.cover_url"
                :src="t.cover_url"
                alt=""
                class="size-full object-cover"
                referrerpolicy="no-referrer"
              />
              <svg v-else class="size-5 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                <path d="M18 3a1 1 0 0 0-1.196-.98l-10 2A1 1 0 0 0 6 5v6.499A3.001 3.001 0 1 0 8 14V8.68l8-1.6V11.5A3.001 3.001 0 1 0 18 13V3Z" />
              </svg>
              <span
                class="absolute -bottom-0.5 -right-0.5 inline-flex size-3.5 items-center justify-center rounded-full bg-white dark:bg-gray-dark"
                aria-hidden="true"
              >
                <span :class="['size-2 rounded-full', STATUS_DOT[t.status] || 'bg-gray-400']"></span>
              </span>
            </span>

            <div class="min-w-0 flex-1">
              <p class="line-clamp-2 text-theme-sm leading-snug text-gray-700 dark:text-gray-300">
                <span class="font-semibold text-gray-800 dark:text-white/90">{{ t.title || '未命名任务' }}</span>
                <span class="text-gray-500 dark:text-gray-400"> · {{ STATUS_LABEL[t.status] || t.status }}</span>
              </p>
              <div class="mt-1 flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
                <MusicPlatformIcon :platform="t.platform" size="xs" />
                <span>{{ targetLabel(t) }}</span>
                <span class="text-gray-300 dark:text-gray-700">·</span>
                <span>{{ formatRelative(t.updated_at || t.created_at) }}</span>
              </div>
            </div>
          </router-link>
        </li>
      </ul>

      <!-- footer -->
      <div class="border-t border-gray-100 px-3 py-2.5 dark:border-gray-800">
        <router-link
          to="/tasks"
          class="block rounded-lg px-3 py-2 text-center text-theme-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.04]"
          @click="close"
        >
          查看全部任务
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 把 tasksStore 暴露的下载任务转成「通知」语义后展示。
 * 子任务（parent_task_id != null）会被过滤掉，避免歌单/专辑展开后塞进上百条通知项。
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { BellIcon } from '@/icons'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import { useTasksStore } from '@/stores/tasks'
import type { DownloadTaskItem } from '@/api'

const tasksStore = useTasksStore()
const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

/**
 * 「上次用户查看过的最大任务 id」。任何 id > lastSeenTaskId 的任务都视为「未读」。
 * 用户每次打开下拉面板就把它抬到当前最大值。
 */
const lastSeenTaskId = ref(0)

const STATUS_LABEL: Record<DownloadTaskItem['status'], string> = {
  queued: '排队中',
  pending: '排队中',
  running: '下载中',
  success: '已完成',
  failed: '失败',
  skipped_dup: '已存在',
  cancelled: '已取消',
}

const STATUS_DOT: Record<DownloadTaskItem['status'], string> = {
  queued: 'bg-warning-500',
  pending: 'bg-warning-500',
  running: 'bg-brand-500',
  success: 'bg-success-500',
  failed: 'bg-error-500',
  skipped_dup: 'bg-gray-400',
  cancelled: 'bg-gray-400',
}

/**
 * 取最近 6 条「父任务级」通知。tasksStore.allTasks 已按 id 倒序，足够。
 * 父任务的 cover/title 才是有意义的通知，子任务是其 children，列表里反而会重复。
 */
const notifications = computed<DownloadTaskItem[]>(() =>
  tasksStore.allTasks.filter((t) => t.parent_task_id == null).slice(0, 6),
)

/** 任意未被「看过」的任务都算未读，体现红点提示。 */
const hasUnread = computed(() => {
  const list = tasksStore.allTasks
  if (!list.length) return false
  return list.some((t) => t.id > lastSeenTaskId.value)
})

const targetLabel = (t: DownloadTaskItem) => {
  if (t.target_type === 'playlist') return '歌单'
  if (t.target_type === 'album') return '专辑'
  return '单曲'
}

/**
 * 把 ISO 时间格式化成 "n 分钟前 / n 小时前 / n 天前"，超过 7 天直接显示日期。
 * 这里就地实现，不引入额外依赖。
 */
const formatRelative = (iso?: string | null) => {
  if (!iso) return ''
  const ts = new Date(iso).getTime()
  if (Number.isNaN(ts)) return ''
  const diffSec = Math.max(0, (Date.now() - ts) / 1000)
  if (diffSec < 60) return '刚刚'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)} 天前`
  return new Date(ts).toLocaleDateString()
}

const toggle = () => {
  open.value = !open.value
  if (open.value) markAsSeen()
}

const close = () => {
  open.value = false
}

/** 打开下拉时把红点清掉。 */
const markAsSeen = () => {
  const max = tasksStore.allTasks.reduce((acc, t) => Math.max(acc, t.id), 0)
  if (max > lastSeenTaskId.value) lastSeenTaskId.value = max
}

const onClickOutside = (e: MouseEvent) => {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) close()
}

/** 路由切换时主动收起。 */
watch(open, (v) => {
  if (v) markAsSeen()
})

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  // 进入时把已存在的任务视作"已读"，避免首次刷新就一片红点
  markAsSeen()
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>
