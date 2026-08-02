<script setup lang="ts">
defineProps<{
  eyebrow?: string;
  title: string;
  description: string;
}>();
</script>

<template>
  <section class="inner-hero" data-page-intro>
    <div class="page-container inner-hero__inner">
      <p v-if="eyebrow" class="inner-hero__eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
      <div v-if="$slots.actions" class="inner-hero__actions">
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>
