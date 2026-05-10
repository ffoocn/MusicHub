<template>
  <div class="space-y-6">
    <div v-if="loading" class="grid grid-cols-1 gap-6 xl:grid-cols-[280px_1fr]">
      <div class="h-72 animate-pulse rounded-2xl bg-gray-100 dark:bg-white/5"></div>
      <div class="h-72 animate-pulse rounded-2xl bg-gray-100 dark:bg-white/5"></div>
    </div>

    <template v-else-if="data">
      <MusicCard>
        <div class="grid grid-cols-1 gap-6 lg:grid-cols-[220px_1fr]">
          <div class="overflow-hidden rounded-2xl bg-gray-100 dark:bg-white/5">
            <img
              v-if="data.cover_url"
              :src="data.cover_url"
              alt=""
              class="aspect-square w-full object-cover"
            />
            <div v-else class="flex aspect-square w-full items-center justify-center text-4xl text-gray-400">
              ♪
            </div>
          </div>

          <div class="min-w-0">
            <div class="mb-4 flex flex-wrap items-center gap-2">
              <MusicPlatformIcon :platform="data.platform" size="md" />
              <MusicBadge color="gray" size="md">{{ data.track_count }} 首</MusicBadge>
            </div>

            <p class="text-theme-sm font-medium text-brand-500 dark:text-brand-400">Playlist</p>
            <h1 class="mt-2 text-title-sm font-semibold text-gray-900 dark:text-white/90">
              {{ data.name }}
            </h1>
            <p class="mt-3 text-theme-sm text-gray-500 dark:text-gray-400">
              创建者：{{ data.creator || '-' }}
            </p>
            <p
              v-if="data.description"
              class="mt-4 max-h-24 overflow-auto whitespace-pre-wrap text-theme-sm leading-6 text-gray-600 dark:text-gray-300"
            >
              {{ data.description }}
            </p>

            <div class="mt-6 flex flex-wrap gap-3">
              <MusicButton variant="outline" :loading="subscribing" @click="subscribe">
                订阅自动同步
              </MusicButton>
            </div>
          </div>
        </div>
      </MusicCard>

      <SongListTable
        :songs="data.songs"
        :bundle="{ type: 'playlist', platform: data.platform, id: data.id }"
      />
    </template>

    <MusicEmpty v-else :title="error || '歌单加载失败'" description="请检查链接是否有效，或稍后重试。" />

    <SubscribeOptionsDialog
      :open="showSubscribeOptions"
      title="订阅歌单"
      :message="data ? `订阅「${data.name}」并每 24 小时自动同步。` : ''"
      :loading="subscribing"
      @close="showSubscribeOptions = false"
      @confirm="confirmSubscribe"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { discoverApi, subscriptionsApi, type PlaylistDetail } from '@/api'
import MusicBadge from '@/components/music/MusicBadge.vue'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import MusicEmpty from '@/components/music/MusicEmpty.vue'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import SubscribeOptionsDialog from '@/components/SubscribeOptionsDialog.vue'
import SongListTable from '@/components/SongListTable.vue'

const route = useRoute()
const toast = useMusicToast()
const data = ref<PlaylistDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const subscribing = ref(false)
const showSubscribeOptions = ref(false)

const subscribe = () => {
  if (!data.value) return
  showSubscribeOptions.value = true
}

const confirmSubscribe = async (generateM3u: boolean) => {
  if (!data.value) return
  subscribing.value = true
  try {
    const result = await subscriptionsApi.add({
      platform: data.value.platform,
      target_type: 'playlist',
      id: data.value.id,
      sync_interval_hours: 24,
      enabled: true,
      generate_m3u: generateM3u,
    })
    toast.success(`已订阅：${result.name}（每 24 小时自动同步）`)
    showSubscribeOptions.value = false
  } catch (e: any) {
    if (e?.response?.status === 409) toast.warning('此歌单已在订阅中')
    else toast.error(`订阅失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    subscribing.value = false
  }
}

const load = async () => {
  loading.value = true
  error.value = null
  data.value = null
  try {
    data.value = await discoverApi.playlist(
      route.params.platform as 'netease' | 'qq',
      route.params.id as string,
    )
  } catch (e: any) {
    error.value = `加载失败：${e?.response?.data?.detail || e?.message || e}`
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.params, load)
</script>
