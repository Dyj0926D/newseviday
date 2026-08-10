<script setup lang="ts">
import {
  PhArrowLeft,
  PhArrowUpRight,
  PhCheckCircle,
  PhSparkle,
  PhWarningCircle,
} from '@phosphor-icons/vue';
import type { ContentSnapshot } from '@newseviday/contracts';
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import Breadcrumbs from '../components/Breadcrumbs.vue';
import {
  displaySummary,
  displayTitle,
  displayWhy,
  formatDateTime,
  languageLabel,
  resolveSource,
  sourceTypeLabel,
  topicLabels,
} from '../lib/intelligence';
import { useContentStore } from '../stores/content';

const route = useRoute();
const content = useContentStore();
const articleId = computed(() => String(route.params.id ?? ''));
const archivedSnapshot = ref<ContentSnapshot | null>(null);
const archiveLoading = ref(false);
const activeSnapshot = computed(() => {
  if (content.snapshot?.articles.some((item) => item.id === articleId.value)) {
    return content.snapshot;
  }
  return archivedSnapshot.value;
});
const isArchived = computed(() => Boolean(archivedSnapshot.value && activeSnapshot.value));
const article = computed(
  () => activeSnapshot.value?.articles.find((item) => item.id === articleId.value) ?? null,
);
const source = computed(() =>
  article.value ? resolveSource(article.value, activeSnapshot.value?.sources ?? []) : undefined,
);
const evidence = computed(() =>
  (activeSnapshot.value?.evidence ?? []).filter((item) =>
    article.value?.evidenceIds.includes(item.id),
  ),
);
const related = computed(() => {
  if (!article.value) return [];
  const topicIds = new Set(Object.keys(article.value.topicScores));
  return (activeSnapshot.value?.articles ?? [])
    .filter(
      (item) =>
        item.id !== article.value?.id &&
        Object.keys(item.topicScores).some((topicId) => topicIds.has(topicId)),
    )
    .slice(0, 3);
});

watch(
  [articleId, () => content.state],
  async () => {
    archivedSnapshot.value = null;
    if (content.state !== 'ready' || article.value) return;
    archiveLoading.value = true;
    archivedSnapshot.value = await content.loadArchivedSnapshotForArticle(articleId.value);
    archiveLoading.value = false;
  },
  { immediate: true },
);
</script>

