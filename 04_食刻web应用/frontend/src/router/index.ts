import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ResultView from '../views/ResultView.vue'
import AboutView from '../views/AboutView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/result/:sessionId', name: 'result', component: ResultView, props: true },
    { path: '/about', name: 'about', component: AboutView },
  ],
})

export default router
