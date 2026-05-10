<script setup lang="ts">
/**
 * 顶栏智能搜索框。
 *
 * 行为：
 *   - 输入文本时实时检测：
 *     - 以 ``http(s)://`` 开头 → 当作链接，用 ``parseMusicUrl`` 解析
 *     - 否则当作搜索关键词
 *   - Enter 提交：
 *     - 链接（song）→ 直接调 ``downloadApi.song`` 加入下载队列
 *     - 链接（playlist / album）→ 跳转到对应详情路由
 *     - 关键词 → ``router.push({ path: '/discover', query: { q } })``
 *   - ⌘/Ctrl + K 全局快捷键聚焦搜索框
 *   - 输入框下方实时给出一行 hint，告诉用户「Enter 会做什么」
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { downloadApi } from '@/api'
import { useMusicToast } from '@/components/music/useMusicToast'
import {
  KIND_LABEL,
  PLATFORM_LABEL,
  looksLikeUrl,
  parseMusicUrl,
  type ParsedMusicUrl,
} from '@/utils/parseMusicUrl'

const router = useRouter()
const toast = useMusicToast()

const text = ref('')
const submitting = ref(false)

const isUrl = computed(() => looksLikeUrl(text.value))
const parsed = computed<ParsedMusicUrl | null>(() => (isUrl.value ? parseMusicUrl(text.value) : null))

/** Enter 时的行为预告。空文本时返回空串以便模板隐藏。 */
const hint = computed(() => {
  const value = text.value.trim()
  if (!value) return ''
  if (isUrl.value) {
    if (!parsed.value) return '链接暂时无法识别，请检查格式'
    const action = parsed.value.kind === 'song' ? '加入下载' : '打开详情'
    return `识别为 ${PLATFORM_LABEL[parsed.value.platform]} · ${KIND_LABEL[parsed.value.kind]}，按 Enter ${action}`
  }
  return `按 Enter 搜索 「${value}」`
})

const onSubmit = async () => {
  const value = text.value.trim()
  if (!value || submitting.value) return

  // URL 模式
  if (isUrl.value) {
    if (!parsed.value) {
      toast.warning('暂时无法识别此链接')
      return
    }
    const result = parsed.value
    if (result.kind === 'song') {
      submitting.value = true
      try {
        await downloadApi.song(result.platform, result.id)
        toast.success('已加入下载队列')
        text.value = ''
      } catch (e: any) {
        toast.error(`入队失败：${e?.response?.data?.detail || e?.message || e}`)
      } finally {
        submitting.value = false
      }
      return
    }
    // playlist / album → 跳详情页
    const routeName = result.kind === 'playlist' ? 'playlist-detail' : 'album-detail'
    router.push({ name: routeName, params: { platform: result.platform, id: result.id } })
    text.value = ''
    return
  }

  // 关键词模式 → 让 Discover 页接管
  router.push({ path: '/discover', query: { q: value } })
}

const focusSearchInput = () => {
  const inputElement = document.getElementById('search-input')
  inputElement?.focus()
}

const handleKeydown = (event: KeyboardEvent) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
    event.preventDefault()
    focusSearchInput()
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div class="hidden xl:block">
    <form @submit.prevent="onSubmit">
      <div class="relative">
        <label for="search-input" class="sr-only">搜索关键词或粘贴链接</label>
        <span class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2">
          <svg
            class="fill-gray-500 dark:fill-gray-400"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M3.04175 9.37363C3.04175 5.87693 5.87711 3.04199 9.37508 3.04199C12.8731 3.04199 15.7084 5.87693 15.7084 9.37363C15.7084 12.8703 12.8731 15.7053 9.37508 15.7053C5.87711 15.7053 3.04175 12.8703 3.04175 9.37363ZM9.37508 1.54199C5.04902 1.54199 1.54175 5.04817 1.54175 9.37363C1.54175 13.6991 5.04902 17.2053 9.37508 17.2053C11.2674 17.2053 13.003 16.5344 14.357 15.4176L17.177 18.238C17.4699 18.5309 17.9448 18.5309 18.2377 18.238C18.5306 17.9451 18.5306 17.4703 18.2377 17.1774L15.418 14.3573C16.5365 13.0033 17.2084 11.2669 17.2084 9.37363C17.2084 5.04817 13.7011 1.54199 9.37508 1.54199Z"
            />
          </svg>
        </span>
        <input
          id="search-input"
          v-model="text"
          type="text"
          placeholder="搜索歌曲，或粘贴歌单 / 专辑 / 歌曲链接"
          class="dark:bg-dark-900 h-11 w-full rounded-lg border border-gray-200 bg-transparent py-2.5 pl-12 pr-14 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-800 dark:bg-gray-900 dark:bg-white/3 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800 xl:w-[430px]"
          :disabled="submitting"
        />
        <button
          type="button"
          @click="focusSearchInput"
          class="absolute right-2.5 top-1/2 inline-flex -translate-y-1/2 items-center gap-0.5 rounded-lg border border-gray-200 bg-gray-50 px-[7px] py-[4.5px] text-xs -tracking-[0.2px] text-gray-500 dark:border-gray-800 dark:bg-white/3 dark:text-gray-400"
          aria-label="Focus search input (Cmd+K)"
        >
          <span aria-hidden="true">⌘</span>
          <span aria-hidden="true">K</span>
        </button>
      </div>
    </form>
    <p
      v-if="hint"
      class="mt-1 truncate text-xs text-gray-500 dark:text-gray-400 xl:max-w-[430px]"
    >
      {{ hint }}
    </p>
  </div>
</template>
