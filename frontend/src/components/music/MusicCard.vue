<template>
  <section
    :class="[
      'rounded-2xl border border-gray-200 bg-white shadow-theme-xs dark:border-gray-800 dark:bg-white/[0.03]',
      padded ? 'p-5 sm:p-6' : '',
      className,
    ]"
  >
    <div v-if="$slots.title || title || $slots.actions" class="mb-5 flex items-start justify-between gap-4">
      <div class="min-w-0">
        <h2 v-if="title" class="text-base font-semibold text-gray-800 dark:text-white/90">
          {{ title }}
        </h2>
        <p v-if="description" class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
          {{ description }}
        </p>
        <slot name="title" />
      </div>
      <div v-if="$slots.actions" class="shrink-0">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
    padded?: boolean
    className?: string
  }>(),
  {
    padded: true,
    className: '',
  },
)
</script>
