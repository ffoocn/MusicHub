<template>
  <MusicCard
    title="访问密码"
    description="修改进入 MusicHub 的访问密码。修改成功后当前会话会失效，需要用新密码重新登录。"
  >
    <form class="grid max-w-xl gap-4" @submit.prevent="submit">
      <MusicFormField label="当前密码" :error="errors.current">
        <input
          v-model="currentPassword"
          type="password"
          autocomplete="current-password"
          class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 outline-hidden focus:border-brand-500 focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:text-white/90"
        />
      </MusicFormField>

      <MusicFormField label="新密码" hint="至少 6 位" :error="errors.next">
        <input
          v-model="newPassword"
          type="password"
          autocomplete="new-password"
          class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 outline-hidden focus:border-brand-500 focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:text-white/90"
        />
      </MusicFormField>

      <MusicFormField label="确认新密码" :error="errors.confirm">
        <input
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 outline-hidden focus:border-brand-500 focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:text-white/90"
        />
      </MusicFormField>

      <div>
        <MusicButton type="submit" :loading="saving">保存新密码</MusicButton>
      </div>
    </form>
  </MusicCard>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { accessApi, clearAccessToken } from '@/api'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import MusicFormField from '@/components/music/MusicFormField.vue'
import { useMusicToast } from '@/components/music/useMusicToast'

const toast = useMusicToast()
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const saving = ref(false)
const errors = reactive({
  current: '',
  next: '',
  confirm: '',
})

const validate = () => {
  errors.current = currentPassword.value ? '' : '请输入当前密码'
  errors.next = newPassword.value.length >= 6 ? '' : '新密码至少 6 位'
  errors.confirm = newPassword.value === confirmPassword.value ? '' : '两次输入的新密码不一致'
  return !errors.current && !errors.next && !errors.confirm
}

const submit = async () => {
  if (!validate()) return
  saving.value = true
  try {
    await accessApi.changePassword(currentPassword.value, newPassword.value)
    clearAccessToken()
    toast.success('访问密码已修改，请重新登录')
    window.dispatchEvent(new CustomEvent('musichub-auth-required'))
  } catch (e: any) {
    errors.current = e?.response?.data?.detail || '修改失败'
  } finally {
    saving.value = false
  }
}
</script>
