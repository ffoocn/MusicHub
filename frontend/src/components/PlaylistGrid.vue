<template>
  <div v-if="loading" class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
    <!--
      骨架结构尽量贴近真实卡：方形封面 + 标题 + 副标题，
      避免 loading → 真实数据时高度跳变。
    -->
    <div
      v-for="idx in 10"
      :key="idx"
      class="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]"
    >
      <div class="aspect-square animate-pulse bg-gray-100 dark:bg-white/5"></div>
      <div class="space-y-2 p-4">
        <div class="h-4 w-4/5 animate-pulse rounded bg-gray-100 dark:bg-white/5"></div>
        <div class="h-4 w-3/5 animate-pulse rounded bg-gray-100 dark:bg-white/5"></div>
        <div class="mt-2 h-3 w-1/2 animate-pulse rounded bg-gray-100 dark:bg-white/5"></div>
      </div>
    </div>
  </div>

  <MusicEmpty v-else-if="!items.length" :title="emptyText" description="换一个平台或分类再试。" />

  <div v-else class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
    <article
      v-for="playlist in items"
      :key="`${playlist.platform}-${playlist.id}`"
      class="group cursor-pointer overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-theme-xs transition hover:-translate-y-0.5 hover:shadow-theme-md dark:border-gray-800 dark:bg-white/[0.03]"
      @click="open(playlist)"
    >
      <div class="relative aspect-square overflow-hidden bg-gray-100 dark:bg-white/5">
        <img
          v-if="playlist.cover_url"
          :src="withCoverParam(playlist.cover_url)"
          :alt="playlist.name"
          class="size-full object-cover transition duration-300 group-hover:scale-105"
          loading="lazy"
        />
        <div v-else class="flex size-full items-center justify-center text-4xl text-gray-400">
          {{ playlist.name?.[0] || '♪' }}
        </div>

        <!--
          Cover 上不再叠加平台图标：左侧导航已经选了平台，每张卡再贴一遍冗余。
          只保留 (1) 右上角播放量胶囊 (2) 悬浮订阅按钮，与网易云客户端样式对齐。
        -->
        <div
          v-if="playlist.play_count"
          class="absolute right-3 top-3 rounded-full bg-gray-900/70 px-2 py-1 text-theme-xs font-medium text-white backdrop-blur"
        >
          ▶ {{ formatCount(playlist.play_count) }}
        </div>

        <button
          v-if="showSubscribe"
          type="button"
          :disabled="busy[`${playlist.platform}-${playlist.id}`]"
          :class="[
            'absolute bottom-3 right-3 flex size-9 items-center justify-center rounded-full text-sm font-semibold text-white shadow-theme-md transition',
            isSubscribed(playlist)
              ? 'bg-success-500'
              : 'bg-brand-500 opacity-0 hover:bg-brand-600 group-hover:opacity-100',
          ]"
          :title="isSubscribed(playlist) ? '已订阅' : '订阅此歌单'"
          @click.stop="toggleSubscribe(playlist)"
        >
          <span v-if="busy[`${playlist.platform}-${playlist.id}`]" class="size-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
          <span v-else>{{ isSubscribed(playlist) ? '✓' : '+' }}</span>
        </button>
      </div>

      <div class="p-4">
        <!--
          固定标题容器高度 ≈ 2 行字（leading-snug × text-theme-sm × 2），
          这样 1 行短标题的卡和 2 行长标题的卡视觉高度对齐，避免锯齿。
        -->
        <h3
          class="line-clamp-2 h-[2.625rem] text-theme-sm font-semibold leading-snug text-gray-800 dark:text-white/90"
          :title="playlist.name"
        >
          {{ playlist.name }}
        </h3>
        <p class="mt-2 truncate text-theme-xs text-gray-500 dark:text-gray-400">
          <span v-if="playlist.creator">{{ playlist.creator }}</span>
          <span v-if="playlist.track_count"> · {{ playlist.track_count }} 首</span>
        </p>
      </div>
    </article>
  </div>

  <SubscribeOptionsDialog
    :open="Boolean(pendingSubscribe)"
    title="订阅歌单"
    :message="pendingSubscribe ? `订阅「${pendingSubscribe.name}」并定期同步新增歌曲。` : ''"
    :loading="Boolean(pendingSubscribe && busy[keyOf(pendingSubscribe)])"
    @close="pendingSubscribe = null"
    @confirm="confirmSubscribe"
  />
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { subscriptionsApi, type PlaylistBrief } from '@/api'
import MusicEmpty from '@/components/music/MusicEmpty.vue'
import SubscribeOptionsDialog from '@/components/SubscribeOptionsDialog.vue'
import { useMusicToast } from '@/components/music/useMusicToast'

