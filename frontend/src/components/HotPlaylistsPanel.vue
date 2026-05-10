<template>
  <!--
    布局：sticky header + 滚动 body + sticky footer（分页器）
      与 DailyPanel 保持一致，分页器始终可见，无需把内容滚到底。
  -->
  <section
    class="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-theme-xs dark:border-gray-800 dark:bg-white/[0.03] lg:h-full"
  >
    <!-- ============== Header（标题 + 操作 + 分类 chips） ============== -->
    <header class="border-b border-gray-100 px-5 py-4 dark:border-gray-800 sm:px-6">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="text-base font-semibold text-gray-800 dark:text-white/90">{{ title }}</h2>
          <p class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">{{ description }}</p>
        </div>
        <div class="flex items-center gap-2">
          <MusicButton variant="outline" size="xs" :loading="loading" @click="reload">刷新</MusicButton>
          <MusicButton size="xs" :disabled="!items.length" :loading="bulkBusy" @click="showBulkSubscribe = true">
            全部订阅（{{ items.length }}）
          </MusicButton>
        </div>
      </div>

      <!-- 分类 chips：仅热门模式显示。保留后端原始分类值用于请求，UI 按「前缀」分组展示并隐藏前缀。 -->
      <div v-if="mode === 'hot'" class="mt-4">
        <div class="space-y-3">
          <div
            v-for="group in visibleCategoryGroups"
            :key="group.name"
            class="grid gap-2 sm:grid-cols-[4rem_1fr]"
          >
            <div class="pt-1 text-xs font-semibold text-gray-500 dark:text-gray-400">{{ group.name }}</div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="cat in group.items"
                :key="cat.value"
                type="button"
                :class="[
                  'rounded-full px-3 py-1 text-xs font-medium transition',
                  cat.value === category
                    ? 'bg-brand-500 text-white shadow-theme-xs dark:bg-brand-500'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-white/5 dark:text-gray-400 dark:hover:bg-white/10',
                ]"
                :title="cat.value"
                @click="onCategory(cat.value)"
              >
                {{ cat.label }}
              </button>
            </div>
          </div>
          <button
            v-if="hiddenCategoryCount > 0"
            type="button"
            class="rounded-full border border-dashed border-gray-300 px-3 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-100 dark:border-white/10 dark:text-gray-400 dark:hover:bg-white/5"
            @click="categoryExpanded = !categoryExpanded"
          >
            {{ categoryExpanded ? '收起' : `展开全部（还有 ${hiddenCategoryCount} 个）` }}
          </button>
        </div>
        <p v-if="categoriesLoading" class="mt-2 text-theme-xs text-gray-400">分类加载中…</p>
      </div>
    </header>

    <!-- ============== Body（滚动） ============== -->
    <div class="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
      <PlaylistGrid
        ref="gridRef"
        :items="items"
        :loading="loading"
        :empty-text="mode === 'hot' ? '该分类下暂无歌单' : '排行榜列表为空'"
      />
    </div>

    <!-- ============== Footer（分页器，仅热门模式 + 至少有过数据时） ============== -->
    <footer
      v-if="mode === 'hot' && (items.length > 0 || page > 1)"
      class="border-t border-gray-100 bg-white px-5 py-3 dark:border-gray-800 dark:bg-transparent sm:px-6"
    >
      <MusicPagination
        :current-page="page"
        :has-more="hasMore"
        :loading="loading"
        :siblings="1"
        @change="onPageChange"
      />
    </footer>

    <SubscribeOptionsDialog
      :open="showBulkSubscribe"
      title="批量订阅歌单"
      :message="`将订阅当前页 ${items.length} 个歌单。`"
      :loading="bulkBusy"
      @close="showBulkSubscribe = false"
      @confirm="bulkSubscribe"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { discoverApi, subscriptionsApi, type PlaylistBrief } from '@/api'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicPagination from '@/components/music/MusicPagination.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import PlaylistGrid from '@/components/PlaylistGrid.vue'
import SubscribeOptionsDialog from '@/components/SubscribeOptionsDialog.vue'
import { DISCOVER_PLATFORM_KEY, type DiscoverPlatform } from '@/components/discover/platformInjection'

type HotMode = 'hot' | 'toplist'

const props = withDefaults(
  defineProps<{
    /** 'hot' = 分类热门歌单；'toplist' = 官方排行榜。 */
    mode?: HotMode
  }>(),
  { mode: 'hot' },
)

const toast = useMusicToast()
const fallbackPlatform = ref<DiscoverPlatform>('netease')
const platform = inject(DISCOVER_PLATFORM_KEY, fallbackPlatform)

/**
 * 按平台动态加载分类（网易云广场分类 / QQ y.qq.com/n/ryqq_v2/category 全量目录）。
 * QQ 分类形如「主题·ACG」，UI 按前缀分组，发请求仍使用原始分类值。
 */
const CATEGORY_GROUP_COLLAPSE_COUNT = 12
const FALLBACK_CATEGORIES = ['全部', '流行', '摇滚', '民谣', '电子', '说唱', '轻音乐', '影视原声', 'ACG', '古典', '怀旧']
const CATEGORY_GROUP_ORDER = ['热门', '主题', '场景', '心情', '年代', '流派', '语种', '分类']

interface CategoryChip {
  value: string
  label: string
}

interface CategoryGroup {
  name: string
  items: CategoryChip[]
}

