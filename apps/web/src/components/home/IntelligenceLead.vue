<script setup lang="ts">
import type { Article, SnapshotTopic, Source } from '@newseviday/contracts';
import { PhArrowUpRight, PhBookmarkSimple, PhCheckCircle, PhTranslate } from '@phosphor-icons/vue';

import {
  displaySummary,
  displayTitle,
  displayWhy,
  formatDateTime,
  languageLabel,
  topicLabels,
} from '../../lib/intelligence';

defineProps<{
  article: Article;
  source?: Source;
  topics: SnapshotTopic[];
  saved: boolean;
}>();

const emit = defineEmits<{ save: [articleId: string] }>();
</script>

<template>
  <article class="intelligence-lead">
    <div class="intelligence-lead__accent" aria-hidden="true">
      <span>TOP SIGNAL</span>
      <strong>01</strong>
    </div>
    <div class="intelligence-lead__content">
      <div class="intel-meta">
        <span class="source-mark">{{ source?.name.slice(0, 1) ?? 'N' }}</span>
        <strong>{{ source?.name ?? article.sourceId }}</strong>
        <span>{{ source?.region ?? '区域未知' }}</span>
        <span v-if="article.language !== 'zh-CN'" class="translation-badge">
          <PhTranslate :size="14" aria-hidden="true" />
          {{ languageLabel(article.language) }}已整理
        </span>
        <span>{{ formatDateTime(article.publishedAt) }}</span>
      </div>

      <p class="intel-kicker">今日重点</p>
      <h3><RouterLink :to="`/article/${article.id}`">{{ displayTitle(article) }}</RouterLink></h3>
      <p class="intel-summary">{{ displaySummary(article) }}</p>

      <div v-if="displayWhy(article)" class="why-panel">
        <PhCheckCircle :size="18" weight="fill" aria-hidden="true" />
        <div>
          <span>为什么值得看</span>
          <p>{{ displayWhy(article) }}</p>
        </div>
      </div>

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
            <PhBookmarkSimple :size="19" :weight="saved ? 'fill' : 'regular'" aria-hidden="true" />
          </button>
          <a :href="article.canonicalUrl" target="_blank" rel="noreferrer">
            查看来源
            <PhArrowUpRight :size="16" aria-hidden="true" />
          </a>
        </div>
      </div>
    </div>
  </article>
</template>
