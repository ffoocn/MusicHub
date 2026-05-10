<template>
  <div class="fixed right-4 top-20 z-999999 flex w-[calc(100%-2rem)] max-w-sm flex-col gap-3 sm:right-6">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      :class="[
        'rounded-xl border bg-white p-4 shadow-theme-lg dark:bg-gray-dark',
        toneClass(toast.tone),
      ]"
    >
      <p class="text-theme-sm font-medium text-gray-800 dark:text-white/90">
        {{ toast.message }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useMusicToast, type MusicToastTone } from './useMusicToast'

const { toasts } = useMusicToast()

const toneClass = (tone: MusicToastTone) => {
  if (tone === 'success') return 'border-success-200 dark:border-success-500/30'
  if (tone === 'warning') return 'border-warning-200 dark:border-warning-500/30'
  if (tone === 'error') return 'border-error-200 dark:border-error-500/30'
  return 'border-brand-200 dark:border-brand-500/30'
}
</script>
