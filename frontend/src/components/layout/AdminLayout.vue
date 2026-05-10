<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-950 xl:flex">
    <app-sidebar />
    <Backdrop />
    <div
      class="min-w-0 flex-1 bg-gray-50 transition-[margin-left] duration-300 ease-in-out dark:bg-gray-950"
      :class="[isExpanded || isHovered ? 'xl:ml-[290px]' : 'xl:ml-[90px]']"
    >
      <app-header @logout="$emit('logout')" />
      <div class="mx-auto w-full max-w-(--breakpoint-2xl) min-w-0 p-4 pb-32 md:p-6 md:pb-32">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import { useSidebar } from '@/composables/useSidebar'
import Backdrop from './Backdrop.vue'
const { isExpanded, isHovered } = useSidebar()

defineEmits(['logout'])
</script>
