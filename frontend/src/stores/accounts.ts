import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi, type AccountStatus } from '@/api'

/**
 * 平台账号全局 store。
 *
 * - `refresh()`：拉取 `/api/auth/status`，刷新本地缓存
 * - 多个组件（AccountManager / AppHeader 等）共享同一份账号状态
 *   登录/登出后只需要调一次 `refresh()`，整个 UI 同步更新
 */
export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref<AccountStatus[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  const validAccounts = computed(() => accounts.value.filter((a) => a.is_valid))
  const loggedIn = computed(() => validAccounts.value.length > 0)

  /** 调度后台 profile 刷新；同 platform 同会话只会触发一次，避免无限循环。 */
  const _autoRefreshing = new Set<string>()
  const _autoRefreshIfMissing = async () => {
    for (const a of accounts.value) {
      if (!a.is_valid) continue
      if (a.nickname && a.avatar_url) continue
      if (_autoRefreshing.has(a.platform)) continue
      _autoRefreshing.add(a.platform)
      authApi
        .refresh(a.platform as 'netease' | 'qq')
        .then((updated) => {
          const idx = accounts.value.findIndex((x) => x.platform === a.platform)
          if (idx >= 0) {
            accounts.value[idx] = {
              ...accounts.value[idx],
              user_id: updated.user_id ?? accounts.value[idx].user_id,
              nickname: updated.nickname ?? accounts.value[idx].nickname,
              vip_type: updated.vip_type ?? accounts.value[idx].vip_type,
              vip_icons: updated.vip_icons ?? accounts.value[idx].vip_icons ?? [],
              avatar_url: updated.avatar_url ?? accounts.value[idx].avatar_url,
            }
          }
        })
        .catch((err) => {
          console.warn(`[accounts] auto-refresh ${a.platform} failed`, err)
        })
    }
  }

  const refresh = async () => {
    loading.value = true
    try {
      accounts.value = await authApi.status()
      _autoRefreshIfMissing()
    } catch (e) {
      console.warn('[accounts] refresh failed', e)
    } finally {
      loading.value = false
      loaded.value = true
    }
  }

  /** 立即返回缓存（如果有），并触发后台刷新。 */
  const ensureLoaded = async () => {
    if (loaded.value) return accounts.value
    await refresh()
    return accounts.value
  }

  /** 强制重新拉一次某平台的 profile（昵称/头像/VIP）。 */
  const refreshProfile = async (platform: 'netease' | 'qq') => {
    try {
      const updated = await authApi.refresh(platform)
      const idx = accounts.value.findIndex((x) => x.platform === platform)
      if (idx >= 0) {
        accounts.value[idx] = {
          ...accounts.value[idx],
          user_id: updated.user_id ?? accounts.value[idx].user_id,
          nickname: updated.nickname ?? accounts.value[idx].nickname,
          vip_type: updated.vip_type ?? accounts.value[idx].vip_type,
          vip_icons: updated.vip_icons ?? accounts.value[idx].vip_icons ?? [],
          avatar_url: updated.avatar_url ?? accounts.value[idx].avatar_url,
        }
      }
      return updated
    } catch (e) {
      console.warn(`[accounts] refreshProfile ${platform} failed`, e)
      throw e
    }
  }

  const getAccount = (platform: 'netease' | 'qq') =>
    accounts.value.find((a) => a.platform === platform)

  return {
    accounts,
    loaded,
    loading,
    validAccounts,
    loggedIn,
    refresh,
    ensureLoaded,
    refreshProfile,
    getAccount,
  }
})
