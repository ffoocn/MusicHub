<template>
  <div
    v-if="isMobileOpen"
    class="fixed inset-0 z-99998 bg-gray-900/50 xl:hidden"
    @click="toggleMobileSidebar"
  ></div>
</template>

<script setup>
import { useSidebar } from '@/composables/useSidebar'
const { toggleMobileSidebar, isMobileOpen } = useSidebar()
</script>
