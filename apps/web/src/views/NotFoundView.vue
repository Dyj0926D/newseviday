<script setup lang="ts">
import { PhArrowLeft } from '@phosphor-icons/vue';
</script>

<template>
  <main id="main-content">
    <section class="page-container not-found" data-page-intro>
      <p class="not-found__code">404</p>
      <h1>页面没有找到</h1>
      <p>地址可能已变化。你可以回到情报流，继续查看当前公开快照。</p>
      <RouterLink class="button button--primary" to="/">
        <PhArrowLeft :size="17" aria-hidden="true" />
        返回情报流
      </RouterLink>
    </section>
  </main>
</template>
