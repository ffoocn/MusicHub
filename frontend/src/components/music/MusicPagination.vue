<template>
  <!--
    分页器组件（参考 TailAdmin Basic Table 3 样式）：
      [← Previous]   1  [2]  3   [Next →]

    用法：
      <MusicPagination
        v-model:current-page="page"
        :total-pages="totalPages"   // 已知总页数时传入
        :has-more="hasMore"         // 未知总页数时仅靠 has_more 判断 Next
        :loading="loading"
        @change="onPageChange"
      />

    对外约束：
      - currentPage 从 1 开始
      - has-more=false 时 Next 禁用；currentPage<=1 时 Previous 禁用
      - total-pages 已知 ⇒ 用 1..N + 省略号布局
        total-pages 未知 ⇒ 仅显示当前页前后 ±siblings 的页码
  -->
  <nav
    aria-label="分页"
    class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-white/[0.03]"
  >
    <!-- Previous -->
    <button
      type="button"
      :disabled="!canPrev || loading"
      :class="[
        'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition',
        canPrev && !loading
          ? 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-white/[0.03]'
          : 'cursor-not-allowed border-gray-100 bg-white text-gray-300 dark:border-gray-800 dark:bg-white/[0.02] dark:text-gray-600',
      ]"
      @click="goTo(currentPage - 1)"
    >
      <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
        <path d="M12.5 15 7.5 10l5-5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span>Previous</span>
    </button>

    <!-- 页码列表 -->
    <ul class="flex items-center gap-1">
      <li v-for="(item, idx) in pageItems" :key="`${item.kind}-${idx}-${item.page ?? ''}`">
        <span
          v-if="item.kind === 'ellipsis'"
          class="inline-flex size-9 items-center justify-center text-sm text-gray-400 dark:text-gray-500"
        >
          …
        </span>
        <button
          v-else
          type="button"
          :aria-current="item.page === currentPage ? 'page' : undefined"
          :disabled="loading"
          :class="[
            'inline-flex size-9 items-center justify-center rounded-lg text-sm font-medium transition',
            item.page === currentPage
              ? 'bg-brand-500 text-white shadow-theme-xs hover:bg-brand-600'
              : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5',
            loading && item.page !== currentPage ? 'cursor-not-allowed opacity-60' : '',
          ]"
          @click="goTo(item.page!)"
        >
          {{ item.page }}
        </button>
      </li>
    </ul>

    <!-- Next -->
    <button
      type="button"
      :disabled="!canNext || loading"
      :class="[
        'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition',
        canNext && !loading
          ? 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-white/[0.03]'
          : 'cursor-not-allowed border-gray-100 bg-white text-gray-300 dark:border-gray-800 dark:bg-white/[0.02] dark:text-gray-600',
      ]"
      @click="goTo(currentPage + 1)"
    >
      <span>Next</span>
      <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
        <path d="m7.5 5 5 5-5 5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  /** 当前页（从 1 开始） */
  currentPage: number
  /** 已知的总页数；未知（API 仅返回 has_more）时可省略 */
  totalPages?: number | null
  /** 后端返回的 has_more（未知 totalPages 时由它决定 Next 是否禁用） */
  hasMore?: boolean
  /** 当前页前后各显示多少个相邻页码（默认 1） */
  siblings?: number
  /** 端点（首页 / 末页）保留多少个 boundary 页码（默认 1） */
  boundaries?: number
  /** loading 时全部按钮禁用 */
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  totalPages: null,
  hasMore: false,
  siblings: 1,
  boundaries: 1,
  loading: false,
})

const emit = defineEmits<{
  'update:currentPage': [page: number]
  change: [page: number]
}>()

const canPrev = computed(() => props.currentPage > 1)
const canNext = computed(() => {
  if (props.totalPages != null) return props.currentPage < props.totalPages
  return !!props.hasMore
})

type PageItem = { kind: 'page' | 'ellipsis'; page?: number }

/**
 * 计算要显示的页码项。
 *
 * - 已知 totalPages：经典方案
 *     [1] … [c-s..c+s] … [N]
 *   并合并端点和窗口（避免出现「1, …, 2」这种废省略号）。
 *
 * - 未知 totalPages：仅按相邻页 + has_more 估计
 *     窗口 = [max(1, c-s), c+s]，但只有 hasMore 时才允许出现 c+1..c+s
 */
const pageItems = computed<PageItem[]>(() => {
  const cur = Math.max(1, props.currentPage)
  const sib = Math.max(0, props.siblings)
  const bnd = Math.max(0, props.boundaries)
  const total = props.totalPages

  if (total != null && total > 0) {
    const pages = new Set<number>()
    for (let i = 1; i <= Math.min(bnd, total); i++) pages.add(i)
    for (let i = Math.max(1, total - bnd + 1); i <= total; i++) pages.add(i)
    for (let i = Math.max(1, cur - sib); i <= Math.min(total, cur + sib); i++) pages.add(i)
    const sorted = Array.from(pages).sort((a, b) => a - b)
    const out: PageItem[] = []
    let prev = 0
    for (const p of sorted) {
      if (prev && p - prev > 1) out.push({ kind: 'ellipsis' })
      out.push({ kind: 'page', page: p })
      prev = p
    }
    return out
  }

  // 未知总页数：只展示当前页附近的窗口
  const start = Math.max(1, cur - sib)
  const tentativeEnd = cur + sib
  const end = props.hasMore ? tentativeEnd : cur
  const out: PageItem[] = []
  for (let i = start; i <= end; i++) out.push({ kind: 'page', page: i })
  return out
})

const goTo = (target: number) => {
  if (props.loading) return
  if (target < 1) return
  if (target === props.currentPage) return
  if (props.totalPages != null && target > props.totalPages) return
  if (props.totalPages == null && target > props.currentPage && !props.hasMore) return
  emit('update:currentPage', target)
  emit('change', target)
}
</script>
