import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '工作台' },
  },
  {
    path: '/data-management',
    name: 'DataManagement',
    component: () => import('../views/DataManagement.vue'),
  },
  {
    path: '/chat-analysis',
    name: 'ChatAnalysis',
    component: () => import('../views/ChatAnalysis.vue'),
    meta: { title: '对话分析' },
  },
  {
    path: '/llm-models',
    name: 'LLMModels',
    component: () => import('../views/LLMModels.vue'),
    meta: { title: '大语言模型管理' },
  },
  {
    path: '/trained-models',
    name: 'TrainedModels',
    component: () => import('../views/TrainedModels.vue'),
    meta: { title: '训练模型管理' },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智能数据分析平台`;
  }
  next();
});

export default router;
