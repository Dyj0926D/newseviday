<script setup lang="ts">
import {
  PhArrowLeft,
  PhArrowUpRight,
  PhCheckCircle,
  PhSparkle,
  PhWarningCircle,
} from '@phosphor-icons/vue';
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import Breadcrumbs from '../components/Breadcrumbs.vue';
import {
  displaySummary,
  displayTitle,
  displayWhy,
  formatDateTime,
  languageLabel,
  resolveSource,
  topicLabels,
} from '../lib/intelligence';
import { useContentStore } from '../stores/content';

const route = useRoute();
const content = useContentStore();
const articleId = computed(() => String(route.params.id ?? ''));
const article = computed(
  () => content.snapshot?.articles.find((item) => item.id === articleId.value) ?? null,
);
const source = computed(() =>
  article.value ? resolveSource(article.value, content.snapshot?.sources ?? []) : undefined,
);
const evidence = computed(() =>
  (content.snapshot?.evidence ?? []).filter((item) => article.value?.evidenceIds.includes(item.id)),
);
const related = computed(() => {
  if (!article.value) return [];
  const topicIds = new Set(Object.keys(article.value.topicScores));
  return (content.snapshot?.articles ?? [])
    .filter(
      (item) =>
        item.id !== article.value?.id &&
        Object.keys(item.topicScores).some((topicId) => topicIds.has(topicId)),
    )
    .slice(0, 3);
});
</script>

<template>
  <main id="main-content">
    <div v-if="content.state === 'loading'" class="page-container inner-loading" role="status">
      <span></span><span></span><span></span>
    </div>

    <section v-else-if="!article" class="page-container not-found" data-page-intro>
      <p class="not-found__code">404</p>
      <h1>没有找到这条情报</h1>
      <p>链接可能已失效，或该内容不在当前公开快照中。</p>
      <RouterLink class="button button--primary" to="/">
        <PhArrowLeft :size="17" aria-hidden="true" />
        返回情报流
      </RouterLink>
    </section>

    <template v-else>
      <header class="article-hero" data-page-intro>
        <div class="page-container article-hero__inner">
          <Breadcrumbs current="文章详情" />
          <div class="intel-meta article-hero__meta">
            <span class="source-mark">{{ source?.name.slice(0, 1) ?? 'N' }}</span>
            <strong>{{ source?.name ?? article.sourceId }}</strong>
            <span>{{ source?.region ?? '区域未知' }}</span>
            <span>{{ languageLabel(article.language) }}</span>
            <span>{{ formatDateTime(article.publishedAt) }}</span>
          </div>
          <h1>{{ displayTitle(article) }}</h1>
          <p class="article-original-title">原始标题：{{ article.facts.title }}</p>
          <p class="article-deck">{{ displaySummary(article) }}</p>
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
            <PhSparkle :size="17" weight="fill" aria-hidden="true" />
            <span>AI 整理，请以原始来源为准</span>
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
            <h2>影响对象</h2>
            <p>
              这条信号与
              {{ topicLabels(article, content.snapshot?.topics ?? []).join('、') }}
              相关，适合数据产品经理、AI 产品经理和平台架构团队继续验证。
            </p>
          </section>

          <section id="article-ask" class="article-ask-panel">
            <div>
              <p class="section-kicker">ARTICLE Q&A</p>
              <h2>继续追问当前文章</h2>
              <p>当前为归档模式，文章问答保留入口和示例问题，但不会发起模型调用。</p>
            </div>
            <div class="suggested-question-list">
              <span>这项变化会影响哪些数据产品？</span>
              <span>原始来源提供了哪些直接证据？</span>
              <span>这条信号还有哪些不确定性？</span>
            </div>
            <button class="button button--secondary" type="button" disabled>AI 问答已暂停</button>
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
                  resolveSource(item, content.snapshot?.sources ?? [])?.name ?? item.sourceId
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
