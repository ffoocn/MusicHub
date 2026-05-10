<template>
  <div class="space-y-6">
    <div class="grid gap-4 lg:grid-cols-2">
      <MusicCard v-for="p in platforms" :key="p.key" :title="p.label">
        <template #actions>
          <MusicBadge :color="getAccount(p.key)?.is_valid ? 'success' : getAccount(p.key) ? 'warning' : 'gray'">
            {{ getAccount(p.key)?.is_valid ? '有效' : getAccount(p.key) ? '已失效' : '未登录' }}
          </MusicBadge>
        </template>

        <div v-if="getAccount(p.key)" class="space-y-5">
          <div class="flex items-center gap-4 rounded-2xl bg-gray-50 px-4 py-3 dark:bg-white/[0.03]">
            <span class="relative flex size-14 items-center justify-center">
              <img
                v-if="getAccount(p.key)?.avatar_url"
                :src="getAccount(p.key)?.avatar_url as string"
                :alt="getAccount(p.key)?.nickname || ''"
                referrerpolicy="no-referrer"
                class="size-14 rounded-full object-cover"
              />
              <span
                v-else
                class="flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-600 text-white"
              >
                <UserRound class="size-6" />
              </span>
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <p class="truncate text-base font-semibold text-gray-800 dark:text-white/90">
                  {{ getAccount(p.key)?.nickname || '匿名用户' }}
                </p>
                <!-- 平台官方下发的真实 VIP 图标 -->
                <img
                  v-for="icon in getAccount(p.key)?.vip_icons || []"
                  :key="icon"
                  :src="icon"
                  class="h-5 w-auto shrink-0"
                  referrerpolicy="no-referrer"
                  @error="onIconError"
                />
              </div>
              <p
                v-if="!(getAccount(p.key)?.vip_icons?.length)"
                class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400"
              >
                {{ formatVip(p.key, getAccount(p.key)?.vip_type) }}
              </p>
            </div>
          </div>
          <div class="grid gap-3 text-theme-sm">
            <InfoRow label="账号 ID" :value="getAccount(p.key)?.user_id || '-'" />
          </div>

          <div class="flex flex-wrap gap-2">
            <MusicButton
              variant="outline"
              :loading="refreshingMap[p.key]"
              @click="refreshProfile(p.key)"
            >
              <RefreshCcw class="size-4" />
              刷新资料
            </MusicButton>
            <MusicButton variant="outline" @click="logout(p.key)">登出</MusicButton>
            <template v-if="p.key === 'qq'">
              <MusicButton variant="outline" @click="startLogin('qq', 'QQ 音乐', 'qq')">
                <QrCode class="size-4" />
                QQ 扫码
              </MusicButton>
              <MusicButton variant="outline" @click="startLogin('qq', 'QQ 音乐', 'wx')">
                <QrCode class="size-4" />
                微信扫码
              </MusicButton>
              <MusicButton variant="outline" @click="startLogin('qq', 'QQ 音乐', 'mobile')">
                <QrCode class="size-4" />
                QQ音乐APP扫码
              </MusicButton>
            </template>
          </div>
        </div>

        <div v-else class="rounded-xl border border-dashed border-gray-300 p-6 text-center dark:border-gray-700">
          <div class="mx-auto flex size-12 items-center justify-center rounded-full bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-400">
            <UserRound class="size-6" />
          </div>
          <p class="mt-3 text-theme-sm font-medium text-gray-800 dark:text-white/90">未登录</p>
          <p class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            登录后可同步每日推荐、收藏歌单和会员音质。
          </p>
          <div class="mt-5 flex flex-wrap justify-center gap-2">
            <MusicButton
              v-if="p.key === 'netease'"
              @click="startLogin('netease', '网易云音乐')"
            >
              <QrCode class="size-4" />
              扫码登录
            </MusicButton>
            <template v-else>
              <MusicButton @click="startLogin('qq', 'QQ 音乐', 'qq')">
                <QrCode class="size-4" />
                QQ 扫码
              </MusicButton>
              <MusicButton variant="outline" @click="startLogin('qq', 'QQ 音乐', 'wx')">
                <QrCode class="size-4" />
                微信扫码
              </MusicButton>
              <MusicButton variant="outline" @click="startLogin('qq', 'QQ 音乐', 'mobile')">
                <QrCode class="size-4" />
                QQ音乐APP扫码
              </MusicButton>
            </template>
          </div>
          <button
            type="button"
            class="mt-4 text-theme-sm font-medium text-brand-500 hover:text-brand-600"
            @click="openCookieImport(p.key, p.label)"
          >
            扫码不行？用 Cookie 导入
          </button>
        </div>
      </MusicCard>
    </div>

    <MusicModal
      :open="qrVisible"
      :title="qrTitle"
      :description="hintText"
      size="sm"
      @close="closeQrModal"
    >
      <div class="text-center">
        <div class="relative mx-auto flex size-64 items-center justify-center rounded-2xl bg-gray-50 p-3 dark:bg-white/5">
          <img
            v-if="qrImageDataUrl"
            :src="qrImageDataUrl"
            :class="['size-60 rounded-xl bg-white p-2 transition', isExpired ? 'opacity-30 blur-[2px]' : '']"
            alt="qrcode"
          />
          <div v-else class="text-theme-sm text-gray-500 dark:text-gray-400">生成二维码中...</div>
          <div v-if="isExpired" class="absolute inset-0 flex items-center justify-center">
            <MusicButton @click="refreshQr">刷新二维码</MusicButton>
          </div>
        </div>
        <MusicQrLoginState
          :status="qrStatus"
          :title="qrStatusText"
          :description="qrStatusDescription"
          className="mt-4"
        />
      </div>
    </MusicModal>

    <MusicModal
      :open="cookieVisible"
      :title="`${cookiePlatformLabel}：Cookie 导入登录`"
      :description="`登录 ${cookiePlatform === 'netease' ? 'music.163.com' : 'y.qq.com'} 后复制 Cookie 字符串并粘贴到下方。`"
      size="lg"
      @close="cookieVisible = false"
    >
      <MusicFormField label="Cookie 字符串" hint="仅保存在本地配置目录，用于平台接口请求。">
        <textarea
          v-model="cookieText"
          rows="8"
          placeholder="如：MUSIC_U=xxx; __csrf=xxx; ..."
          class="w-full rounded-xl border border-gray-300 bg-transparent px-4 py-3 text-theme-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
        />
      </MusicFormField>
      <template #footer>
        <div class="flex justify-end gap-3">
          <MusicButton variant="outline" :disabled="cookieSubmitting" @click="cookieVisible = false">取消</MusicButton>
          <MusicButton :loading="cookieSubmitting" @click="submitCookie">导入</MusicButton>
        </div>
      </template>
    </MusicModal>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, onUnmounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { QrCode, RefreshCcw, UserRound } from 'lucide-vue-next'
