<script setup lang="ts">
import type { Article } from '@newseviday/contracts';
import { PhArrowRight, PhSparkle } from '@phosphor-icons/vue';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import PageIntro from '../components/PageIntro.vue';
import FeedControls from '../components/home/FeedControls.vue';
import InlineNotice from '../components/home/InlineNotice.vue';
import IntelligenceLead from '../components/home/IntelligenceLead.vue';
import IntelligenceRow from '../components/home/IntelligenceRow.vue';
import SignalOverview from '../components/home/SignalOverview.vue';
import { resolveSource } from '../lib/intelligence';
import { useContentStore } from '../stores/content';

const route = useRoute();
const router = useRouter();
const content = useContentStore();

const query = ref(readQuery('q'));
const view = ref<'all' | 'recommended'>(readQuery('view') === 'recommended' ? 'recommended' : 'all');
const topic = ref(readQuery('topic'));
const region = ref(readQuery('region'));
const source = ref(readQuery('source'));
const time = ref(readQuery('time'));
const visibleCount = ref(4);
const savedIds = ref(new Set<string>());

const snapshot = computed(() => content.snapshot);
const sources = computed(() => snapshot.value?.sources ?? []);
const topics = computed(() => snapshot.value?.topics ?? []);
const regions = computed(() => [...new Set(sources.value.map((item) => item.region))]);

const filteredArticles = computed(() => {
  const normalizedQuery = query.value.trim().toLocaleLowerCase();
  const anchor = snapshot.value ? new Date(snapshot.value.generatedAt).getTime() : Date.now();
  const windowHours = time.value === '24h' ? 24 : time.value === '3d' ? 72 : time.value === '7d' ? 168 : null;

  const items = (snapshot.value?.articles ?? []).filter((article) => {
    const articleSource = resolveSource(article, sources.value);
    const searchable = [
      article.facts.title,
      article.facts.abstract,
      article.ai?.titleZh,
      article.ai?.summaryZh,
      article.ai?.whyItMatters,
      articleSource?.name,
      articleSource?.region,
    ]
      .filter(Boolean)
      .join(' ')
      .toLocaleLowerCase();

    if (normalizedQuery && !searchable.includes(normalizedQuery)) return false;
    if (topic.value && !Object.hasOwn(article.topicScores, topic.value)) return false;
    if (source.value && article.sourceId !== source.value) return false;
    if (region.value && articleSource?.region !== region.value) return false;
    if (windowHours && article.publishedAt) {
      const age = anchor - new Date(article.publishedAt).getTime();
      if (age > windowHours * 60 * 60 * 1000) return false;
    }
    return true;
  });

  return items.sort((left, right) => {
    if (view.value === 'recommended') return recommendationScore(right) - recommendationScore(left);
    return timestamp(right) - timestamp(left);
  });
});

