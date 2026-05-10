<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-10 dark:bg-gray-950">
    <div class="w-full max-w-md rounded-3xl border border-gray-200 bg-white p-6 shadow-theme-lg dark:border-gray-800 dark:bg-gray-900">
      <div class="mb-6 flex items-center gap-3">
        <img src="/images/logo/logo-icon.svg" alt="MusicHub" class="size-12" />
        <div>
          <h1 class="text-xl font-semibold text-gray-900 dark:text-white">MusicHub</h1>
          <p class="text-theme-sm text-gray-500 dark:text-gray-400">输入访问密码后进入应用</p>
        </div>
      </div>

      <form class="space-y-4" @submit.prevent="submit">
        <MusicFormField label="访问密码" :error="error">
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            autofocus
            class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 outline-hidden focus:border-brand-500 focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:text-white/90"
            placeholder="请输入访问密码"
          />
        </MusicFormField>

        <MusicButton type="submit" size="md" class-name="w-full" :loading="loading">
          进入
        </MusicButton>

        <p class="text-theme-xs text-gray-500 dark:text-gray-400">
          初始密码为 <code class="rounded bg-gray-100 px-1.5 py-0.5 dark:bg-gray-800">musichub</code>，
          登录后可在「设置 → 安全」修改。
        </p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { accessApi, setAccessToken } from '@/api'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicFormField from '@/components/music/MusicFormField.vue'

const emit = defineEmits<{
  authenticated: []
}>()

const password = ref('')
const loading = ref(false)
const error = ref('')

const submit = async () => {
  error.value = ''
  if (!password.value) {
    error.value = '请输入访问密码'
    return
  }
  loading.value = true
  try {
    const res = await accessApi.login(password.value)
    setAccessToken(res.token)
    emit('authenticated')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '密码错误'
  } finally {
    loading.value = false
  }
}
</script>