const categories = ref<string[]>([...FALLBACK_CATEGORIES])
const categoriesLoading = ref(false)
const categoryExpanded = ref(false)
const category = ref<string>(categories.value[0] ?? '全部')

const splitCategory = (raw: string): { group: string; label: string } => {
  if (raw === '全部') return { group: '热门', label: '全部' }
  const normalized = raw.trim()
  const separators = ['·', '：', ':']
  for (const separator of separators) {
    const index = normalized.indexOf(separator)
    if (index > 0) {
      const group = normalized.slice(0, index).trim()
      const label = normalized.slice(index + 1).trim()
      if (group && label) return { group, label }
    }
  }
  return { group: '分类', label: normalized }
}

const categoryGroups = computed<CategoryGroup[]>(() => {
  const grouped = new Map<string, CategoryChip[]>()
  for (const raw of categories.value) {
    const { group, label } = splitCategory(raw)
    if (!grouped.has(group)) grouped.set(group, [])
    grouped.get(group)?.push({ value: raw, label })
  }
  return [...grouped.entries()]
    .sort(([a], [b]) => {
      const ia = CATEGORY_GROUP_ORDER.indexOf(a)
      const ib = CATEGORY_GROUP_ORDER.indexOf(b)
      if (ia >= 0 || ib >= 0) return (ia >= 0 ? ia : 999) - (ib >= 0 ? ib : 999)
      return a.localeCompare(b, 'zh-Hans-CN')
    })
    .map(([name, items]) => ({ name, items }))
})

const visibleCategoryGroups = computed<CategoryGroup[]>(() =>
  categoryGroups.value.map((group) => ({
    name: group.name,
    items: categoryExpanded.value ? group.items : group.items.slice(0, CATEGORY_GROUP_COLLAPSE_COUNT),
  })),
)

const hiddenCategoryCount = computed(() => {
  if (categoryExpanded.value) return 0
  return categoryGroups.value.reduce(
    (sum, group) => sum + Math.max(0, group.items.length - CATEGORY_GROUP_COLLAPSE_COUNT),
    0,
  )
})

const loadCategories = async () => {
  categoriesLoading.value = true
  try {
    const list = await discoverApi.hotPlaylistCategories(platform.value)
    categories.value = list.length > 0 ? list : [...FALLBACK_CATEGORIES]
  } catch (e: any) {
    categories.value = [...FALLBACK_CATEGORIES]
    toast.error(`分类加载失败：${e?.message || e}`)
  } finally {
    categoriesLoading.value = false
    if (!categories.value.includes(category.value)) {
      category.value = categories.value[0] ?? '全部'
    }
  }
}
const items = ref<PlaylistBrief[]>([])
const loading = ref(false)
const bulkBusy = ref(false)
const showBulkSubscribe = ref(false)
const gridRef = ref<InstanceType<typeof PlaylistGrid> | null>(null)

const PAGE_SIZE = 25
const page = ref(1)
const hasMore = ref(false)

const mode = computed(() => props.mode)
const title = computed(() => (mode.value === 'hot' ? '热门歌单' : '官方排行榜'))
const description = computed(() =>
  mode.value === 'hot' ? '按平台和分类发现可订阅热门歌单。' : '平台官方榜单：飙升 / 新歌 / 热歌 ...',
)

const onCategory = (value: string) => {
  if (value === category.value) return
  category.value = value
  page.value = 1
  load()
}

watch(platform, async () => {
  page.value = 1
  categoryExpanded.value = false
  await loadCategories()
  await load()
})

watch(mode, async () => {
  if (mode.value === 'hot') {
    await loadCategories()
    category.value = categories.value[0] ?? '全部'
  }
  page.value = 1
  load()
})

const bulkSubscribe = async (generateM3u: boolean) => {
  if (!items.value.length) return
  bulkBusy.value = true
  try {
    const result = await subscriptionsApi.bulkAdd({
      items: items.value.map((playlist) => ({
        platform: playlist.platform as 'netease' | 'qq',
        target_type: 'playlist',
        id: playlist.id,
        name: playlist.name,
        cover_url: playlist.cover_url,
        creator: playlist.creator,
      })),
      generate_m3u: generateM3u,
    })
    toast.success(`已订阅 ${result.created.length} 个，跳过 ${result.skipped.length} 个`)
    showBulkSubscribe.value = false
    await gridRef.value?.refreshSubscribed()
  } catch (e: any) {
    toast.error(`批量订阅失败：${e?.message || e}`)
  } finally {
    bulkBusy.value = false
  }
}

/**
 * 拉取当前 page/category 对应的一页数据（替换式）。
 *
 * 配合 TailAdmin 风格分页器：每次切页都是替换当前 items，而不是追加。
 */
const load = async () => {
  loading.value = true
  hasMore.value = false
  try {
    if (mode.value === 'toplist') {
      items.value = await discoverApi.topLists(platform.value)
      hasMore.value = false
      return
    }
    const resp = await discoverApi.hotPlaylists(
      platform.value,
      category.value,
      page.value,
      PAGE_SIZE,
    )
    items.value = resp.items
    page.value = resp.page
    hasMore.value = resp.has_more
  } catch (e: any) {
    toast.error(`加载失败：${e?.message || e}`)
    items.value = []
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

const onPageChange = (target: number) => {
  if (loading.value) return
  if (target === page.value) return
  page.value = target
  load()
}

const reload = () => load()
onMounted(async () => {
  await loadCategories()
  await load()
})
</script>
