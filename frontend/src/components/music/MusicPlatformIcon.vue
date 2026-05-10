<template>
  <span
    :class="['inline-flex shrink-0 items-center justify-center align-middle', className]"
    :style="{ width: pixelSize + 'px', height: pixelSize + 'px' }"
    :title="label"
    :aria-label="label"
  >
    <img
      :src="iconSrc"
      :alt="label"
      :width="pixelSize"
      :height="pixelSize"
      :style="{ width: pixelSize + 'px', height: pixelSize + 'px' }"
      class="block max-w-full max-h-full object-contain"
      loading="lazy"
    />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Platform = 'netease' | 'qq' | string
type IconSize = 'xs' | 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    platform: Platform
    size?: IconSize
    className?: string
  }>(),
  {
    size: 'sm',
    className: '',
  },
)

const label = computed(() => {
  if (props.platform === 'netease') return '网易云音乐'
  if (props.platform === 'qq') return 'QQ 音乐'
  return props.platform || '未知平台'
})

const iconSrc = computed(() => {
  if (props.platform === 'netease') return '/images/platforms/netease-music.png'
  if (props.platform === 'qq') return '/images/platforms/qq-music.png'
  return '/images/logo/logo-icon.svg'
})

// 用像素而不是 Tailwind size-* 类，避免外层 flex/grid 在某些断点
// 把图标拉伸成超大块（订阅/统计页里出现过的"巨大红圈"）。
const pixelSize = computed(() => {
  switch (props.size) {
    case 'xs':
      return 18
    case 'md':
      return 28
    case 'lg':
      return 36
    default:
      return 22
  }
})
</script>
