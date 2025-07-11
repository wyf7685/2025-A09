import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '工作台' }
  },
  {
    path: '/data-management',
    name: 'DataManagement',
    component: () => import('../views/DataManagement.vue')
  },
  {
    path: '/chat-analysis',
    name: 'ChatAnalysis',
    component: () => import('../views/ChatAnalysis.vue'),
    meta: { title: '对话分析' }
  },
  {
    path: '/models',
    name: 'Models',
    component: () => import('../views/Models.vue'),
    meta: { title: '模型管理' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智能数据分析平台`
  }
  next()
})

export default router
