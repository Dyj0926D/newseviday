<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import PageIntro from '../components/PageIntro.vue';

const route = useRoute();
const title = computed(() => String(route.meta.title ?? 'NewsEviday'));
const description = computed(() => String(route.meta.description ?? '该页面将在后续阶段实现。'));
</script>

<template>
  <main id="main-content">
    <PageIntro :title="title" :description="description" />
    <section class="page-container placeholder-shell">
      <div class="inline-notice">
        <strong>工程骨架状态</strong>
        <p>路由、页面容器和响应式基础已建立，业务组件将在静态产品阶段补齐。</p>
      </div>
      <RouterLink class="text-link" to="/">返回情报流</RouterLink>
    </section>
  </main>
</template>
