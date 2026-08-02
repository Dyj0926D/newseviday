<script setup lang="ts">
defineProps<{
  eyebrow?: string;
  title: string;
  description: string;
}>();
</script>

<template>
  <section class="page-intro" data-page-intro>
    <div class="page-container page-intro__inner">
      <p v-if="eyebrow" class="page-intro__eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p class="page-intro__description">{{ description }}</p>
      <div v-if="$slots.actions" class="page-intro__actions">
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>
