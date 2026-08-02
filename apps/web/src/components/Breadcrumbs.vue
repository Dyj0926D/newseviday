<script setup lang="ts">
defineProps<{
  current: string;
  parentLabel?: string;
  parentTo?: string;
}>();
</script>

<template>
  <nav class="breadcrumbs" aria-label="面包屑">
    <RouterLink :to="parentTo ?? '/'">{{ parentLabel ?? '最新情报' }}</RouterLink>
    <span aria-hidden="true">/</span>
    <span aria-current="page">{{ current }}</span>
  </nav>
</template>
