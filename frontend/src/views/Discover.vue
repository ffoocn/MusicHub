<template>
  <div class="flex flex-col gap-6 lg:h-[calc(100vh-13.5rem)] lg:flex-row lg:overflow-hidden">

    <!-- ============== 左侧：功能导航（固定 288px，内部独立滚动） ============== -->
    <aside class="space-y-4 lg:w-72 lg:shrink-0 lg:overflow-y-auto lg:pr-1">
      <!--
        垂直导航：
        - recommendTabs（推荐歌曲 / 推荐歌单）：紧贴顶部，无分组标题
        - playlistTabs（热门歌单 / 官方排行榜 / 我的歌单）：保留「歌单」分组标题
        搜索 / URL 导入已经迁移到顶栏的智能搜索框，左侧不再展示。
      -->
      <nav class="rounded-2xl border border-gray-200 bg-white p-2 shadow-theme-xs dark:border-gray-800 dark:bg-white/[0.03]">
        <div>
          <div v-if="loadingModes" class="space-y-2 px-2 py-2">
            <div v-for="i in 3" :key="i" class="h-9 animate-pulse rounded-xl bg-gray-100 dark:bg-white/5"></div>
          </div>
          <div v-else-if="!recommendTabs.length" class="px-3 py-3 text-xs text-gray-500 dark:text-gray-400">
            该平台暂无推荐模式
          </div>
          <button
            v-for="tab in recommendTabs"
            :key="tab.name"
            type="button"
            :class="navItemClass(tab.name)"
            @click="onNavClick(tab.name)"
          >
            <NavIcon :icon="tab.icon" :active="activeTab === tab.name" />
            <span class="flex-1">{{ tab.label }}</span>
            <span class="text-xs text-gray-400 group-hover:text-gray-500 dark:text-gray-500">{{ tab.hint }}</span>
          </button>
        </div>

        <div class="mt-3">
          <p class="px-2 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">歌单</p>
          <button
            v-for="tab in playlistTabs"
            :key="tab.name"
            type="button"
            :class="navItemClass(tab.name)"
            @click="onNavClick(tab.name)"
          >
            <NavIcon :icon="tab.icon" :active="activeTab === tab.name" />
            <span class="flex-1">{{ tab.label }}</span>
            <span class="text-xs text-gray-400 group-hover:text-gray-500 dark:text-gray-500">{{ tab.hint }}</span>
          </button>
        </div>
      </nav>
    </aside>

    <!-- ============== 右侧：主内容区 ============== -->
    <!--
      整体改为 flex column：
      - 顶部 segmented platform tabs（仅推荐/歌单类视图显示）
      - 下方 panel 容器 flex-1，溢出时由 panel 自身或外层容器滚动
    -->
    <main class="flex min-w-0 flex-1 flex-col lg:h-full lg:pr-1">
      <!--
        平台切换：移到主区域顶部，与「推荐歌曲 / 推荐歌单 / 热门歌单 / 官方排行榜 / 我的歌单」共享平台上下文。
        - 搜索模式（顶栏 ?q= 触发）下隐藏：搜索本身是跨平台聚合
        - 样式参考 TailAdmin segment：rounded-full 灰底胶囊
      -->
      <div v-if="showPlatformSwitch" class="mb-4 shrink-0">
        <div
          role="tablist"
          aria-label="平台切换"
          class="inline-flex items-center gap-1 rounded-full bg-gray-100 p-1 dark:bg-white/[0.05]"
        >
          <button
            v-for="p in platforms"
            :key="p.value"
            type="button"
            role="tab"
            :aria-selected="platform === p.value"
            :class="[
              'min-w-[110px] rounded-full px-5 py-2 text-sm font-medium transition',
              platform === p.value
                ? 'bg-white text-gray-900 shadow-theme-xs dark:bg-gray-800 dark:text-white'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
            ]"
            @click="setPlatform(p.value)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <div class="min-h-0 flex-1 lg:overflow-y-auto">
        <SearchPanel v-if="isSearchActive" />
        <HotPlaylistsPanel v-else-if="activeTab === 'hot'" mode="hot" />
        <HotPlaylistsPanel v-else-if="activeTab === 'toplist'" mode="toplist" />
        <MyPlaylistsPanel  v-else-if="activeTab === 'my'" />
        <DailyPanel
          v-else-if="activeMode && activeMode.kind && activeMode.id"
          :key="`${platform}:${activeMode.kind}:${activeMode.id}`"
          :platform="platform"
          :mode-kind="activeMode.kind"
          :mode-id="activeMode.id"
          :mode-label="activeMode.label"
        />
      </div>
    </main>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, provide, h, defineComponent, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Flame,
  Headphones,
  Heart,
  LayoutGrid,
  ListMusic,
  Radar,
  Sparkles,
  Star,
  Sun,
  User,
} from 'lucide-vue-next'
import SearchPanel from '@/components/SearchPanel.vue'
import DailyPanel from '@/components/DailyPanel.vue'
import HotPlaylistsPanel from '@/components/HotPlaylistsPanel.vue'
import MyPlaylistsPanel from '@/components/MyPlaylistsPanel.vue'
import { discoverApi, type RecommendMode } from '@/api'
import { DISCOVER_PLATFORM_KEY } from '@/components/discover/platformInjection'

