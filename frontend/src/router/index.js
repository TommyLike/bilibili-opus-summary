import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import DetailView from '../views/DetailView.vue'

const routes = [
  { path: '/', component: HomeView },
  { path: '/summary/:id', component: DetailView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
