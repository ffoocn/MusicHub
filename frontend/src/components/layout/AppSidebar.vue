<template>
  <aside
    :class="[
      'fixed left-0 top-0 z-99999 mt-0 flex h-screen flex-col overflow-hidden border-r border-gray-200 bg-white px-5 text-gray-900 transition-[width,transform] duration-300 ease-in-out dark:border-gray-800 dark:bg-gray-900',
      isExpanded || isMobileOpen || isHovered ? 'w-[290px]' : 'w-[90px]',
      isMobileOpen ? 'translate-x-0' : '-translate-x-full',
      'xl:translate-x-0',
    ]"
    @mouseenter="!isExpanded && setIsHovered(true)"
    @mouseleave="setIsHovered(false)"
  >
    <div
      :class="[
        'flex shrink-0 items-center gap-2 pb-7 pt-8',
        !showContent ? 'xl:justify-center' : 'justify-start',
      ]"
    >
      <router-link to="/discover" class="flex min-w-0 items-center gap-2.5">
        <!--
          Sidebar 顶部 logo：进一步贴齐 TailAdmin Dashboard 原版（icon ~32px + 较大粗体文字）。
            - 容器 size-8 (32px) + rounded-lg，内部 icon size-5 (20px)；
            - 右侧文字 text-xl font-bold，显著比 base 字号醒目，对齐原版"TailAdmin"字样的视觉权重。
        -->
        <span
          class="flex size-8 items-center justify-center rounded-lg bg-brand-500 text-white shadow-theme-xs"
        >
          <HeadphoneAltIcon class="size-5" />
        </span>
        <span :class="logoLabelClass">
          MusicHub
        </span>
      </router-link>
    </div>

    <div class="flex min-h-0 flex-1 flex-col overflow-y-auto pb-4 duration-300 ease-linear no-scrollbar">
      <nav class="mb-6">
        <div class="flex flex-col gap-6">
          <div>
            <h2
              :class="[
                'mb-4 flex text-xs uppercase leading-[20px] text-gray-400',
                !showContent ? 'xl:justify-center' : 'justify-start',
              ]"
            >
              <span :class="sectionLabelClass">Workspace</span>
              <MoreDots v-if="!showContent" class="size-6" />
            </h2>

            <ul class="flex flex-col gap-1">
              <li v-for="item in primaryItems" :key="item.path">
                <router-link
                  :to="item.path"
                  :class="[
                    'menu-item group',
                    isActive(item.path) ? 'menu-item-active' : 'menu-item-inactive',
                    !showContent ? 'xl:justify-center xl:gap-0' : 'xl:justify-start',
                  ]"
                >
                  <span
                    :class="[
                      'flex size-6 shrink-0 items-center justify-center',
                      isActive(item.path) ? 'menu-item-icon-active' : 'menu-item-icon-inactive',
                    ]"
                  >
                    <component :is="item.icon" class="size-6" />
                  </span>
                  <span
                    :class="[navLabelClass, 'menu-item-text flex min-w-0 items-center gap-2']"
                  >
                    <span class="truncate">{{ item.name }}</span>
                    <span
                      v-if="item.badge && tasksStore.runningCount > 0"
                      class="ml-auto inline-flex rounded-full bg-brand-500 px-2 py-0.5 text-xs font-medium text-white"
                    >
                      {{ tasksStore.runningCount > 99 ? '99+' : tasksStore.runningCount }}
                    </span>
                  </span>
                </router-link>
              </li>
            </ul>
          </div>

          <div>
            <h2
              :class="[
                'mb-4 flex text-xs uppercase leading-[20px] text-gray-400',
                !showContent ? 'xl:justify-center' : 'justify-start',
              ]"
            >
              <span :class="sectionLabelClass">System</span>
              <MoreDots v-if="!showContent" class="size-6" />
            </h2>

            <ul class="flex flex-col gap-1">
              <li v-for="item in systemItems" :key="item.path">
                <router-link
                  :to="item.path"
                  :class="[
                    'menu-item group',
                    isActive(item.path) ? 'menu-item-active' : 'menu-item-inactive',
                    !showContent ? 'xl:justify-center xl:gap-0' : 'xl:justify-start',
                  ]"
                >
                  <span
                    :class="[
                      'flex size-6 shrink-0 items-center justify-center',
                      isActive(item.path) ? 'menu-item-icon-active' : 'menu-item-icon-inactive',
                    ]"
                  >
                    <component :is="item.icon" class="size-6" />
                  </span>
                  <span :class="[navLabelClass, 'menu-item-text']">
                    {{ item.name }}
                  </span>
                </router-link>
              </li>
            </ul>
          </div>
        </div>
      </nav>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  FolderIcon,
  GridIcon,
  HeadphoneAltIcon,
  MoreDots,
  RefreshIcon,
  SettingsIcon,
  TaskIcon,
} from '@/icons'
import { useSidebar } from '@/composables/useSidebar'
import { useTasksStore } from '@/stores/tasks'

const route = useRoute()
const tasksStore = useTasksStore()
const { isExpanded, isMobileOpen, isHovered, setIsHovered } = useSidebar()
const showContent = computed(() => isExpanded.value || isHovered.value || isMobileOpen.value)
const contentMotionClass = computed(() => [
  'min-w-0 overflow-hidden whitespace-nowrap transition-[opacity,max-width,transform] duration-200 ease-in-out',
  showContent.value ? 'max-w-[180px] translate-x-0 opacity-100' : 'max-w-0 -translate-x-1 opacity-0',
])
const logoLabelClass = computed(() => [
  ...contentMotionClass.value,
  'truncate text-xl font-bold text-gray-900 dark:text-white',
])
const navLabelClass = computed(() => [
  ...contentMotionClass.value,
])
const sectionLabelClass = computed(() => [
  'overflow-hidden whitespace-nowrap transition-[opacity,max-width,transform] duration-200 ease-in-out',
  showContent.value ? 'max-w-[120px] translate-x-0 opacity-100' : 'max-w-0 -translate-x-1 opacity-0',
])

const primaryItems = [
  { icon: GridIcon, name: '发现', path: '/discover' },
  { icon: FolderIcon, name: '本地库', path: '/library' },
  { icon: RefreshIcon, name: '订阅与自动化', path: '/subscriptions' },
  { icon: TaskIcon, name: '下载任务', path: '/tasks', badge: true },
]

const systemItems = [
  { icon: SettingsIcon, name: '设置', path: '/settings' },
]

const isActive = (path: string) => {
  if (path === '/discover') return route.path === '/' || route.path === '/discover'
  return route.path === path || route.path.startsWith(`${path}/`)
}

</script>
