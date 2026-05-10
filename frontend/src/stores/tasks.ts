import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { tasksApi, type DownloadTaskItem } from '@/api'

/**
 * 任务全局 store。
 *
 * - 启动时拉一次列表
 * - 连 WS `/api/tasks/ws` 接受 task.created / task.updated 事件
 * - 自动重连（指数退避，最多 30s）
 */
export const useTasksStore = defineStore('tasks', () => {
  const tasks = ref<Map<number, DownloadTaskItem>>(new Map())
  const connected = ref(false)
  const paused = ref(false)
  const concurrency = ref(0)
  const queueSize = ref(0)
  let socket: WebSocket | null = null
  let reconnectDelay = 1000
  let reconnectTimer: number | null = null

  const allTasks = computed<DownloadTaskItem[]>(() =>
    Array.from(tasks.value.values()).sort((a, b) => b.id - a.id),
  )

  const runningCount = computed(
    () =>
      Array.from(tasks.value.values()).filter(
        (t) => t.status === 'running' || t.status === 'queued',
      ).length,
  )

  const summary = computed(() => {
    const out: Record<string, number> = {
      queued: 0,
      running: 0,
      success: 0,
      failed: 0,
      skipped_dup: 0,
      cancelled: 0,
    }
    for (const t of tasks.value.values()) {
      out[t.status] = (out[t.status] || 0) + 1
    }
    return out
  })

  const upsert = (t: DownloadTaskItem) => {
    tasks.value.set(t.id, t)
  }

  const removeTask = (id: number) => {
    tasks.value.delete(id)
  }

  const clearTaskByStatus = async (status: string) => {
    await tasksApi.clear(status)
    for (const [id, t] of tasks.value) {
      if (t.status === status) tasks.value.delete(id)
    }
  }

  const refresh = async () => {
    try {
      const [r, control] = await Promise.all([
        tasksApi.list({ limit: 300 }),
        tasksApi.control().catch(() => null),
      ])
      const next = new Map<number, DownloadTaskItem>()
      for (const t of r.items) next.set(t.id, t)
      tasks.value = next
      if (control) {
        paused.value = control.paused
        concurrency.value = control.concurrency
        queueSize.value = control.queue_size
      }
    } catch (e) {
      console.warn('refresh tasks failed', e)
    }
  }

  const cancelTask = async (id: number) => {
    try {
      await tasksApi.cancel(id)
      const t = tasks.value.get(id)
      if (t) {
        upsert({ ...t, status: 'cancelled' })
      }
    } catch (e) {
      throw e
    }
  }

  const cancelWaiting = async () => {
    await tasksApi.cancelWaiting()
    await refresh()
  }

  const cancelSelected = async (ids: number[]) => {
    await tasksApi.cancelSelected(ids)
    await refresh()
  }

  const retrySelected = async (ids: number[]) => {
    await tasksApi.retrySelected(ids)
    await refresh()
  }

  const deleteSelected = async (ids: number[], deleteLocalFiles = false) => {
    await tasksApi.deleteSelected(ids, deleteLocalFiles)
    await refresh()
  }

  const pauseQueue = async () => {
    const control = await tasksApi.pause()
    paused.value = control.paused
    concurrency.value = control.concurrency
    queueSize.value = control.queue_size
  }

  const resumeQueue = async () => {
    const control = await tasksApi.resume()
    paused.value = control.paused
    concurrency.value = control.concurrency
    queueSize.value = control.queue_size
  }

  const connect = () => {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return
    }
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    // dev 模式 vite 代理 /ws → backend /api/tasks/ws，但实际后端路径是 /api/tasks/ws
    const url = `${proto}://${host}/api/tasks/ws`
    socket = new WebSocket(url)

    socket.onopen = () => {
      connected.value = true
      reconnectDelay = 1000
    }
    socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.event === 'task.created' || msg.event === 'task.updated') {
          upsert(msg.task)
        }
      } catch (e) {
        console.warn('ws parse error', e, ev.data)
      }
    }
    socket.onclose = () => {
      connected.value = false
      socket = null
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = window.setTimeout(connect, reconnectDelay)
      reconnectDelay = Math.min(reconnectDelay * 2, 30000)
    }
    socket.onerror = (e) => {
      console.warn('ws error', e)
    }
  }

  const init = async () => {
    await refresh()
    connect()
  }

  return {
    tasks,
    allTasks,
    runningCount,
    summary,
    connected,
    paused,
    concurrency,
    queueSize,
    init,
    refresh,
    upsert,
    removeTask,
    cancelTask,
    cancelWaiting,
    cancelSelected,
    retrySelected,
    deleteSelected,
    pauseQueue,
    resumeQueue,
    clearTaskByStatus,
  }
})
