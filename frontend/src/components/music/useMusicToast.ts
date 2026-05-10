import { ref } from 'vue'

export type MusicToastTone = 'success' | 'warning' | 'error' | 'info'

export interface MusicToastItem {
  id: number
  tone: MusicToastTone
  message: string
}

const toasts = ref<MusicToastItem[]>([])
let nextId = 1

const push = (tone: MusicToastTone, message: string, duration = 2400) => {
  const id = nextId++
  toasts.value.push({ id, tone, message })
  window.setTimeout(() => {
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }, duration)
}

export const useMusicToast = () => ({
  toasts,
  success: (message: string, duration?: number) => push('success', message, duration),
  warning: (message: string, duration?: number) => push('warning', message, duration),
  error: (message: string, duration?: number) => push('error', message, duration),
  info: (message: string, duration?: number) => push('info', message, duration),
})
