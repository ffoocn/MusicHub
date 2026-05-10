import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    {
      path: '/',
      redirect: '/discover',
    },
    {
      path: '/discover',
      name: 'discover',
      component: () => import('@/views/Discover.vue'),
      meta: { title: '发现' },
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('@/views/Library.vue'),
      meta: { title: '本地库' },
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: () => import('@/views/Tasks.vue'),
      meta: { title: '任务' },
    },
    {
      path: '/playlist/:platform/:id',
      name: 'playlist-detail',
      component: () => import('@/views/PlaylistDetail.vue'),
      meta: { title: '歌单' },
    },
    {
      path: '/album/:platform/:id',
      name: 'album-detail',
      component: () => import('@/views/AlbumDetail.vue'),
      meta: { title: '专辑' },
    },
    {
      path: '/stats',
      redirect: '/library',
    },
    {
      path: '/subscriptions',
      name: 'subscriptions',
      component: () => import('@/views/Subscriptions.vue'),
      meta: { title: '订阅与自动化' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/Settings.vue'),
      meta: { title: '设置' },
    },
  ],
})

export default router
