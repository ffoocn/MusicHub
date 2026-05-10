import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useTasksStore } from './stores/tasks'
import './assets/main.css'
import './style.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// 全局任务实时连接（WebSocket）
const tasksStore = useTasksStore(pinia)
tasksStore.init()

app.mount('#app')
