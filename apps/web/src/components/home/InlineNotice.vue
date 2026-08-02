<script setup lang="ts">
import { PhInfo } from '@phosphor-icons/vue';

defineProps<{
  title: string;
  description: string;
}>();
</script>

<template>
  <div class="feed-notice" role="note">
    <PhInfo :size="18" weight="fill" aria-hidden="true" />
    <div>
      <strong>{{ title }}</strong>
      <p>{{ description }}</p>
    </div>
  </div>
</template>
