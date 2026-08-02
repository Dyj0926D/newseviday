<script setup lang="ts">
import { onMounted } from 'vue';

import AppHeader from './components/AppHeader.vue';
import { useContentStore } from './stores/content';
import { useProfileStore } from './stores/profile';
import { useRuntimeStore } from './stores/runtime';

const runtime = useRuntimeStore();
const content = useContentStore();
const profile = useProfileStore();

onMounted(() => {
  profile.hydrate();
  void content.refresh();
  void runtime.refresh();
});
</script>

<template>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <AppHeader />
  <RouterView />
  <footer class="site-footer">
    <div class="page-container site-footer__inner">
      <p>NewsEviday，有证据的 AI 产品与技术情报。</p>
      <nav aria-label="透明度与项目链接">
        <RouterLink to="/product">产品介绍</RouterLink>
        <RouterLink to="/eval">Eval</RouterLink>
        <RouterLink to="/status">数据状态</RouterLink>
        <a href="https://github.com/Dyj0926D/newseviday" target="_blank" rel="noreferrer">GitHub</a>
      </nav>
    </div>
  </footer>
</template>
