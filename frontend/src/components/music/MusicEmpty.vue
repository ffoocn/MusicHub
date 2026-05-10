<template>
  <div class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-200 px-6 py-10 text-center dark:border-gray-800">
    <div class="mb-3 flex size-12 items-center justify-center rounded-full bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-400">
      <slot name="icon">—</slot>
    </div>
    <h3 class="text-sm font-medium text-gray-800 dark:text-white/90">{{ title }}</h3>
    <p v-if="description" class="mt-1 max-w-md text-theme-sm text-gray-500 dark:text-gray-400">
      {{ description }}
    </p>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
  }>(),
  {
    title: '暂无数据',
    description: '',
  },
)
</script>
