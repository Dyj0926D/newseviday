import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

import ArticleView from './views/ArticleView.vue';
import AskView from './views/AskView.vue';
import BriefView from './views/BriefView.vue';
import EvalView from './views/EvalView.vue';
import HomeView from './views/HomeView.vue';
import NotFoundView from './views/NotFoundView.vue';
import ProductView from './views/ProductView.vue';
import ProfileView from './views/ProfileView.vue';
import StatusView from './views/StatusView.vue';

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { title: '最新情报' },
  },
  {
    path: '/article/:id',
    name: 'article',
    component: ArticleView,
    meta: { title: '情报详情' },
  },
  {
    path: '/ask',
    name: 'ask',
    component: AskView,
    meta: { title: '证据问答' },
  },
  {
    path: '/brief',
    name: 'brief',
    component: BriefView,
    meta: { title: '趋势简报' },
  },
  {
    path: '/profile',
    name: 'profile',
    component: ProfileView,
    meta: { title: '关注偏好' },
  },
  {
    path: '/eval',
    name: 'eval',
    component: EvalView,
    meta: { title: '质量评测' },
  },
  {
    path: '/status',
    name: 'status',
    component: StatusView,
    meta: { title: '更新状态' },
  },
  {
    path: '/product',
    name: 'product',
    component: ProductView,
    meta: { title: '产品介绍' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView,
    meta: { title: '页面未找到' },
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition;
    if (to.hash) return { el: to.hash, top: 72, behavior: 'smooth' };
    return { top: 0 };
  },
});

router.afterEach((to) => {
  const pageTitle = typeof to.meta.title === 'string' ? to.meta.title : 'NewsEviday';
  document.title = `${pageTitle} | NewsEviday`;
});
