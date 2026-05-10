<template>
  <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
    <div
      :class="['h-full rounded-full transition-all', colorClass]"
      :style="{ width: `${safeValue}%` }"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    value: number
    color?: 'brand' | 'success' | 'warning' | 'error' | 'info'
  }>(),
  {
    color: 'brand',
  },
)

const safeValue = computed(() => Math.max(0, Math.min(100, props.value)))
const colorClass = computed(() => {
  if (props.color === 'success') return 'bg-success-500'
  if (props.color === 'warning') return 'bg-warning-500'
  if (props.color === 'error') return 'bg-error-500'
  if (props.color === 'info') return 'bg-blue-light-500'
  return 'bg-brand-500'
})
</script>
