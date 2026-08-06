<script setup lang="ts">
import type { Article, SnapshotTopic, Source } from '@newseviday/contracts';
import { PhArrowUpRight, PhBookmarkSimple, PhTranslate } from '@phosphor-icons/vue';

import {
  displaySummary,
  displayTitle,
  displayWhy,
  formatDateTime,
  translationStatus,
  topicLabels,
} from '../../lib/intelligence';

defineProps<{
  article: Article;
  source?: Source;
  topics: SnapshotTopic[];
  saved: boolean;
  recommendationReason?: string;
}>();

const emit = defineEmits<{ save: [articleId: string] }>();
</script>

<template>
  <article class="intelligence-row">
    <div class="intel-meta">
      <span class="source-mark">{{ source?.name.slice(0, 1) ?? 'N' }}</span>
      <strong>{{ source?.name ?? article.sourceId }}</strong>
      <span>{{ source?.region ?? '区域未知' }}</span>
      <span v-if="article.language !== 'zh-CN'" class="translation-badge">
        <PhTranslate :size="14" aria-hidden="true" />
        {{ translationStatus(article) }}
      </span>
      <span>{{ formatDateTime(article.publishedAt) }}</span>
    </div>

    <h3>
      <RouterLink :to="`/article/${article.id}`">{{ displayTitle(article) }}</RouterLink>
    </h3>
    <p class="intel-summary">{{ displaySummary(article) }}</p>
    <p v-if="displayWhy(article)" class="intel-why">
      <strong>关注原因</strong>
      {{ displayWhy(article) }}
    </p>
    <p v-if="recommendationReason" class="recommendation-reason">{{ recommendationReason }}</p>

    <div class="intel-footer">
      <div class="intel-tags" aria-label="主题标签">
        <span v-for="label in topicLabels(article, topics)" :key="label">{{ label }}</span>
      </div>
      <div class="intel-actions">
        <button
          class="icon-button"
          type="button"
          :aria-label="saved ? '取消收藏' : '收藏情报'"
          :aria-pressed="saved"
          @click="emit('save', article.id)"
        >
          <PhBookmarkSimple :size="18" :weight="saved ? 'fill' : 'regular'" aria-hidden="true" />
        </button>
        <a :href="article.canonicalUrl" target="_blank" rel="noreferrer" aria-label="查看原始来源">
          <PhArrowUpRight :size="18" aria-hidden="true" />
        </a>
      </div>
    </div>
  </article>
</template>
