<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-99999 flex items-center justify-center bg-gray-900/50 p-4 backdrop-blur-[2px]"
      @click.self="handleBackdrop"
    >
      <div
        :class="[
          'max-h-[90vh] min-w-0 overflow-y-auto rounded-2xl border border-gray-200 bg-white shadow-theme-xl dark:border-gray-800 dark:bg-gray-900',
          className,
        ]"
        :style="{ width: sizeWidth }"
      >
        <div class="flex items-start justify-between gap-4 border-b border-gray-200 p-5 dark:border-gray-800">
          <div class="min-w-0">
            <h2 class="text-lg font-semibold text-gray-900 dark:text-white/90">{{ title }}</h2>
            <p v-if="description" class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
              {{ description }}
            </p>
          </div>
          <button
            type="button"
            class="inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/5"
            aria-label="关闭"
            @click="$emit('close')"
          >
            <X class="size-5" />
          </button>
        </div>
        <div class="p-5">
          <slot />
        </div>
        <div v-if="$slots.footer" class="border-t border-gray-200 p-5 dark:border-gray-800">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'

type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    size?: ModalSize
    closeOnBackdrop?: boolean
    className?: string
  }>(),
  {
    description: '',
    size: 'md',
    closeOnBackdrop: true,
    className: '',
  },
)

const emit = defineEmits<{
  close: []
}>()

/** 使用内联宽度，避免 Tailwind 动态任意值未生成时弹窗退化为全屏。 */
const sizeWidth = computed(() => {
  if (props.size === 'sm') return 'min(100%, 24rem)'
  if (props.size === 'lg') return 'min(100%, 42rem)'
  if (props.size === 'xl') return 'min(100%, 56rem)'
  return 'min(100%, 36rem)'
})

const handleBackdrop = () => {
  if (props.closeOnBackdrop) emit('close')
}
</script>