import QRCode from 'qrcode'
import MusicBadge from '@/components/music/MusicBadge.vue'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import MusicFormField from '@/components/music/MusicFormField.vue'
import MusicModal from '@/components/music/MusicModal.vue'
import MusicQrLoginState from '@/components/music/MusicQrLoginState.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import { authApi, type QQLoginType } from '@/api'
import { useAccountsStore } from '@/stores/accounts'

const InfoRow = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
  },
  setup(props) {
    return () =>
      h('div', { class: 'flex items-center justify-between gap-4 rounded-lg bg-gray-50 px-4 py-3 dark:bg-white/[0.03]' }, [
        h('span', { class: 'text-gray-500 dark:text-gray-400' }, props.label),
        h('span', { class: 'truncate font-medium text-gray-800 dark:text-white/90' }, props.value),
      ])
  },
})

const platforms = [
  { key: 'netease' as const, label: '网易云音乐' },
  { key: 'qq' as const, label: 'QQ 音乐' },
]

const message = useMusicToast()
const accountsStore = useAccountsStore()
const { accounts } = storeToRefs(accountsStore)

const refreshingMap = reactive<Record<string, boolean>>({
  netease: false,
  qq: false,
})

const getAccount = (key: 'netease' | 'qq') =>
  accounts.value.find((a) => a.platform === key)

/** 文字回退（仅在没拿到平台真实 VIP 图标时使用）。 */
const formatVip = (key: 'netease' | 'qq', vip: number | null | undefined) => {
  if (vip === null || vip === undefined) return '-'
  if (key === 'netease') {
    if (vip === 0) return '普通'
    if (vip === 110) return '黑胶 VIP'
    return `VIP ${vip}`
  }
  if (vip === 0) return '普通'
  return `VIP ${vip}`
}

const onIconError = (e: Event) => {
  // 图标加载失败时隐藏，避免破图
  const el = e.target as HTMLImageElement
  el.style.display = 'none'
}

const qrVisible = ref(false)
const qrTitle = ref('')
const qrImageDataUrl = ref<string | null>(null)
const qrStatusText = ref('生成二维码...')
const currentPlatform = ref<'netease' | 'qq' | null>(null)
const currentSubtype = ref<QQLoginType>('qq')

const hintText = computed(() => {
  if (currentPlatform.value === 'netease') return '请用网易云音乐 APP 扫描上方二维码'
  if (currentPlatform.value === 'qq' && currentSubtype.value === 'wx')
    return '请用微信扫一扫上方二维码（确认登录后会自动获取 QQ 音乐授权）'
  if (currentPlatform.value === 'qq' && currentSubtype.value === 'mobile')
    return '请用 QQ 音乐 APP 扫描上方二维码'
  return '请用 QQ APP 扫描上方二维码'
})

const qrStatus = computed(() => {
  if (qrStatusText.value.includes('成功')) return 'success'
  if (qrStatusText.value.includes('已扫码')) return 'scanned'
  if (qrStatusText.value.includes('过期') || qrStatusText.value.includes('失效')) return 'expired'
  if (qrStatusText.value.includes('失败')) return 'error'
  if (qrStatusText.value.includes('生成') || qrStatusText.value.includes('等待') || qrStatusText.value.includes('请扫码')) return 'pending'
  return 'unknown'
})

