<template>
  <div class="space-y-6">
    <div class="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
      <aside class="rounded-2xl border border-gray-200 bg-white p-3 shadow-theme-xs dark:border-gray-800 dark:bg-white/[0.03]">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="[
            'flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-theme-sm font-medium transition',
            activeTab === tab.key
              ? 'bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400'
              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-white/[0.03] dark:hover:text-white/90',
          ]"
          @click="activeTab = tab.key"
        >
          <component :is="tab.icon" class="size-5 shrink-0" />
          <span>{{ tab.label }}</span>
        </button>
      </aside>

      <section class="min-w-0">
        <AccountManager v-if="activeTab === 'account'" />
        <DownloadSettings v-else-if="activeTab === 'download'" />
        <OrganizeSettings v-else />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Download, FolderTree, UserRound } from 'lucide-vue-next'
import AccountManager from '@/components/AccountManager.vue'
import DownloadSettings from '@/components/DownloadSettings.vue'
import OrganizeSettings from '@/components/OrganizeSettings.vue'

type SettingsTab = 'account' | 'download' | 'organize'

const activeTab = ref<SettingsTab>('account')

const tabs = [
  { key: 'account' as const, label: '账号管理', icon: UserRound },
  { key: 'download' as const, label: '下载偏好', icon: Download },
  { key: 'organize' as const, label: '目录与命名', icon: FolderTree },
]
</script>
