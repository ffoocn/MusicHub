<template>
  <div :class="['rounded-2xl border border-gray-200 bg-white p-4 text-center dark:border-gray-800 dark:bg-white/[0.03]', className]">
    <div :class="['mx-auto flex size-12 items-center justify-center rounded-full', iconClass]">
      <LoaderCircle v-if="status === 'pending'" class="size-6 animate-spin" />
      <Smartphone v-else-if="status === 'scanned'" class="size-6" />
      <CheckCircle v-else-if="status === 'success'" class="size-6" />
      <RefreshCw v-else-if="status === 'expired'" class="size-6" />
      <AlertCircle v-else class="size-6" />
    </div>
    <h3 class="mt-3 text-theme-sm font-semibold text-gray-900 dark:text-white/90">{{ stateTitle }}</h3>
    <p class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">{{ stateDescription }}</p>
    <div v-if="$slots.actions" class="mt-4 flex justify-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AlertCircle, CheckCircle, LoaderCircle, RefreshCw, Smartphone } from 'lucide-vue-next'

type QrLoginStatus = 'pending' | 'scanned' | 'success' | 'expired' | 'error' | 'unknown'

const props = withDefaults(
  defineProps<{
    status: QrLoginStatus
    title?: string
    description?: string
    className?: string
  }>(),
  {
    title: '',
    description: '',
    className: '',
  },
)

const stateTitle = computed(() => {
  if (props.title) return props.title
  if (props.status === 'pending') return '等待扫码'
  if (props.status === 'scanned') return '已扫码，等待确认'
  if (props.status === 'success') return '登录成功'
  if (props.status === 'expired') return '二维码已过期'
  if (props.status === 'error') return '登录失败'
  return '状态未知'
})

const stateDescription = computed(() => {
  if (props.description) return props.description
  if (props.status === 'pending') return '请使用对应音乐 App 扫描二维码。'
  if (props.status === 'scanned') return '请在手机端确认授权登录。'
  if (props.status === 'success') return '账号状态已保存，可以关闭窗口。'
  if (props.status === 'expired') return '请刷新二维码后重新扫码。'
  if (props.status === 'error') return '请重试，或改用 Cookie 导入。'
  return '暂未识别当前扫码状态。'
})

const iconClass = computed(() => {
  if (props.status === 'success') return 'bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500'
  if (props.status === 'expired') return 'bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-orange-400'
  if (props.status === 'error' || props.status === 'unknown') return 'bg-error-50 text-error-500 dark:bg-error-500/15'
  return 'bg-brand-50 text-brand-500 dark:bg-brand-500/15'
})
</script>
