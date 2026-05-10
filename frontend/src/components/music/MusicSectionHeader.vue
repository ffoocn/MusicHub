<template>
  <div :class="['flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between', className]">
    <div class="min-w-0">
      <p v-if="eyebrow" class="mb-2 text-theme-xs font-semibold uppercase tracking-wide text-brand-500">
        {{ eyebrow }}
      </p>
      <h1 :class="[level === 'page' ? 'text-title-sm sm:text-title-md' : 'text-xl', 'font-semibold text-gray-900 dark:text-white/90']">
        {{ title }}
      </h1>
      <p v-if="description" class="mt-2 max-w-2xl text-theme-sm text-gray-500 dark:text-gray-400">
        {{ description }}
      </p>
    </div>
    <div v-if="$slots.actions" class="flex shrink-0 flex-wrap gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description?: string
    eyebrow?: string
    level?: 'page' | 'section'
    className?: string
  }>(),
  {
    description: '',
    eyebrow: '',
    level: 'section',
    className: '',
  },
)
</script>
