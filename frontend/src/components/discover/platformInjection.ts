import type { InjectionKey, Ref } from 'vue'

export type DiscoverPlatform = 'netease' | 'qq'

/**
 * 发现页全局选中的平台。由 Discover.vue 在顶部 provide，
 * 各子面板（推荐 / 热门 / 我的歌单）通过 inject 共享这个状态，
 * 不再维护各自独立的平台切换。
 */
export const DISCOVER_PLATFORM_KEY: InjectionKey<Ref<DiscoverPlatform>> = Symbol('discover-platform')
