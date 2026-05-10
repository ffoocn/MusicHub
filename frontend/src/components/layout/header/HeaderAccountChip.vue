<template>
  <!--
    顶栏右上「账号 chip」+ 下拉菜单（参考 TailAdmin User Dropdown）：
      - 触发器：头像 + 平台徽章 + 昵称 + chevron，hover 浅灰背景，无外边框；
      - Dropdown：
          1) 顶部用户摘要（主账号头像 + 昵称 + 平台 / VIP 标签）
          2) 已登录账号列表（每个平台一行，含 VIP 图标）
          3) 「实时连接」状态行（来自 tasksStore.connected）
          4) 菜单项：设置 / 管理账号
  -->
  <div class="relative" ref="rootRef">
    <!--
      触发器尺寸 / 间距对齐 TailAdmin User Dropdown：
        - 头像 h-11 w-11，与右侧通知 / 设置等圆形按钮等高
        - 头像 mr-3、昵称 mr-1，按钮本身无 padding 与 hover bg，仅 hover 改文字色
    -->
    <button
      type="button"
      class="flex items-center text-gray-700 transition dark:text-gray-400"
      :aria-label="primaryAccount ? `已登录 ${platformLabel(primaryAccount.platform)}` : '未登录'"
      @click="toggle"
    >
      <span class="relative mr-3 flex size-11 items-center justify-center">
        <img
          v-if="primaryAvatar"
          :src="primaryAvatar"
          :alt="primaryAccount?.nickname || ''"
          class="size-11 rounded-full object-cover"
          referrerpolicy="no-referrer"
          @error="onImgError"
        />
        <span
          v-else
          class="flex size-11 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-600 text-white"
        >
          <UserRound class="size-6" />
        </span>
        <!--
          头像右下角小徽章：外层用实心白圆作为底盘，让平台 icon 不会从透明边缘漏出来；
          深色模式底盘色对齐 dropdown 暗色（gray-900）。
        -->
        <span
          v-if="primaryAccount"
          class="absolute -bottom-0.5 -right-0.5 inline-flex items-center justify-center rounded-full bg-white p-0.5 dark:bg-gray-900"
        >
          <MusicPlatformIcon :platform="primaryAccount.platform" size="xs" />
        </span>
      </span>

      <!--
        触发器只显示昵称：头像右下角已经有平台 logo 徽章，副标题再写一遍平台名属于冗余信息。
      -->
      <span class="mr-1 hidden max-w-[120px] truncate text-left text-theme-sm font-medium text-gray-700 sm:block dark:text-gray-400">
        {{ primaryAccount?.nickname || '未登录' }}
      </span>

      <ChevronDown
        :class="['hidden size-4 text-gray-500 transition sm:block dark:text-gray-400', open ? 'rotate-180' : '']"
      />
    </button>

    <div
      v-if="open"
      class="absolute right-0 z-9999 mt-2 w-[300px] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark"
    >
      <!-- 顶部主账号摘要 -->
      <div class="flex items-center gap-3 px-4 py-4">
        <span class="relative flex size-12 items-center justify-center">
          <img
            v-if="primaryAvatar"
            :src="primaryAvatar"
            :alt="primaryAccount?.nickname || ''"
            class="size-12 rounded-full object-cover"
            referrerpolicy="no-referrer"
            @error="onImgError"
          />
          <span
            v-else
            class="flex size-12 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-600 text-white"
          >
            <UserRound class="size-6" />
          </span>
          <span
            v-if="primaryAccount"
            class="absolute -bottom-0.5 -right-0.5 inline-flex items-center justify-center rounded-full bg-white p-0.5 dark:bg-gray-dark"
          >
            <MusicPlatformIcon :platform="primaryAccount.platform" size="xs" />
          </span>
        </span>
        <div class="min-w-0 flex-1">
          <p class="truncate text-theme-sm font-semibold text-gray-800 dark:text-white/90">
            {{ primaryAccount?.nickname || '未登录' }}
          </p>
        </div>
      </div>

      <!-- 已登录账号列表 -->
      <div v-if="store.validAccounts.length" class="border-t border-gray-100 px-3 py-3 dark:border-gray-800">
        <p class="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
          已登录账号
        </p>
        <div class="space-y-2">
          <div
            v-for="acc in store.validAccounts"
            :key="acc.platform"
            class="flex items-center gap-3 rounded-xl border border-gray-100 bg-gray-50 px-3 py-2 dark:border-gray-800 dark:bg-white/[0.02]"
          >
            <span class="relative flex size-9 items-center justify-center">
              <img
                v-if="avatarFor(acc)"
                :src="avatarFor(acc) as string"
                :alt="acc.nickname || ''"
                class="size-9 rounded-full object-cover"
                referrerpolicy="no-referrer"
                @error="onImgError"
              />
              <span
                v-else
                class="flex size-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-600 text-white"
              >
                <UserRound class="size-4" />
              </span>
              <span
                class="absolute -bottom-0.5 -right-0.5 inline-flex items-center justify-center rounded-full bg-white p-0.5 dark:bg-gray-dark"
              >
                <MusicPlatformIcon :platform="acc.platform" size="xs" />
              </span>
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <p class="truncate text-theme-sm font-semibold text-gray-800 dark:text-white/90">
                  {{ acc.nickname || '匿名用户' }}
                </p>
                <img
                  v-for="icon in acc.vip_icons || []"
                  :key="icon"
                  :src="icon"
                  class="h-4 w-auto shrink-0"
                  referrerpolicy="no-referrer"
                  @error="onIconError($event, icon)"
                />
              </div>
              <p class="mt-0.5 truncate text-theme-xs text-gray-500 dark:text-gray-400">
                {{ platformLabel(acc.platform) }}<span v-if="!hasIcons(acc)"> · {{ formatVip(acc) }}</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 实时连接状态行（替代原顶栏的「实时连接」chip） -->
      <div class="border-t border-gray-100 dark:border-gray-800">
        <div class="flex items-center justify-between px-4 py-2.5">
          <span class="flex items-center gap-2 text-theme-sm font-medium text-gray-700 dark:text-gray-300">
            <span class="relative flex size-2.5">
              <span
                v-if="tasksStore.connected"
                class="absolute inline-flex size-full animate-ping rounded-full bg-success-400 opacity-60"
              ></span>
              <span
                :class="tasksStore.connected ? 'bg-success-500' : 'bg-warning-500'"
                class="relative inline-flex size-2.5 rounded-full"
              ></span>
            </span>
            实时连接
          </span>
          <span class="text-theme-xs text-gray-500 dark:text-gray-400">
            {{ tasksStore.connected ? '已连接' : '连接中…' }}
          </span>
        </div>
      </div>

      <!-- 菜单项：设置 / 管理账号 -->
      <div class="border-t border-gray-100 p-2 dark:border-gray-800">
        <router-link
          to="/settings"
          class="flex items-center gap-3 rounded-lg px-3 py-2 text-theme-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.04]"
          @click="close"
        >
          <SettingsIcon class="size-4 text-gray-500 dark:text-gray-400" />
          设置
        </router-link>
        <router-link
          to="/settings"
          class="flex items-center gap-3 rounded-lg px-3 py-2 text-theme-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.04]"
          @click="close"
        >
          <UserRound class="size-4 text-gray-500 dark:text-gray-400" />
          管理账号
        </router-link>
        <button
          type="button"
          class="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-theme-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.04]"
          @click="logout"
        >
          <LogOut class="size-4 text-gray-500 dark:text-gray-400" />
          退出访问
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ChevronDown, LogOut, UserRound } from 'lucide-vue-next'
import { SettingsIcon } from '@/icons'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import { useAccountsStore } from '@/stores/accounts'
import { useTasksStore } from '@/stores/tasks'
import type { AccountStatus } from '@/api'

