import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import NewView from '../views/NewView.vue'
import DetailView from '../views/DetailView.vue'

const routes = [
  { path: '/', component: HomeView },
  { path: '/new', component: NewView },
  { path: '/summary/:id', component: DetailView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
