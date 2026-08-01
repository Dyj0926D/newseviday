<script setup lang="ts">
import { PhList, PhMagnifyingGlass, PhUserCircle } from '@phosphor-icons/vue';

import { useRuntimeStore } from '../stores/runtime';

const runtime = useRuntimeStore();
</script>

<template>
  <header class="app-header">
    <div class="page-container app-header__inner">
      <RouterLink class="brand" to="/" aria-label="NewsEviday 首页">NewsEviday</RouterLink>

      <nav class="desktop-nav" aria-label="主导航">
        <RouterLink to="/">情报流</RouterLink>
        <RouterLink to="/brief">趋势简报</RouterLink>
        <RouterLink to="/ask">情报问答</RouterLink>
        <RouterLink to="/product">产品介绍</RouterLink>
      </nav>

      <div class="app-header__actions">
        <span class="mode-badge">{{ runtime.statusLabel }}</span>
        <RouterLink class="icon-link" to="/?focus=search" aria-label="搜索情报">
          <PhMagnifyingGlass :size="20" weight="regular" aria-hidden="true" />
        </RouterLink>
        <RouterLink class="icon-link desktop-profile" to="/profile" aria-label="我的画像">
          <PhUserCircle :size="20" weight="regular" aria-hidden="true" />
        </RouterLink>

        <details class="mobile-nav">
          <summary aria-label="打开导航菜单">
            <PhList :size="22" weight="regular" aria-hidden="true" />
          </summary>
          <nav aria-label="移动端导航">
            <RouterLink to="/">情报流</RouterLink>
            <RouterLink to="/brief">趋势简报</RouterLink>
            <RouterLink to="/ask">情报问答</RouterLink>
            <RouterLink to="/product">产品介绍</RouterLink>
            <RouterLink to="/profile">我的画像</RouterLink>
            <RouterLink to="/eval">Eval</RouterLink>
            <RouterLink to="/status">数据状态</RouterLink>
          </nav>
        </details>
      </div>
    </div>
  </header>
</template>
