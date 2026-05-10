<template>
  <transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="translate-y-4 opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="translate-y-4 opacity-0"
  >
    <div
      v-if="player.current"
      class="fixed inset-x-0 bottom-0 z-99999 border-t border-gray-200 bg-white/95 px-3 py-3 shadow-theme-xl backdrop-blur-xl dark:border-gray-800 dark:bg-gray-900/95 sm:px-5"
    >
      <div class="mx-auto flex max-w-(--breakpoint-2xl) flex-col gap-3 xl:flex-row xl:items-center">
        <div class="flex min-w-0 items-center gap-3 xl:w-[320px]">
          <div
            class="flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-gray-100 text-gray-400 dark:bg-white/5 dark:text-gray-500"
          >
            <img
              v-if="player.current.cover_url"
              :src="player.current.cover_url"
              alt=""
              class="size-full object-cover"
            />
            <span v-else class="text-lg">♪</span>
          </div>

          <div class="min-w-0 flex-1">
            <p class="truncate text-theme-sm font-semibold text-gray-900 dark:text-white/90">
              {{ player.current.name }}
            </p>
            <div class="mt-1 flex min-w-0 items-center gap-2">
              <span class="truncate text-theme-xs text-gray-500 dark:text-gray-400">
                {{ player.current.artist }}
              </span>
              <MusicBadge v-if="player.current.source === 'local'" color="success" className="shrink-0">
                本地
              </MusicBadge>
              <MusicPlatformIcon v-else :platform="player.current.platform" size="xs" />
            </div>
          </div>
        </div>

        <div class="flex flex-1 items-center gap-3">
          <button
            type="button"
            class="flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-500 text-white shadow-theme-xs transition hover:bg-brand-600"
            @click="player.togglePlay"
            :aria-label="player.playing ? '暂停' : '播放'"
          >
            <svg v-if="player.playing" class="size-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 5.75C8 5.33579 8.33579 5 8.75 5H10.25C10.6642 5 11 5.33579 11 5.75V18.25C11 18.6642 10.6642 19 10.25 19H8.75C8.33579 19 8 18.6642 8 18.25V5.75Z" />
              <path d="M13 5.75C13 5.33579 13.3358 5 13.75 5H15.25C15.6642 5 16 5.33579 16 5.75V18.25C16 18.6642 15.6642 19 15.25 19H13.75C13.3358 19 13 18.6642 13 18.25V5.75Z" />
            </svg>
            <svg v-else class="ml-0.5 size-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8.25 5.917C8.25 5.137 9.108 4.659 9.773 5.067L18.12 10.15C18.76 10.54 18.76 11.46 18.12 11.85L9.773 16.933C9.108 17.341 8.25 16.863 8.25 16.083V5.917Z" />
            </svg>
          </button>

          <div class="flex min-w-0 flex-1 items-center gap-2">
            <span class="w-10 text-right text-theme-xs text-gray-500 dark:text-gray-400">
              {{ fmt(player.positionSec) }}
            </span>
            <input
              type="range"
              min="0"
              max="100"
              step="0.1"
              :value="player.positionPct"
              :style="rangeStyle(player.positionPct)"
              class="music-range flex-1"
              aria-label="播放进度"
              @input="onSeek"
            />
            <span class="w-10 text-theme-xs text-gray-500 dark:text-gray-400">
              {{ fmt(player.durationSec) }}
            </span>
          </div>
        </div>

        <div class="flex items-center justify-between gap-3 xl:w-[220px] xl:justify-end">
          <div class="flex items-center gap-2">
            <svg class="size-4 text-gray-500 dark:text-gray-400" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M4 9.75C4 9.33579 4.33579 9 4.75 9H8.19098L12.2197 5.31033C12.8625 4.72152 13.9 5.17742 13.9 6.04938V17.9506C13.9 18.8226 12.8625 19.2785 12.2197 18.6897L8.19098 15H4.75C4.33579 15 4 14.6642 4 14.25V9.75Z" />
              <path d="M16.3675 8.28253C16.6604 7.98964 17.1353 7.98964 17.4282 8.28253C19.476 10.3303 19.476 13.6697 17.4282 15.7175C17.1353 16.0104 16.6604 16.0104 16.3675 15.7175C16.0746 15.4246 16.0746 14.9497 16.3675 14.6569C17.8295 13.1949 17.8295 10.8051 16.3675 9.34315C16.0746 9.05025 16.0746 8.57543 16.3675 8.28253Z" />
            </svg>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              :value="player.volume * 100"
              :style="rangeStyle(player.volume * 100)"
              class="music-range w-24"
              aria-label="音量"
              @input="onVolume"
            />
          </div>

          <button
            type="button"
            class="flex size-10 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-white"
            aria-label="关闭播放器"
            @click="player.stop"
          >
            <svg class="size-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
              <path fill-rule="evenodd" clip-rule="evenodd" d="M6.21967 7.28033C5.92678 6.98744 5.92678 6.51256 6.21967 6.21967C6.51256 5.92678 6.98744 5.92678 7.28033 6.21967L12 10.9393L16.7197 6.21967C17.0126 5.92678 17.4874 5.92678 17.7803 6.21967C18.0732 6.51256 18.0732 6.98744 17.7803 7.28033L13.0607 12L17.7803 16.7197C18.0732 17.0126 18.0732 17.4874 17.7803 17.7803C17.4874 18.0732 17.0126 18.0732 16.7197 17.7803L12 13.0607L7.28033 17.7803C6.98744 18.0732 6.51256 18.0732 6.21967 17.7803C5.92678 17.4874 5.92678 17.0126 6.21967 16.7197L10.9393 12L6.21967 7.28033Z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { usePlayerStore } from '@/stores/player'
import MusicBadge from '@/components/music/MusicBadge.vue'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'

const player = usePlayerStore()

const fmt = (sec: number) => {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const onSeek = (event: Event) => {
  if (!player.durationSec) return
  const pct = Number((event.target as HTMLInputElement).value)
  player.seek((pct / 100) * player.durationSec)
}

const onVolume = (event: Event) => {
  const value = Number((event.target as HTMLInputElement).value)
  player.setVolume(value / 100)
}

const rangeStyle = (value: number) => ({
  '--range-fill': `${Math.max(0, Math.min(100, value || 0))}%`,
})
</script>