type PlatformId = 'netease' | 'qq'

interface NavTab {
  name: string
  label: string
  /**
   * 直接传 lucide-vue-next 组件，避免维护"图标名 ↔ SVG path"映射表。
   * 这样新增图标只要改 import 不用动渲染逻辑。
   */
  icon: Component
  hint: string
  kind?: 'song' | 'playlist'
  id?: string
}

/**
 * 按 mode id 选语义化图标。
 *
 * 之前所有 song mode 全部回退到星形 ⭐，左侧导航看上去清一色，无法区分。
 * 这里给每个具体的 mode id 配一个专属图标：
 *  - 雷达推荐 ``radar_recommend`` → 雷达
 *  - 推荐新歌 ``recommend_newsong`` → 闪光（"新"语义）
 *  - 猜你喜欢 ``guess_recommend`` → 心形
 *  - 网易云每日推荐 ``default`` → 太阳（每日）
 *  - 推荐歌单 ``recommend_songlist`` / ``personalized`` → 歌单方格
 *  - 旧 ``home_feed`` / 未知 → 通用耳机图标
 */
const SONG_MODE_ICON: Record<string, Component> = {
  radar_recommend: Radar,
  recommend_newsong: Sparkles,
  guess_recommend: Heart,
  default: Sun,
  home_feed: Headphones,
}

const PLAYLIST_MODE_ICON: Record<string, Component> = {
  personalized: LayoutGrid,
  recommend_songlist: LayoutGrid,
  default: ListMusic,
}

const route = useRoute()
const router = useRouter()

const platforms: { value: PlatformId; label: string }[] = [
  { value: 'netease', label: '网易云' },
  { value: 'qq', label: 'QQ 音乐' },
]

const platform = ref<PlatformId>('netease')
/** 当前选中的 nav tab，搜索模式由 route.query.q 触发，不写到这里。 */
const activeTab = ref<string>('')

provide(DISCOVER_PLATFORM_KEY, platform)
const songModes = ref<RecommendMode[]>([])
const playlistModes = ref<RecommendMode[]>([])
const loadingModes = ref(false)

const playlistTabs: NavTab[] = [
  { name: 'hot',     label: '热门歌单',   icon: Flame,        hint: '分类' },
  { name: 'toplist', label: '官方排行榜', icon: Flame,        hint: '榜单' },
  { name: 'my',      label: '我的歌单',   icon: User,         hint: '已登录' },
]

const recommendTabs = computed<NavTab[]>(() => {
  const songs: NavTab[] = songModes.value.map((m) => ({
    name: `mode-song-${m.id}`,
    label: m.label,
    icon: SONG_MODE_ICON[m.id] ?? Star,
    hint: '歌曲',
    kind: 'song',
    id: m.id,
  }))
  const lists: NavTab[] = playlistModes.value.map((m) => ({
    name: `mode-playlist-${m.id}`,
    label: m.label,
    icon: PLAYLIST_MODE_ICON[m.id] ?? ListMusic,
    hint: '歌单',
    kind: 'playlist',
    id: m.id,
  }))
  return [...songs, ...lists]
})