const store = useAccountsStore()
const tasksStore = useTasksStore()

const emit = defineEmits<{
  logout: []
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

const failedAvatars = ref<Set<string>>(new Set())

const primaryAccount = computed<AccountStatus | undefined>(() => {
  return (
    store.validAccounts.find((a) => a.platform === 'netease') ||
    store.validAccounts[0]
  )
})

const primaryAvatar = computed(() => avatarFor(primaryAccount.value))

const platformLabel = (p: string) => {
  if (p === 'netease') return '网易云音乐'
  if (p === 'qq') return 'QQ 音乐'
  return p
}

const hasIcons = (acc: AccountStatus) =>
  Array.isArray(acc.vip_icons) && acc.vip_icons.length > 0

const formatVip = (acc: AccountStatus) => {
  const v = acc.vip_type
  if (v == null) return '账号已登录'
  if (acc.platform === 'netease') {
    if (v === 0) return '普通用户'
    if (v === 110) return '黑胶 VIP'
    return `VIP ${v}`
  }
  if (v === 0) return '普通用户'
  return `VIP ${v}`
}

const onIconError = (e: Event, url: string) => {
  const el = e.target as HTMLImageElement
  el.style.display = 'none'
  console.warn('[vip-icon] failed to load', url)
}

const avatarFor = (acc?: AccountStatus): string | null => {
  if (!acc || !acc.avatar_url) return null
  if (failedAvatars.value.has(acc.avatar_url)) return null
  return acc.avatar_url
}

const onImgError = (e: Event) => {
  const img = e.target as HTMLImageElement
  if (img.src) failedAvatars.value.add(img.src)
}

const toggle = () => {
  open.value = !open.value
}

const close = () => {
  open.value = false
}

const logout = () => {
  close()
  emit('logout')
}

const onClickOutside = (e: MouseEvent) => {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) close()
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  store.ensureLoaded()
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>
