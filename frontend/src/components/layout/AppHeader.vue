<template>
  <header
    class="sticky top-0 z-99999 flex w-full border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 xl:border-b"
  >
    <div class="flex grow flex-col items-center justify-between xl:flex-row xl:px-6">
      <div
        class="flex w-full items-center justify-between gap-2 border-b border-gray-200 px-3 py-3 dark:border-gray-800 sm:gap-4 xl:justify-normal xl:border-b-0 xl:px-0 lg:py-4"
      >
        <!--
          Sidebar toggle 按钮：完全对齐 TailAdmin Dashboard 标准
            h-11 w-11 + rounded-lg + border + 灰描边
            （取消旧实现里小屏 h-10 无 border 的 fallback —— 始终 border 视觉更稳定）
        -->
        <button
          @click="handleToggle"
          class="z-9999 flex h-11 w-11 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 transition hover:bg-gray-100 hover:text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white"
          :class="[
            isMobileOpen
              ? 'bg-gray-100 dark:bg-gray-800 lg:bg-transparent dark:lg:bg-transparent'
              : '',
          ]"
          aria-label="Toggle sidebar"
        >
          <MenuIcon v-if="!isMobileOpen" />
          <svg
            v-else
            class="fill-current"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M6.21967 7.28131C5.92678 6.98841 5.92678 6.51354 6.21967 6.22065C6.51256 5.92775 6.98744 5.92775 7.28033 6.22065L11.999 10.9393L16.7176 6.22078C17.0105 5.92789 17.4854 5.92788 17.7782 6.22078C18.0711 6.51367 18.0711 6.98855 17.7782 7.28144L13.0597 12L17.7782 16.7186C18.0711 17.0115 18.0711 17.4863 17.7782 17.7792C17.4854 18.0721 17.0105 18.0721 16.7176 17.7792L11.999 13.0607L7.28033 17.7794C6.98744 18.0722 6.51256 18.0722 6.21967 17.7794C5.92678 17.4865 5.92678 17.0116 6.21967 16.7187L10.9384 12L6.21967 7.28131Z"
            />
          </svg>
        </button>

        <router-link to="/discover" class="flex items-center gap-3 xl:hidden">
          <span class="flex size-9 items-center justify-center rounded-xl bg-brand-500 text-white">
            <HeadphoneAltIcon />
          </span>
          <span class="text-base font-semibold text-gray-900 dark:text-white">MusicHub</span>
        </router-link>

        <!--
          顶栏智能搜索：关键词搜索 + 链接识别（歌曲入队 / 歌单专辑跳转）。
          位置 / 宽度对齐 TailAdmin Dashboard：搜索框紧贴在 sidebar toggle 之后，左对齐，
          自身固定 xl:w-[430px]，不再 flex-1 撑开。
        -->
        <SearchBar />

        <button
          @click="toggleApplicationMenu"
          class="z-9999 flex h-10 w-10 items-center justify-center rounded-lg text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800 xl:hidden"
          aria-label="Toggle header actions"
        >
          <MoreDots />
        </button>
      </div>

      <div
        :class="[isApplicationMenuOpen ? 'flex' : 'hidden']"
        class="w-full items-center justify-end gap-2 px-5 py-4 shadow-theme-md xl:flex xl:px-0 xl:shadow-none 2xsm:gap-3"
      >
        <ThemeToggler />
        <NotificationDropdown />
        <HeaderAccountChip />
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { HeadphoneAltIcon, MenuIcon, MoreDots } from '@/icons'
import { useSidebar } from '@/composables/useSidebar'
import ThemeToggler from '@/components/common/ThemeToggler.vue'
import HeaderAccountChip from '@/components/layout/header/HeaderAccountChip.vue'
import NotificationDropdown from '@/components/layout/header/NotificationDropdown.vue'
import SearchBar from '@/components/layout/header/SearchBar.vue'

const route = useRoute()
const { toggleSidebar, toggleMobileSidebar, isMobileOpen } = useSidebar()
const isApplicationMenuOpen = ref(false)

const currentTitle = computed(() => (route.meta?.title as string) || '发现')

const handleToggle = () => {
  if (window.innerWidth >= 1280) toggleSidebar()
  else toggleMobileSidebar()
}

const toggleApplicationMenu = () => {
  isApplicationMenuOpen.value = !isApplicationMenuOpen.value
}

watchEffect(() => {
  document.title = `MusicHub · ${currentTitle.value}`
})
</script>
