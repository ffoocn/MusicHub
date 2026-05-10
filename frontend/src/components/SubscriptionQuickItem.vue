<template>
  <div
    :class="[
      'rounded-2xl border bg-white p-4 shadow-theme-xs transition dark:bg-white/[0.03]',
      existing
        ? 'border-success-200 dark:border-success-500/30'
        : 'border-gray-200 hover:border-brand-200 dark:border-gray-800 dark:hover:border-brand-500/30',
    ]"
  >
    <div class="flex items-start justify-between gap-3">
      <h3 class="min-w-0 truncate text-theme-sm font-semibold text-gray-800 dark:text-white/90">
        {{ title }}
      </h3>
      <MusicBadge :color="badgeColor">{{ tag }}</MusicBadge>
    </div>
    <p class="mt-2 min-h-10 text-theme-sm leading-5 text-gray-500 dark:text-gray-400">
      {{ description }}
    </p>
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <MusicButton v-if="!existing" size="xs" :loading="loading" @click="$emit('click')">
        订阅
      </MusicButton>
      <template v-else>
        <MusicBadge color="success" size="md">已订阅</MusicBadge>
        <MusicButton size="xs" variant="outline" @click="$emit('sync')">立即同步</MusicButton>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MusicBadge from '@/components/music/MusicBadge.vue'
import MusicButton from '@/components/music/MusicButton.vue'

const props = defineProps<{
  title: string
  description: string
  tag: string
  tagType: 'success' | 'info' | 'warning' | 'default'
  loading?: boolean
  existing?: boolean
  existingId?: number
}>()

defineEmits<{
  click: []
  sync: []
}>()

const badgeColor = computed(() => {
  if (props.tagType === 'success') return 'success'
  if (props.tagType === 'info') return 'info'
  if (props.tagType === 'warning') return 'warning'
  return 'gray'
})
</script>
