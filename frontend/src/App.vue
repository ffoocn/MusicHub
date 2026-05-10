<template>
  <AccessLogin v-if="!checking && !authenticated" @authenticated="handleAuthenticated" />
  <div v-else-if="checking" class="flex min-h-screen items-center justify-center bg-gray-50 text-gray-500 dark:bg-gray-950 dark:text-gray-400">
    正在检查登录状态...
  </div>
  <ThemeProvider v-else>
    <SidebarProvider>
      <AdminLayout @logout="handleLogout">
        <router-view />
      </AdminLayout>
      <PlayerBar />
      <MusicToastHost />
    </SidebarProvider>
  </ThemeProvider>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useTasksStore } from '@/stores/tasks'
import { accessApi, clearAccessToken } from '@/api'
import AccessLogin from '@/components/AccessLogin.vue'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import SidebarProvider from '@/components/layout/SidebarProvider.vue'
import ThemeProvider from '@/components/layout/ThemeProvider.vue'
import PlayerBar from '@/components/PlayerBar.vue'
import MusicToastHost from '@/components/music/MusicToastHost.vue'

const checking = ref(true)
const authenticated = ref(false)
const tasksStore = useTasksStore()

const handleAuthenticated = async () => {
  authenticated.value = true
  await tasksStore.init()
}

const handleAuthRequired = () => {
  tasksStore.disconnect()
  authenticated.value = false
}

const handleLogout = async () => {
  try {
    await accessApi.logout()
  } catch {
    // 即使服务端会话已过期，也需要清理本地 token 并回到登录页。
  }
  clearAccessToken()
  tasksStore.disconnect()
  authenticated.value = false
}

onMounted(async () => {
  window.addEventListener('musichub-auth-required', handleAuthRequired)
  try {
    const res = await accessApi.status()
    if (res.authenticated) {
      await handleAuthenticated()
    }
  } finally {
    checking.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('musichub-auth-required', handleAuthRequired)
})
</script>
