import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

import HomeView from './views/HomeView.vue';
import PlaceholderView from './views/PlaceholderView.vue';

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { title: '情报流' },
  },
  {
    path: '/article/:id',
    name: 'article',
    component: PlaceholderView,
    meta: {
      title: '文章详情',
      description: '跨语言摘要、核心判断和证据面板将在静态产品阶段实现。',
    },
  },
  {
    path: '/ask',
    name: 'ask',
    component: PlaceholderView,
    meta: {
      title: '情报问答',
      description: '基于已收录内容回答问题，并展示引用和检索过程。',
    },
  },
  {
    path: '/brief',
    name: 'brief',
    component: PlaceholderView,
    meta: {
      title: '趋势简报',
      description: '汇总最近 7 天的重要变化、区域差异和下一步观察清单。',
    },
  },
  {
    path: '/profile',
    name: 'profile',
    component: PlaceholderView,
    meta: {
      title: '我的画像',
      description: '画像保持可选，并在浏览器本地保存。',
    },
  },
  {
    path: '/eval',
    name: 'eval',
    component: PlaceholderView,
    meta: {
      title: 'Eval',
      description: '展示实际运行的检索指标、版本和失败案例。',
    },
  },
  {
    path: '/status',
    name: 'status',
    component: PlaceholderView,
    meta: {
      title: '数据状态',
      description: '公开最后更新时间、来源状态和 AI 能力状态。',
    },
  },
  {
    path: '/product',
    name: 'product',
    component: PlaceholderView,
    meta: {
      title: '产品介绍',
      description: '从产品思路、技术架构、RAG 和 Eval 解释 NewsEviday。',
    },
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 };
  },
});

router.afterEach((to) => {
  const pageTitle = typeof to.meta.title === 'string' ? to.meta.title : 'NewsEviday';
  document.title = `${pageTitle} | NewsEviday`;
});
