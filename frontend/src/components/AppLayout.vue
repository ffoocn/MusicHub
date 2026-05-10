<template>
  <div class="app-layout-legacy">
    <slot />
  </div>
</template>

<script setup lang="ts">
// 该组件为历史兼容壳层。当前业务已迁移到 layout/* 下的新布局组件。
</script>

<style scoped>
.app-layout-legacy {
  min-height: 100vh;
}
</style>