const activeMode = computed(() => recommendTabs.value.find((t) => t.name === activeTab.value) || null)

/** 顶栏搜索通过 ?q=... 跳到本页时即视为搜索模式。 */
const isSearchActive = computed(() => !!((route.query.q as string) || '').trim())

/** 搜索是跨平台聚合，主区域顶部的平台切换在此场景下没有意义，需要隐藏。 */
const showPlatformSwitch = computed(() => !isSearchActive.value)

const navItemClass = (name: string) => [
  'group mt-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition',
  !isSearchActive.value && activeTab.value === name
    ? 'bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400'
    : 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-white/[0.03]',
]

/**
 * 用户从左侧 nav 选中某个 tab：
 * - 切换 activeTab；
 * - 如果当前还带着 ?q= 搜索 query，需要先清掉，否则搜索面板会一直覆盖在主区域。
 */
const onNavClick = (name: string) => {
  activeTab.value = name
  if (route.query.q) {
    router.replace({ path: '/discover', query: {} })
  }
}

/**
 * 左侧 nav 项前的小图标。
 *
 * 渲染逻辑：
 *  1. 外层 ``span`` 是一个圆角小方块，激活态白底+品牌色，普通态浅灰底；
 *  2. 内部把传入的 lucide 组件以 ``h(Component)`` 渲染出来，统一控制尺寸+stroke 粗细；
 *  3. lucide 图标默认 ``stroke="currentColor"``，会跟随父级文字颜色，所以这里只需要在
 *     父 wrap 上控制颜色即可。
 */
const NavIcon = defineComponent({
  props: {
    icon: { type: Object as () => Component, required: true },
    active: { type: Boolean, default: false },
  },
  setup(props) {
    const wrapClass = () => [
      'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition',
      props.active
        ? 'bg-white text-brand-500 shadow-theme-xs dark:bg-gray-800 dark:text-brand-400'
        : 'bg-gray-100 text-gray-400 group-hover:text-gray-600 dark:bg-white/5 dark:text-gray-500',
    ]
    return () =>
      h('span', { class: wrapClass() }, [
        h(props.icon as Component, { class: 'h-4 w-4', 'stroke-width': 2 }),
      ])
  },
})

/**
 * 切换平台：
 * - 重新拉取该平台支持的推荐模式；
 * - 如果当前 activeTab 是已不存在的推荐项，回退到该平台的第一个推荐项。
 *   平台无关的歌单 tab（hot / toplist / my）保持不变。
 */
const setPlatform = async (value: PlatformId) => {
  if (platform.value === value) return
  platform.value = value
  await loadModesForCurrentPlatform()
  const stillExists = recommendTabs.value.some((t) => t.name === activeTab.value)
  if (activeTab.value.startsWith('mode-') && !stillExists) {
    const first = recommendTabs.value[0]
    activeTab.value = first ? first.name : ''
  } else if (!activeTab.value && recommendTabs.value.length) {
    activeTab.value = recommendTabs.value[0].name
  }
}

const loadModesForCurrentPlatform = async () => {
  loadingModes.value = true
  try {
    const data = await discoverApi.recommendModes(platform.value)
    songModes.value = data.song_modes || []
    playlistModes.value = data.playlist_modes || []
  } catch {
    songModes.value = []
    playlistModes.value = []
  } finally {
    loadingModes.value = false
  }
}

watch(platform, () => {}, { immediate: false })

onMounted(async () => {
  await loadModesForCurrentPlatform()
  // 默认选中：进入页面没有 ?q= 时，落到平台第一个推荐项
  if (!isSearchActive.value && !activeTab.value && recommendTabs.value.length) {
    activeTab.value = recommendTabs.value[0].name
  }
})
</script>
