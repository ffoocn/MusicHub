<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[
      'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition',
      sizeClass,
      variantClass,
      (disabled || loading) ? 'cursor-not-allowed opacity-50' : '',
      className,
    ]"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
    <slot />
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type ButtonVariant = 'primary' | 'outline' | 'ghost' | 'danger'
type ButtonSize = 'xs' | 'sm' | 'md'

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant
    size?: ButtonSize
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
    loading?: boolean
    className?: string
  }>(),
  {
    variant: 'primary',
    size: 'sm',
    type: 'button',
    disabled: false,
    loading: false,
    className: '',
  },
)

defineEmits<{
  click: [event: MouseEvent]
}>()

const sizeClass = computed(() => {
  if (props.size === 'xs') return 'px-3 py-2 text-theme-xs'
  if (props.size === 'md') return 'px-5 py-3 text-theme-sm'
  return 'px-4 py-2.5 text-theme-sm'
})

const variantClass = computed(() => {
  if (props.variant === 'outline') {
    return 'border border-gray-300 bg-white text-gray-700 shadow-theme-xs hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-white/[0.03]'
  }
  if (props.variant === 'ghost') {
    return 'text-gray-600 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-200'
  }
  if (props.variant === 'danger') {
    return 'bg-error-500 text-white shadow-theme-xs hover:bg-error-600'
  }
  return 'bg-brand-500 text-white shadow-theme-xs hover:bg-brand-600'
})
</script>
