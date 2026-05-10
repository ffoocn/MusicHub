<template>
  <div>
    <div @click="toggle()" ref="button">
      <slot name="dropdown-button"></slot>
    </div>
    <div class="z-10" ref="content">
      <div
        v-show="isOpen"
        class="p-2 bg-white border border-gray-200 rounded-2xl shadow-lg dark:border-gray-800 dark:bg-gray-dark w-40"
      >
        <div
          class="space-y-1"
          role="menu"
          aria-orientation="vertical"
          aria-labelledby="options-menu"
        >
          <slot name="dropdown-content"></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { createPopper, type Instance as PopperInstance } from '@popperjs/core'

const isOpen = ref(false)
const button = ref<HTMLElement | null>(null)
const content = ref<HTMLElement | null>(null)
const popperInstance = ref<PopperInstance | null>(null)

const toggle = () => {
  isOpen.value = !isOpen.value
  if (popperInstance.value) {
    popperInstance.value.update()
  }
}

const close = (event: MouseEvent) => {
  if (button.value && !button.value.contains(event.target as Node)) {
    isOpen.value = false
  }
}

defineSlots<{
  'dropdown-button'(): any
  'dropdown-content'(): any
}>()

onMounted(() => {
  document.addEventListener('click', close)

  if (button.value && content.value) {
    popperInstance.value = createPopper(button.value, content.value, {
      placement: 'bottom-end',
      modifiers: [
        {
          name: 'offset',
          options: {
            offset: [0, 4],
          },
        },
      ],
    })
  }
})

onUnmounted(() => {
  document.removeEventListener('click', close)

  if (popperInstance.value) {
    popperInstance.value.destroy()
    popperInstance.value = null
  }
})
</script>

<style></style>
