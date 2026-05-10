<template>
  <!--
    紧凑确认对话框，专门服务"删除 / 确认"等单步操作场景。

    与 MusicModal 解耦后的好处：
      1. 自带固定 max-w-md（≈ 448px）尺寸，不再受父容器 stacking context 影响；
      2. icon + 标题 + 副文 用一行 flex 布局，按钮直接在底部独立 padding 区，
         视觉与 TailAdmin / shadcn confirm dialog 一致；
      3. 加载中（loading）时禁止背景点关 + 取消按钮，防止误关。
  -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="flex items-center justify-center bg-gray-900/50 p-4 backdrop-blur-[2px]"
        :style="{
          position: 'fixed',
          top: '0',
          right: '0',
          bottom: '0',
          left: '0',
          zIndex: 99999,
        }"
        role="presentation"
        @click.self="handleBackdrop"
      >
        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
          appear
        >
          <div
            v-if="open"
            class="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-theme-xl dark:border-gray-800 dark:bg-gray-900"
            :style="{
              width: '100%',
              maxWidth: '420px',
            }"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="titleId"
            :aria-describedby="message ? messageId : undefined"
          >
            <!-- 主体：icon + 文本 + 关闭按钮 -->
            <div class="flex items-start gap-4 p-5">
              <div
                :class="[
                  'flex size-10 shrink-0 items-center justify-center rounded-full',
                  iconClass,
                ]"
              >
                <AlertTriangle v-if="tone !== 'success'" class="size-5" />
                <CheckCircle v-else class="size-5" />
              </div>
              <div class="min-w-0 flex-1">
                <h2
                  :id="titleId"
                  class="text-base font-semibold text-gray-900 dark:text-white/90"
                >
                  {{ title }}
                </h2>
                <p
                  v-if="message"
                  :id="messageId"
                  class="mt-1 text-theme-sm leading-relaxed text-gray-500 dark:text-gray-400"
                >
                  {{ message }}
                </p>
                <slot />
              </div>
              <button
                type="button"
                class="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50 dark:text-gray-500 dark:hover:bg-white/5 dark:hover:text-white"
                aria-label="关闭"
                :disabled="loading"
                @click="handleClose"
              >
                <X class="size-4" />
              </button>
            </div>

            <!-- 按钮组 -->
            <div class="flex justify-end gap-3 border-t border-gray-200 px-5 py-4 dark:border-gray-800">
              <MusicButton
                variant="outline"
                size="sm"
                :disabled="loading"
                @click="handleClose"
              >
                {{ cancelText }}
              </MusicButton>
              <MusicButton
                :variant="tone === 'danger' ? 'danger' : 'primary'"
                size="sm"
                :loading="loading"
                @click="emit('confirm')"
              >
                {{ confirmText }}
              </MusicButton>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'
import { AlertTriangle, CheckCircle, X } from 'lucide-vue-next'
import MusicButton from '@/components/music/MusicButton.vue'

type ConfirmTone = 'info' | 'warning' | 'danger' | 'success'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message?: string
    tone?: ConfirmTone
    confirmText?: string
    cancelText?: string
    loading?: boolean
    /** 关闭项：点击背景 / 点 X 是否触发 close。loading 时强制关闭。 */
    closeOnBackdrop?: boolean
  }>(),
  {
    message: '',
    tone: 'warning',
    confirmText: '确认',
    cancelText: '取消',
    loading: false,
    closeOnBackdrop: true,
  },
)

const emit = defineEmits<{
  close: []
  confirm: []
}>()

const _id = useId()
const titleId = `confirm-title-${_id}`
const messageId = `confirm-msg-${_id}`

const iconClass = computed(() => {
  if (props.tone === 'danger') return 'bg-error-50 text-error-500 dark:bg-error-500/15'
  if (props.tone === 'success') return 'bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500'
  if (props.tone === 'info') return 'bg-brand-50 text-brand-500 dark:bg-brand-500/15'
  return 'bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-orange-400'
})

const handleClose = () => {
  if (!props.loading) emit('close')
}
const handleBackdrop = () => {
  if (props.loading) return
  if (props.closeOnBackdrop) emit('close')
}
</script>