const props = withDefaults(
  defineProps<{
    items: PlaylistBrief[]
    loading?: boolean
    emptyText?: string
    showSubscribe?: boolean
  }>(),
  {
    loading: false,
    emptyText: '暂无歌单',
    showSubscribe: true,
  },
)

const emit = defineEmits<{
  subscribed: [playlist: PlaylistBrief]
}>()

const router = useRouter()
const toast = useMusicToast()
const subscribedKeys = ref<Set<string>>(new Set())
const busy = reactive<Record<string, boolean>>({})
const pendingSubscribe = ref<PlaylistBrief | null>(null)

const keyOf = (playlist: PlaylistBrief) => `${playlist.platform}-${playlist.id}`
const isSubscribed = (playlist: PlaylistBrief) => subscribedKeys.value.has(keyOf(playlist))

const open = (playlist: PlaylistBrief) => {
  router.push({ name: 'playlist-detail', params: { platform: playlist.platform, id: playlist.id } })
}

const refreshSubscribed = async () => {
  if (!props.showSubscribe) return
  try {
    const list = await subscriptionsApi.list()
    subscribedKeys.value = new Set(
      list.filter((item) => item.target_type !== 'daily').map((item) => `${item.platform}-${item.platform_playlist_id}`),
    )
  } catch {
    // Ignore subscription status failures so discovery content still renders.
  }
}

const toggleSubscribe = async (playlist: PlaylistBrief) => {
  const key = keyOf(playlist)
  if (busy[key]) return
  if (isSubscribed(playlist)) {
    toast.info('已订阅，可在「订阅与自动化」管理')
    return
  }
  pendingSubscribe.value = playlist
}

const confirmSubscribe = async (generateM3u: boolean) => {
  const playlist = pendingSubscribe.value
  if (!playlist) return
  const key = keyOf(playlist)
  busy[key] = true
  try {
    await subscriptionsApi.add({
      platform: playlist.platform as 'netease' | 'qq',
      target_type: 'playlist',
      id: playlist.id,
      generate_m3u: generateM3u,
    })
    subscribedKeys.value.add(key)
    toast.success(`已订阅：${playlist.name}`)
    emit('subscribed', playlist)
    pendingSubscribe.value = null
  } catch (e: any) {
    const status = e?.response?.status
    if (status === 409) {
      subscribedKeys.value.add(key)
      toast.info('此歌单已在订阅中')
      pendingSubscribe.value = null
    } else {
      toast.error(`订阅失败：${e?.response?.data?.detail || e?.message || e}`)
    }
  } finally {
    busy[key] = false
  }
}

const formatCount = (n: number) => {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}亿`
  if (n >= 10_000) return `${(n / 10_000).toFixed(1)}万`
  return String(n)
}

const withCoverParam = (url: string) => {
  if (!url) return url
  if (url.includes('?param=')) return url
  return `${url}${url.includes('?') ? '&' : '?'}param=300y300`
}

watch(() => props.items, refreshSubscribed)
onMounted(refreshSubscribed)

defineExpose({ refreshSubscribed })
</script>
