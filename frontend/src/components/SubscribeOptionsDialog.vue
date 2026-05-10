<template>
  <MusicConfirmDialog
    :open="open"
    :title="title"
    :message="message"
    tone="info"
    :loading="loading"
    confirm-text="确认订阅"
    cancel-text="取消"
    @close="emit('close')"
    @confirm="emit('confirm', generateM3u)"
  >
    <label class="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-white/5">
      <input
        v-model="generateM3u"
        type="checkbox"
        class="mt-0.5 size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-600"
      />
      <span>
        <span class="block text-theme-sm font-medium text-gray-800 dark:text-white/90">生成 M3U8 播放列表</span>
        <span class="mt-1 block text-theme-xs text-gray-500 dark:text-gray-400">
          开启后会在同步下载后生成 `_m3u/*.m3u8`，关闭则只维护订阅和下载任务。
        </span>
      </span>
    </label>
  </MusicConfirmDialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import MusicConfirmDialog from '@/components/music/MusicConfirmDialog.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message?: string
    loading?: boolean
    defaultGenerateM3u?: boolean
  }>(),
  {
    message: '',
    loading: false,
    defaultGenerateM3u: true,
  },
)

const emit = defineEmits<{
  close: []
  confirm: [generateM3u: boolean]
}>()

const generateM3u = ref(props.defaultGenerateM3u)

watch(
  () => props.open,
  (open) => {
    if (open) generateM3u.value = props.defaultGenerateM3u
  },
)
</script>
