<template>
  <div class="flex flex-wrap gap-2">
    <span
      v-for="p in platforms"
      :key="p.key"
      :class="[
        'inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-theme-sm font-medium',
        getStatus(p.key)
          ? 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500'
          : 'bg-gray-100 text-gray-600 dark:bg-white/5 dark:text-gray-400',
      ]"
    >
      <MusicPlatformIcon :platform="p.key" size="xs" />
      <CheckCircle v-if="getStatus(p.key)" class="size-4" />
      <XCircle v-else class="size-4" />
      {{ getStatus(p.key)?.nickname || '未登录' }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { CheckCircle, XCircle } from 'lucide-vue-next'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import { useAccountsStore } from '@/stores/accounts'

const platforms = [
  { key: 'netease' as const },
  { key: 'qq' as const },
]

const store = useAccountsStore()
const accounts = computed(() => store.accounts)

const getStatus = (key: 'netease' | 'qq') =>
  accounts.value.find((a) => a.platform === key && a.is_valid)

onMounted(() => {
  store.ensureLoaded()
})
</script>