const qrStatusDescription = computed(() => {
  if (qrStatus.value === 'pending') return hintText.value
  if (qrStatus.value === 'scanned') return '请在手机端确认授权，确认后会自动关闭弹窗。'
  if (qrStatus.value === 'success') return '账号已保存，正在刷新账号状态。'
  if (qrStatus.value === 'expired') return '二维码不可继续使用，请刷新后重新扫码。'
  if (qrStatus.value === 'error') return '可以稍后重试，或改用 Cookie 导入。'
  return '请根据当前提示处理扫码登录。'
})

const isExpired = computed(
  () =>
    qrStatusText.value.includes('过期') ||
    qrStatusText.value.includes('失效') ||
    qrStatusText.value.includes('失败'),
)

const refreshQr = () => {
  if (!currentPlatform.value) return
  startLogin(currentPlatform.value, qrTitle.value.split(' ')[0], currentSubtype.value)
}

let pollTimer: number | null = null

const refresh = async () => {
  try {
    await accountsStore.refresh()
  } catch (e) {
    console.warn(e)
  }
}

const refreshProfile = async (platform: 'netease' | 'qq') => {
  refreshingMap[platform] = true
  try {
    const r = await accountsStore.refreshProfile(platform)
    message.success(`已刷新${r.nickname ? '：' + r.nickname : ''}`)
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '刷新失败'
    message.error(msg)
  } finally {
    refreshingMap[platform] = false
  }
}

const startLogin = async (
  platform: 'netease' | 'qq',
  label: string,
  type: QQLoginType = 'qq',
) => {
  stopPoll()
  const suffix = type === 'wx' ? '· 微信扫码' : type === 'mobile' ? '· QQ音乐APP扫码' : ''
  qrTitle.value = `${label} ${suffix}`
  qrImageDataUrl.value = null
  qrStatusText.value = '生成二维码...'
  qrVisible.value = true
  currentPlatform.value = platform
  currentSubtype.value = type

  try {
    const res = await authApi.createQR(platform, type)
    if (res.qr_image_b64) {
      qrImageDataUrl.value = `data:image/png;base64,${res.qr_image_b64}`
    } else if (res.qr_url) {
      qrImageDataUrl.value = await QRCode.toDataURL(res.qr_url, {
        width: 240,
        margin: 1,
        color: { dark: '#000000', light: '#ffffff' },
      })
    }
    qrStatusText.value = '请扫码'

    pollTimer = window.setInterval(async () => {
      try {
        const r = await authApi.pollQR(platform, res.ticket)
        if (r.status === 'pending') {
          qrStatusText.value = '等待扫码...'
        } else if (r.status === 'scanned') {
          qrStatusText.value = '已扫码，请在手机端确认'
        } else if (r.status === 'success') {
          qrStatusText.value = `登录成功${r.nickname ? '：' + r.nickname : ''}`
          message.success(`${label} 登录成功${r.nickname ? '（' + r.nickname + '）' : ''}`)
          stopPoll()
          setTimeout(() => (qrVisible.value = false), 600)
          await refresh()
        } else if (r.status === 'expired') {
          qrStatusText.value = '二维码已过期，请关闭重试'
          stopPoll()
        } else if (r.status === 'unknown') {
          qrStatusText.value = `未知状态：${r.message ?? ''}`
        }
      } catch (e: any) {
        if (e?.response?.status === 404) {
          qrStatusText.value = '会话已失效，请关闭重试'
          stopPoll()
        } else {
          console.warn(e)
        }
      }
    }, 2500)
  } catch (e) {
    qrStatusText.value = '生成失败，请稍后重试'
    console.error(e)
  }
}

const logout = async (platform: 'netease' | 'qq') => {
  await authApi.logout(platform)
  message.success('已登出')
  await refresh()
}

const stopPoll = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const closeQrModal = () => {
  qrVisible.value = false
  stopPoll()
}

const cookieVisible = ref(false)
const cookieText = ref('')
const cookiePlatform = ref<'netease' | 'qq'>('netease')
const cookiePlatformLabel = ref('')
const cookieSubmitting = ref(false)

const openCookieImport = (platform: 'netease' | 'qq', label: string) => {
  cookiePlatform.value = platform
  cookiePlatformLabel.value = label
  cookieText.value = ''
  cookieVisible.value = true
}

const submitCookie = async () => {
  const txt = cookieText.value.trim()
  if (!txt) {
    message.warning('请粘贴 Cookie 字符串')
    return
  }
  cookieSubmitting.value = true
  try {
    const r: any = await authApi.importCookie(cookiePlatform.value, txt)
    message.success(
      `导入成功${r.nickname ? '：' + r.nickname : ''}（${cookiePlatformLabel.value}）`,
    )
    cookieVisible.value = false
    await refresh()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '导入失败'
    message.error(msg)
  } finally {
    cookieSubmitting.value = false
  }
}

onMounted(refresh)
onUnmounted(stopPoll)
</script>
