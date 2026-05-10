<template>
  <span :class="[baseClass, sizeClass, colorClass, className]">
    <slot />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type BadgeColor = 'brand' | 'success' | 'warning' | 'error' | 'info' | 'gray'
type BadgeSize = 'sm' | 'md'

const props = withDefaults(
  defineProps<{
    color?: BadgeColor
    size?: BadgeSize
    solid?: boolean
    className?: string
  }>(),
  {
    color: 'gray',
    size: 'sm',
    solid: false,
    className: '',
  },
)

const baseClass = 'inline-flex items-center justify-center rounded-full font-medium'

const sizeClass = computed(() =>
  props.size === 'md' ? 'px-3 py-1 text-theme-sm' : 'px-2.5 py-0.5 text-theme-xs',
)

const lightColors: Record<BadgeColor, string> = {
  brand: 'bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400',
  success: 'bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500',
  warning: 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-orange-400',
  error: 'bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500',
  info: 'bg-blue-light-50 text-blue-light-600 dark:bg-blue-light-500/15 dark:text-blue-light-500',
  gray: 'bg-gray-100 text-gray-700 dark:bg-white/5 dark:text-white/80',
}

const solidColors: Record<BadgeColor, string> = {
  brand: 'bg-brand-500 text-white',
  success: 'bg-success-500 text-white',
  warning: 'bg-warning-500 text-white',
  error: 'bg-error-500 text-white',
  info: 'bg-blue-light-500 text-white',
  gray: 'bg-gray-700 text-white dark:bg-white/10',
}

const colorClass = computed(() => (props.solid ? solidColors[props.color] : lightColors[props.color]))
</script>
