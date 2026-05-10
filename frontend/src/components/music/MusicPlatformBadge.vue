<template>
  <MusicBadge :color="color" :size="size" :solid="solid" :className="className">
    {{ label }}
  </MusicBadge>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MusicBadge from '@/components/music/MusicBadge.vue'

type Platform = 'netease' | 'qq' | string
type BadgeColor = 'brand' | 'success' | 'warning' | 'error' | 'info' | 'gray'

const props = withDefaults(
  defineProps<{
    platform: Platform
    size?: 'sm' | 'md'
    solid?: boolean
    className?: string
  }>(),
  {
    size: 'sm',
    solid: false,
    className: '',
  },
)

const label = computed(() => {
  if (props.platform === 'netease') return '网易云'
  if (props.platform === 'qq') return 'QQ 音乐'
  return props.platform || '未知平台'
})

const color = computed<BadgeColor>(() => {
  if (props.platform === 'netease') return 'error'
  if (props.platform === 'qq') return 'brand'
  return 'gray'
})
</script>
