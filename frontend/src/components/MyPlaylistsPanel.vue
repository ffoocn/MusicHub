<template>
  <div class="space-y-6">
    <!-- 工具栏卡片 -->
    <MusicCard title="我的歌单" description="登录后读取你在平台上创建和收藏的歌单。">
      <template #actions>
        <div class="flex items-center gap-2">
          <MusicButton variant="outline" size="xs" :loading="loading" @click="load">刷新</MusicButton>
          <MusicButton
            v-if="data.logged_in && (data.created.length || data.collected.length)"
            size="xs"
            :loading="bulkBusy"
            @click="openBulkSubscribe([...data.created, ...data.collected])"
          >
            全部订阅（{{ data.created.length + data.collected.length }}）
          </MusicButton>
        </div>
      </template>

      <div class="flex flex-wrap items-center gap-3">
        <!-- 当前平台徽章（顶部已统一切换） -->
        <span class="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
          {{ platform === 'netease' ? '网易云' : 'QQ 音乐' }}
        </span>
        <!-- 用户昵称徽章 -->
        <span
          v-if="data.logged_in && data.nickname"
          class="inline-flex items-center gap-1.5 rounded-full bg-success-50 px-3 py-1 text-xs font-medium text-success-700 dark:bg-success-500/15 dark:text-success-400"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-success-500"></span>
          {{ data.nickname }}
        </span>
      </div>
    </MusicCard>

    <!-- 未登录提示 -->
    <div v-if="!loading && !data.logged_in" class="rounded-2xl border border-warning-200 bg-warning-50/50 p-6 dark:border-warning-500/30 dark:bg-warning-500/5">
      <div class="flex items-start gap-4">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-warning-100 dark:bg-warning-500/20">
          <svg class="h-5 w-5 text-warning-600 dark:text-warning-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 5Zm0 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" />
          </svg>
        </div>
        <div>
          <p class="text-sm font-semibold text-warning-700 dark:text-warning-400">尚未登录</p>
          <p class="mt-1 text-sm text-warning-600/80 dark:text-warning-400/70">
            请先到「设置 → 账号管理」扫码登录 {{ platform === 'netease' ? '网易云' : 'QQ 音乐' }}，登录后即可查看自己的歌单。
          </p>
        </div>
      </div>
    </div>

    <template v-else>
      <!-- 我创建的 -->
      <MusicCard :title="`我创建的（${data.created.length}）`">
        <template #actions>
          <MusicButton v-if="data.created.length" variant="outline" size="xs" @click="openBulkSubscribe(data.created)">
            订阅本组
          </MusicButton>
        </template>
        <PlaylistGrid ref="createdRef" :items="data.created" :loading="loading" empty-text="暂无创建的歌单" />
      </MusicCard>

      <!-- 我收藏的 -->
      <MusicCard v-if="data.collected.length" :title="`我收藏的（${data.collected.length}）`">
        <template #actions>
          <MusicButton variant="outline" size="xs" @click="openBulkSubscribe(data.collected)">订阅本组</MusicButton>
        </template>
        <PlaylistGrid ref="collectedRef" :items="data.collected" :loading="false" />
      </MusicCard>
    </template>

    <SubscribeOptionsDialog
      :open="pendingBulk.length > 0"
      title="批量订阅我的歌单"
      :message="`将订阅 ${pendingBulk.length} 个歌单。`"
      :loading="bulkBusy"
      @close="pendingBulk = []"
      @confirm="bulkSubscribe"
    />
  </div>
</template>

<script setup lang="ts">
import { inject, onMounted, reactive, ref, watch } from 'vue'
import { discoverApi, subscriptionsApi, type PlaylistBrief } from '@/api'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import PlaylistGrid from '@/components/PlaylistGrid.vue'
import { DISCOVER_PLATFORM_KEY, type DiscoverPlatform } from '@/components/discover/platformInjection'
import SubscribeOptionsDialog from '@/components/SubscribeOptionsDialog.vue'

interface MyData {
  created: PlaylistBrief[]
  collected: PlaylistBrief[]
  logged_in: boolean
  nickname?: string
}

const toast = useMusicToast()
const fallbackPlatform = ref<DiscoverPlatform>('netease')
const platform = inject(DISCOVER_PLATFORM_KEY, fallbackPlatform)
const loading = ref(false)
const bulkBusy = ref(false)
const createdRef = ref<InstanceType<typeof PlaylistGrid> | null>(null)
const collectedRef = ref<InstanceType<typeof PlaylistGrid> | null>(null)
const data = reactive<MyData>({ created: [], collected: [], logged_in: false })
const pendingBulk = ref<PlaylistBrief[]>([])

watch(platform, () => {
  load()
})

const openBulkSubscribe = (list: PlaylistBrief[]) => {
  if (!list.length) return
  pendingBulk.value = list
}

const bulkSubscribe = async (generateM3u: boolean) => {
  const list = pendingBulk.value
  if (!list.length) return
  bulkBusy.value = true
  try {
    const result = await subscriptionsApi.bulkAdd({
      items: list.map((playlist) => ({
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
    pendingBulk.value = []
    await Promise.all([createdRef.value?.refreshSubscribed(), collectedRef.value?.refreshSubscribed()])
  } catch (e: any) {
    toast.error(`批量订阅失败：${e?.message || e}`)
  } finally {
    bulkBusy.value = false
  }
}

const load = async () => {
  loading.value = true
  try {
    const result = await discoverApi.myPlaylists(platform.value)
    data.created = result.created
    data.collected = result.collected
    data.logged_in = result.logged_in
    data.nickname = result.nickname
  } catch (e: any) {
    toast.error(`加载失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
