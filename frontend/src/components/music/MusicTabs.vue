<template>
  <div :class="['flex flex-wrap gap-2 rounded-xl bg-gray-100 p-1 dark:bg-white/[0.03]', className]">
    <button
      v-for="tab in tabs"
      :key="tab.value"
      type="button"
      :disabled="tab.disabled"
      :class="[
        'inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-theme-sm font-medium transition',
        modelValue === tab.value
          ? 'bg-white text-gray-900 shadow-theme-xs dark:bg-gray-800 dark:text-white/90'
          : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white/90',
        tab.disabled ? 'cursor-not-allowed opacity-50' : '',
      ]"
      @click="selectTab(tab.value, tab.disabled)"
    >
      <span>{{ tab.label }}</span>
      <span
        v-if="tab.badge !== undefined"
        class="rounded-full bg-gray-100 px-2 py-0.5 text-theme-xs text-gray-600 dark:bg-white/10 dark:text-gray-300"
      >
        {{ tab.badge }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
export interface MusicTabItem {
  label: string
  value: string
  badge?: string | number
  disabled?: boolean
}

withDefaults(
  defineProps<{
    tabs: MusicTabItem[]
    modelValue: string
    className?: string
  }>(),
  {
    className: '',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
}>()

const selectTab = (value: string, disabled?: boolean) => {
  if (disabled) return
  emit('update:modelValue', value)
  emit('change', value)
}
</script>
