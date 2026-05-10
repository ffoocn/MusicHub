<template>
  <label :for="forId" :class="['block', className]">
    <span v-if="label" class="mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300">
      {{ label }}
      <span v-if="required" class="text-error-500">*</span>
    </span>
    <slot />
    <span v-if="error" class="mt-1.5 block text-theme-xs text-error-500">{{ error }}</span>
    <span v-else-if="hint" class="mt-1.5 block text-theme-xs text-gray-500 dark:text-gray-400">
      {{ hint }}
    </span>
  </label>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string
    hint?: string
    error?: string
    forId?: string
    required?: boolean
    className?: string
  }>(),
  {
    label: '',
    hint: '',
    error: '',
    forId: undefined,
    required: false,
    className: '',
  },
)
</script>
