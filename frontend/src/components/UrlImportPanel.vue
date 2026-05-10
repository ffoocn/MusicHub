<template>
  <MusicCard title="链接导入" description="粘贴网易云 / QQ 音乐的歌曲、歌单、专辑 URL，自动识别并跳转或入队。">
    <!-- 工具栏 -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative min-w-0 flex-1">
        <span class="pointer-events-none absolute inset-y-0 left-3.5 flex items-center">
          <svg class="h-4 w-4 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M12.586 4.586a2 2 0 1 1 2.828 2.828l-3 3a2 2 0 0 1-2.828 0 .75.75 0 0 0-1.06 1.06 3.5 3.5 0 0 0 4.95 0l3-3a3.5 3.5 0 0 0-4.95-4.95l-1.5 1.5a.75.75 0 0 0 1.06 1.06l1.5-1.5Zm-5 5a2 2 0 0 1 2.828 0 .75.75 0 1 0 1.06-1.06 3.5 3.5 0 0 0-4.95 0l-3 3a3.5 3.5 0 0 0 4.95 4.95l1.5-1.5a.75.75 0 0 0-1.06-1.06l-1.5 1.5a2 2 0 0 1-2.828-2.828l3-3Z" />
          </svg>
        </span>
        <input
          v-model="url"
          type="url"
          placeholder="https://music.163.com/#/playlist?id=xxx 或 https://y.qq.com/n/ryqq/playlist/xxx"
          class="h-11 w-full rounded-lg border border-gray-300 bg-transparent py-2.5 pl-10 pr-4 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
          @keyup.enter="parseAndGo"
        />
      </div>
      <MusicButton :loading="loading" @click="parseAndGo">解析并打开</MusicButton>
    </div>

    <div v-if="parsed" class="mt-4 flex items-center gap-2">
      <MusicPlatformIcon :platform="parsed.platform" size="sm" />
      <span class="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
        {{ typeLabel(parsed.kind) }} · ID {{ parsed.id }}
      </span>
    </div>

    <!-- 平台格式说明 -->
    <div class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div class="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-white/[0.02]">
        <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">网易云音乐</p>
        <ul class="space-y-1 text-xs text-gray-500 dark:text-gray-400">
          <li>歌曲：music.163.com/#/song?id=…</li>
          <li>歌单：music.163.com/#/playlist?id=…</li>
          <li>专辑：music.163.com/#/album?id=…</li>
        </ul>
      </div>
      <div class="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-white/[0.02]">
        <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">QQ 音乐</p>
        <ul class="space-y-1 text-xs text-gray-500 dark:text-gray-400">
          <li>歌曲：y.qq.com/n/ryqq/songDetail/…</li>
          <li>歌单：y.qq.com/n/ryqq/playlist/…</li>
          <li>专辑：y.qq.com/n/ryqq/album/…</li>
        </ul>
      </div>
    </div>
  </MusicCard>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { downloadApi } from '@/api'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import { useMusicToast } from '@/components/music/useMusicToast'

const router = useRouter()
const toast = useMusicToast()
const url = ref('')
const loading = ref(false)

interface ParseResult {
  platform: 'netease' | 'qq'
  kind: 'song' | 'playlist' | 'album'
  id: string
}
const parsed = ref<ParseResult | null>(null)

const typeLabel = (k: string) => (k === 'song' ? '歌曲' : k === 'playlist' ? '歌单' : '专辑')

const parseUrl = (raw: string): ParseResult | null => {
  const value = raw.trim()
  if (!value) return null
  if (/music\.163\.com/.test(value)) {
    const idMatch = value.match(/[?&]id=(\d+)/)
    if (!idMatch) return null
    const id = idMatch[1]
    if (/playlist/.test(value)) return { platform: 'netease', kind: 'playlist', id }
    if (/album/.test(value)) return { platform: 'netease', kind: 'album', id }
    return { platform: 'netease', kind: 'song', id }
  }
  if (/y\.qq\.com/.test(value) || /qq\.com\/n\/ryqq/.test(value)) {
    const match = value.match(/\/(song(?:Detail)?|playlist|album)\/([\w]+)/i)
    if (!match) return null
    const kindRaw = match[1].toLowerCase()
    const kind: 'song' | 'playlist' | 'album' = kindRaw.startsWith('song')
      ? 'song'
      : kindRaw === 'album'
        ? 'album'
        : 'playlist'
    return { platform: 'qq', kind, id: match[2] }
  }
  return null
}

const parseAndGo = async () => {
  const result = parseUrl(url.value)
  if (!result) {
    toast.warning('暂时无法识别此链接，请粘贴歌曲 / 歌单 / 专辑的网页链接')
    return
  }
  parsed.value = result
  if (result.kind === 'song') {
    loading.value = true
    try {
      await downloadApi.song(result.platform, result.id)
      toast.success('已加入下载队列')
    } catch (e: any) {
      toast.error(`入队失败：${e?.response?.data?.detail || e?.message || e}`)
    } finally {
      loading.value = false
    }
    return
  }
  router.push(`/${result.kind}/${result.platform}/${result.id}`)
}
</script>
