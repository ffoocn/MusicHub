<template>
  <div :class="['overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]', className]">
    <div v-if="$slots.toolbar" class="border-b border-gray-200 p-4 dark:border-gray-800">
      <slot name="toolbar" />
    </div>
    <div class="overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
        <thead v-if="$slots.head" class="bg-gray-50 dark:bg-white/[0.02]">
          <slot name="head" />
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          <slot />
        </tbody>
      </table>
    </div>
    <div v-if="$slots.footer" class="border-t border-gray-200 p-4 dark:border-gray-800">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    className?: string
  }>(),
  {
    className: '',
  },
)
</script>