<template>
  <main id="main-content">
    <div
      v-if="content.state === 'loading' || archiveLoading"
      class="page-container inner-loading"
      role="status"
    >
      <span></span><span></span><span></span>
    </div>

    <section v-else-if="!article" class="page-container not-found" data-page-intro>
      <p class="not-found__code">404</p>
      <h1>没有找到这条情报</h1>
      <p>当前快照和公开历史索引中都没有找到这条内容。</p>
      <RouterLink class="button button--primary" to="/">
        <PhArrowLeft :size="17" aria-hidden="true" />
        返回最新情报
      </RouterLink>
    </section>

    <template v-else>
      <header class="article-hero" data-page-intro>
        <div class="page-container article-hero__inner">
          <Breadcrumbs current="情报详情" />
          <div class="intel-meta article-hero__meta">
            <span class="source-mark">{{ source?.name.slice(0, 1) ?? 'N' }}</span>
            <strong>{{ source?.name ?? article.sourceId }}</strong>
            <span class="source-type-badge">{{
              sourceTypeLabel(source?.sourceType ?? article.sourceType)
            }}</span>
            <span>{{ source?.region ?? '区域未知' }}</span>
            <span>{{ languageLabel(article.language) }}</span>
            <span>{{ formatDateTime(article.publishedAt) }}</span>
          </div>
          <h1>{{ displayTitle(article) }}</h1>
          <p class="article-original-title">原始标题：{{ article.facts.title }}</p>
          <p class="article-deck">{{ displaySummary(article) }}</p>
          <p v-if="isArchived" class="article-archive-notice">
            这是历史快照内容，整理时间为 {{ formatDateTime(activeSnapshot?.generatedAt ?? null) }}。
          </p>
          <div class="article-hero__actions">
            <a
              class="button button--primary"
              :href="article.canonicalUrl"
              target="_blank"
              rel="noreferrer"
            >
              查看原始来源
              <PhArrowUpRight :size="17" aria-hidden="true" />
            </a>
            <a class="button button--secondary" href="#article-ask">追问这篇文章</a>
          </div>
          <div class="ai-disclosure">
            <PhSparkle v-if="article.ai" :size="17" weight="fill" aria-hidden="true" />
            <PhCheckCircle v-else :size="17" aria-hidden="true" />
            <span>
              {{
                article.ai?.provider === 'deepseek'
                  ? 'AI 结构化整理，请以原始来源为准'
                  : article.ai?.provider === 'editorial'
                    ? '编辑整理，请以原始来源为准'
                    : '来源标题与摘要，未经改写'
              }}
            </span>
            <small v-if="article.ai">
              {{ article.ai.model === 'demo-fixture' ? '演示整理' : article.ai.model }} ·
              {{ formatDateTime(article.ai.generatedAt) }}
            </small>
          </div>
        </div>
      </header>

      <div class="page-container article-layout">
        <article class="article-body">
          <section v-if="displayWhy(article) && evidence.length" class="core-judgment">
            <p class="section-kicker">CORE JUDGMENT</p>
            <h2>为什么重要</h2>
            <p>{{ displayWhy(article) }}</p>
          </section>

          <section class="article-section">
            <h2>发生了什么</h2>
            <p>{{ displaySummary(article) }}</p>
          </section>

          <section v-if="article.ai?.keyPoints.length" class="article-section">
            <h2>关键事实</h2>
            <ol class="fact-list">
              <li v-for="(point, index) in article.ai.keyPoints" :key="point">
                <span>{{ String(index + 1).padStart(2, '0') }}</span>
                <p>{{ point }} <a v-if="evidence[0]" :href="`#${evidence[0].id}`">[1]</a></p>
              </li>
            </ol>
          </section>

          <section class="article-section">
            <h2>相关主题</h2>
            <p>
              这条信号与
              {{ topicLabels(article, activeSnapshot?.topics ?? []).join('、') }}
              相关。你可以结合原始来源和关联证据判断它是否值得继续跟进。
            </p>
          </section>

          <section id="article-ask" class="article-ask-panel">
            <div>
              <p class="section-kicker">ARTICLE Q&A</p>
              <h2>继续追问当前文章</h2>
              <p>问答只使用当前文章和关联证据；证据不足时会明确说明。</p>
            </div>
            <div class="suggested-question-list">
              <span>这项变化会影响哪些数据产品？</span>
              <span>原始来源提供了哪些直接证据？</span>
              <span>这条信号还有哪些不确定性？</span>
            </div>
            <RouterLink
              class="button button--secondary"
              :to="{ path: '/ask', query: { article: article.id } }"
            >
              带着文章去提问
            </RouterLink>
          </section>

          <section v-if="related.length" class="related-section">
            <div class="section-heading">
              <div>
                <p class="section-kicker">RELATED SIGNALS</p>
                <h2>相关情报</h2>
              </div>
            </div>
            <div class="related-list">
              <RouterLink v-for="item in related" :key="item.id" :to="`/article/${item.id}`">
                <span>{{
                  resolveSource(item, activeSnapshot?.sources ?? [])?.name ?? item.sourceId
                }}</span>
                <strong>{{ displayTitle(item) }}</strong>
                <PhArrowUpRight :size="17" aria-hidden="true" />
              </RouterLink>
            </div>
          </section>
        </article>

        <aside class="evidence-panel" aria-labelledby="evidence-title">
          <div class="evidence-panel__heading">
            <div>
              <p>EVIDENCE</p>
              <h2 id="evidence-title">原始证据</h2>
            </div>
            <span>{{ evidence.length }} 条</span>
          </div>
          <div v-if="evidence.length" class="evidence-list">
            <article v-for="(item, index) in evidence" :id="item.id" :key="item.id">
              <span>[{{ index + 1 }}]</span>
              <strong>{{ source?.name ?? item.sourceId }}</strong>
              <p>{{ item.excerpt }}</p>
              <a :href="item.url" target="_blank" rel="noreferrer">
                打开来源
                <PhArrowUpRight :size="15" aria-hidden="true" />
              </a>
            </article>
          </div>
          <div v-else class="evidence-empty">
            <PhWarningCircle :size="20" aria-hidden="true" />
            <p>当前证据不足，不展示核心判断。</p>
          </div>
          <div class="evidence-rule">
            <PhCheckCircle :size="18" weight="fill" aria-hidden="true" />
            <p>页面只展示短证据片段与原始链接，不转载完整正文。</p>
          </div>
        </aside>
      </div>
    </template>
  </main>
</template>