const visibleArticles = computed(() => filteredArticles.value.slice(0, visibleCount.value));
const leadArticle = computed(() => visibleArticles.value[0] ?? null);
const listArticles = computed(() => visibleArticles.value.slice(1));
const topicSignals = computed(() =>
  topics.value
    .map((item) => ({
      ...item,
      count: (snapshot.value?.articles ?? []).filter((article) => Object.hasOwn(article.topicScores, item.id)).length,
    }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 4),
);
const overseasCount = computed(() =>
  (snapshot.value?.articles ?? []).filter((article) => {
    const itemSource = resolveSource(article, sources.value);
    return itemSource?.region !== '中国';
  }).length,
);

function readQuery(key: string): string {
  const value = route.query[key];
  return typeof value === 'string' ? value : '';
}

function timestamp(article: Article): number {
  return new Date(article.publishedAt ?? article.collectedAt).getTime();
}

function recommendationScore(article: Article): number {
  return Math.max(0, ...Object.values(article.topicScores));
}

function updateRoute(key: string, value: string): void {
  const nextQuery = { ...route.query };
  if (value) nextQuery[key] = value;
  else delete nextQuery[key];
  delete nextQuery.focus;
  void router.replace({ path: '/', query: nextQuery });
}

function submitSearch(): void {
  updateRoute('q', query.value.trim());
}

function setView(value: 'all' | 'recommended'): void {
  view.value = value;
  updateRoute('view', value === 'all' ? '' : value);
}

function setFilter(key: 'topic' | 'region' | 'source' | 'time', value: string): void {
  if (key === 'topic') topic.value = value;
  if (key === 'region') region.value = value;
  if (key === 'source') source.value = value;
  if (key === 'time') time.value = value;
  updateRoute(key, value);
}

function toggleSaved(articleId: string): void {
  const next = new Set(savedIds.value);
  if (next.has(articleId)) next.delete(articleId);
  else next.add(articleId);
  savedIds.value = next;
  localStorage.setItem('newseviday-saved-articles', JSON.stringify([...next]));
}

function clearFilters(): void {
  query.value = '';
  topic.value = '';
  region.value = '';
  source.value = '';
  time.value = '';
  view.value = 'all';
  void router.replace({ path: '/' });
}

watch([query, view, topic, region, source, time], () => {
  visibleCount.value = 4;
});

watch(
  () => route.query,
  () => {
    query.value = readQuery('q');
    view.value = readQuery('view') === 'recommended' ? 'recommended' : 'all';
    topic.value = readQuery('topic');
    region.value = readQuery('region');
    source.value = readQuery('source');
    time.value = readQuery('time');
  },
);

onMounted(async () => {
  const stored = localStorage.getItem('newseviday-saved-articles');
  if (stored) {
    try {
      savedIds.value = new Set(JSON.parse(stored) as string[]);
    } catch {
      localStorage.removeItem('newseviday-saved-articles');
    }
  }

  await content.refresh();
  if (readQuery('focus') === 'search') {
    await nextTick();
    document.querySelector<HTMLInputElement>('[data-home-search]')?.focus();
  }
});
</script>

<template>
  <main id="main-content">
    <PageIntro
      eyebrow="DAILY INTELLIGENCE · 今日更新"
      title="发现变化，看见脉络"
      description="海内外 AI 与数据情报，经过翻译、整理与证据关联。"
    >
      <template #actions>
        <RouterLink class="button button--primary" to="/profile">
          <PhSparkle :size="17" weight="fill" aria-hidden="true" />
          定制我的关注
        </RouterLink>
        <RouterLink class="hero-text-link" to="/product">
          看懂产品方法
          <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </template>
    </PageIntro>

    <section class="page-container intelligence-shell" aria-labelledby="feed-title">
      <div class="intelligence-main">
        <FeedControls
          :query="query"
          :view="view"
          :topics="topics"
          :topic="topic"
          :region="region"
          :source="source"
          :time="time"
          :regions="regions"
          :sources="sources"
          @search="submitSearch"
          @update:query="query = $event"
          @update:view="setView"
          @update:topic="setFilter('topic', $event)"
          @update:region="setFilter('region', $event)"
          @update:source="setFilter('source', $event)"
          @update:time="setFilter('time', $event)"
        />

        <div class="intelligence-feed-content">
          <div class="section-heading intelligence-heading">
            <div>
              <p class="section-kicker">CURATED FEED</p>
              <h2 id="feed-title">{{ view === 'recommended' ? '为你推荐' : '今日情报' }}</h2>
              <p>{{ filteredArticles.length }} 条信号，按来源时间与主题相关度整理</p>
            </div>
            <RouterLink class="text-link" to="/brief">
              查看趋势简报
              <PhArrowRight :size="16" aria-hidden="true" />
            </RouterLink>
          </div>

          <InlineNotice
            v-if="content.isDemo"
            title="当前展示产品演示快照"
            description="内容用于验证页面结构与产品流程，不代表实时新闻。真实采集和 DeepSeek 调用仍保持关闭。"
          />

          <div v-if="content.state === 'loading'" class="feed-loading" role="status" aria-label="正在读取情报快照">
            <span></span><span></span><span></span>
          </div>

          <div v-else-if="leadArticle" class="intelligence-feed">
            <IntelligenceLead
              :article="leadArticle"
              :source="resolveSource(leadArticle, sources)"
              :topics="topics"
              :saved="savedIds.has(leadArticle.id)"
              @save="toggleSaved"
            />
            <IntelligenceRow
              v-for="article in listArticles"
              :key="article.id"
              :article="article"
              :source="resolveSource(article, sources)"
              :topics="topics"
              :saved="savedIds.has(article.id)"
              @save="toggleSaved"
            />

            <div v-if="visibleCount < filteredArticles.length" class="load-more">
              <button class="button button--secondary" type="button" @click="visibleCount += 4">
                加载更多情报
              </button>
              <span>已展示 {{ visibleArticles.length }} / {{ filteredArticles.length }}</span>
            </div>
          </div>

          <div v-else class="empty-state" role="status">
            <h3>{{ content.state === 'error' ? '快照暂时无法读取' : '没有符合条件的情报' }}</h3>
            <p>页面主体仍可浏览。你可以清除筛选，或稍后查看新的归档快照。</p>
            <button class="button button--secondary" type="button" @click="clearFilters">清除筛选</button>
          </div>
        </div>
      </div>

      <SignalOverview
        :source-count="snapshot?.sourceCount ?? 0"
        :overseas-count="overseasCount"
        :new-count="snapshot?.articles.length ?? 0"
        :updated-at="snapshot?.generatedAt ?? null"
        :topics="topicSignals"
        :demo="content.isDemo"
      />
    </section>
  </main>
</template>
