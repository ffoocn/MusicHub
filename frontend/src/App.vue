<template>
  <ThemeProvider>
    <SidebarProvider>
      <AdminLayout>
        <router-view />
      </AdminLayout>
      <PlayerBar />
      <MusicToastHost />
    </SidebarProvider>
  </ThemeProvider>
</template>

<script setup lang="ts">
import AdminLayout from '@/components/layout/AdminLayout.vue'
import SidebarProvider from '@/components/layout/SidebarProvider.vue'
import ThemeProvider from '@/components/layout/ThemeProvider.vue'
import PlayerBar from '@/components/PlayerBar.vue'
import MusicToastHost from '@/components/music/MusicToastHost.vue'
</script>
