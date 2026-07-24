import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/global.css'
import './styles/main.css'

performance.mark('shike-boot-start')

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

performance.mark('shike-boot-end')
try {
  performance.measure('shike-boot', 'shike-boot-start', 'shike-boot-end')
} catch {
  /* ignore */
}
