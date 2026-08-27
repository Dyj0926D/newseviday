<script setup lang="ts">
import type { Article } from '@newseviday/contracts';
import { PhArrowRight } from '@phosphor-icons/vue';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import FeedControls from '../components/home/FeedControls.vue';
import HomeImmersiveHero from '../components/home/HomeImmersiveHero.vue';
import InlineNotice from '../components/home/InlineNotice.vue';
import IntelligenceLead from '../components/home/IntelligenceLead.vue';
import IntelligenceRow from '../components/home/IntelligenceRow.vue';
import SignalOverview from '../components/home/SignalOverview.vue';
import {
  diversifyBySource,
  selectKeySignal,
  sortLatestArticles,
  summarizeVisibleFreshness,
} from '../lib/feedRanking';
import { formatDateTime, isChineseDisplayReady, resolveSource } from '../lib/intelligence';
import { useContentStore, type ArchiveArticleEntry } from '../stores/content';
import { useProfileStore } from '../stores/profile';

const route = useRoute();
const router = useRouter();
const content = useContentStore();
const profile = useProfileStore();

const query = ref(readQuery('q'));
const view = ref<'all' | 'recommended'>(
  readQuery('view') === 'recommended' ? 'recommended' : 'all',
);
const topic = ref(readQuery('topic'));
const region = ref(readQuery('region'));
const source = ref(readQuery('source'));
const time = ref(readQuery('time'));
const visibleCount = ref(4);
const savedIds = ref(new Set<string>());
const archiveResults = ref<ArchiveArticleEntry[]>([]);
const archiveSearching = ref(false);
const defaultFeedWindowDays = 30;

const snapshot = computed(() => content.snapshot);
const sources = computed(() => snapshot.value?.sources ?? []);
const topics = computed(() => snapshot.value?.topics ?? []);
const regions = computed(() => [...new Set(sources.value.map((item) => item.region))]);

const filteredArticles = computed(() => {
  const normalizedQuery = query.value.trim().toLocaleLowerCase();
  const anchor = snapshot.value ? new Date(snapshot.value.generatedAt).getTime() : Date.now();
  const windowHours =
    time.value === '24h'
      ? 24
      : time.value === '3d'
        ? 72
        : time.value === '7d'
          ? 168
          : time.value === 'all'
            ? null
            : defaultFeedWindowDays * 24;
  const requireChinese = time.value !== 'all';

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
    if (requireChinese && !isChineseDisplayReady(article)) return false;
    if (windowHours && article.publishedAt) {
      const age = anchor - new Date(article.publishedAt).getTime();
      if (age > windowHours * 60 * 60 * 1000) return false;
    }
    return true;
  });

  if (view.value === 'recommended') {
    return items.sort(
      (left, right) =>
        recommendationScore(right) - recommendationScore(left) ||
        timestamp(right) - timestamp(left),
    );
  }
  return sortLatestArticles(items);
});

const isDefaultFeed = computed(
  () =>
    view.value === 'all' &&
    !query.value.trim() &&
    !topic.value &&
    !region.value &&
    !source.value &&
    !time.value,
);
const keySignalArticle = computed(() =>
  isDefaultFeed.value ? selectKeySignal(filteredArticles.value, new Date().toISOString()) : null,
);
const displayArticles = computed(() => {
  const keySignal = keySignalArticle.value;
  const remaining = keySignal
    ? filteredArticles.value.filter((article) => article.id !== keySignal.id)
    : filteredArticles.value;
  const diversified = diversifyBySource(remaining, {
    leadingSourceIds: keySignal ? [keySignal.sourceId] : [],
  });
  return keySignal ? [keySignal, ...diversified] : diversified;
});
const visibleArticles = computed(() => displayArticles.value.slice(0, visibleCount.value));
const leadArticle = computed(() => keySignalArticle.value);
const listArticles = computed(() =>
  leadArticle.value ? visibleArticles.value.slice(1) : visibleArticles.value,
);
const topicSignals = computed(() =>
  topics.value
    .map((item) => ({
      ...item,
      count: (snapshot.value?.articles ?? []).filter((article) =>
        Object.hasOwn(article.topicScores, item.id),
      ).length,
    }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 4),
);
const overseasCount = computed(
  () =>
    (snapshot.value?.articles ?? []).filter((article) => {
      const itemSource = resolveSource(article, sources.value);
      return Boolean(itemSource?.region && !itemSource.region.includes('中国'));
    }).length,
);
const contributingSourceCount = computed(
  () => new Set((snapshot.value?.articles ?? []).map((article) => article.sourceId)).size,
);
const organizedArticleCount = computed(
  () => (snapshot.value?.articles ?? []).filter((article) => Boolean(article.ai)).length,
);
const modelOrganizedArticleCount = computed(
  () =>
    (snapshot.value?.articles ?? []).filter((article) => article.ai?.provider === 'deepseek')
      .length,
);
const defaultFreshness = computed(() =>
  snapshot.value
    ? summarizeVisibleFreshness(snapshot.value.articles, snapshot.value.generatedAt)
    : { visibleCount: 0, recent24HourCount: 0, latestPublishedAt: null },
);
const recent24HourCount = computed(() => defaultFreshness.value.recent24HourCount);
const latestPublishedAt = computed(() => defaultFreshness.value.latestPublishedAt);
const productionNoticeDescription = computed(() => {
  if (!snapshot.value) return '';
  return `数据整理于 ${formatDateTime(snapshot.value.generatedAt)}，来自 ${contributingSourceCount.value} 个实际贡献来源；${organizedArticleCount.value} 篇已完成中文结构化整理，其中 ${modelOrganizedArticleCount.value} 篇由 AI 生成，其余为编辑整理。重要判断请回到原文核验。`;
});

function readQuery(key: string): string {
  const value = route.query[key];
  return typeof value === 'string' ? value : '';
}

function timestamp(article: Article): number {
  return new Date(article.publishedAt ?? article.collectedAt).getTime();
}

function recommendationScore(article: Article): number {
  const valueScore = contentScore(article);
  if (profile.profile) {
    const profileScore = Object.entries(article.topicScores).reduce(
      (score, [topicId, topicScore]) =>
        score + topicScore * (profile.profile?.interests[topicId] ?? 0),
      0,
    );
    return valueScore * 0.4 + profileScore * 0.6;
  }
  return valueScore;
}

function contentScore(article: Article): number {
  if (typeof article.contentScore === 'number') return article.contentScore;
  return Math.max(0, ...Object.values(article.topicScores)) * 0.65 + 0.35;
}

function recommendationReason(article: Article): string | undefined {
  if (view.value !== 'recommended' || !profile.profile) return undefined;
  const match = Object.entries(article.topicScores)
    .map(([topicId, score]) => ({
      label: topics.value.find((item) => item.id === topicId)?.label ?? topicId,
      score: score * (profile.profile?.interests[topicId] ?? 0),
    }))
    .sort((left, right) => right.score - left.score)[0];
  return match && match.score > 0 ? `与你关注的“${match.label}”相关` : undefined;
}

function updateRoute(key: string, value: string): void {
  const nextQuery = { ...route.query };
  if (value) nextQuery[key] = value;
  else delete nextQuery[key];
  delete nextQuery.focus;
  void router.replace({ path: '/', query: nextQuery });
}

async function submitSearch(): Promise<void> {
  updateRoute('q', query.value.trim());
  archiveSearching.value = query.value.trim().length >= 2;
  archiveResults.value = await content.searchArchive(query.value);
  archiveSearching.value = false;
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

  profile.hydrate();
  await content.refresh();
  if (query.value.trim().length >= 2) await submitSearch();
  if (readQuery('focus') === 'search') {
    await nextTick();
    document.querySelector<HTMLInputElement>('[data-home-search]')?.focus();
  }
});
</script>

<template>
  <main id="main-content">
    <HomeImmersiveHero />

    <div class="home-content-surface">
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
                <h2 id="feed-title">{{ view === 'recommended' ? '为你推荐' : '最新情报' }}</h2>
                <p v-if="time === ''">
                  {{ filteredArticles.length }} 条近 30 天中文情报，按发布时间整理
                </p>
                <p v-else>共 {{ filteredArticles.length }} 条内容，按当前筛选条件整理</p>
              </div>
              <RouterLink class="text-link" to="/brief">
                查看趋势简报
                <PhArrowRight :size="16" aria-hidden="true" />
              </RouterLink>
            </div>

            <InlineNotice
              v-if="content.isDemo"
              title="当前为内容预览"
              description="页面展示用于体验产品流程的示例内容，来源与结论不用于实时判断。"
            />
            <InlineNotice
              v-else-if="snapshot"
              title="当前为受控更新"
              :description="productionNoticeDescription"
            />
            <InlineNotice
              v-if="isDefaultFeed && snapshot && recent24HourCount === 0"
              title="今日暂无新入选情报"
              :description="`最近 24 小时没有内容同时通过来源、主题和中文展示门槛。以下展示近 30 天情报，最近一篇发布于 ${formatDateTime(latestPublishedAt)}。`"
            />
            <InlineNotice
              v-if="isDefaultFeed && snapshot && !keySignalArticle"
              title="今日暂无达标重点信号"
              description="当前内容已通过基础质量筛选，但没有一条同时满足相关性、工程价值、证据成熟度和中文展示门槛。以下信息流仍按内容价值排序。"
            />

            <InlineNotice
              v-if="view === 'recommended' && !profile.hasProfile"
              title="当前使用通用推荐"
              description="你还没有设置关注偏好，系统会按站点主题相关度排序。该功能完全可选。"
            />

            <div
              v-if="content.state === 'loading'"
              class="feed-loading"
              role="status"
              aria-label="正在读取情报快照"
            >
              <span></span><span></span><span></span>
            </div>

            <div v-else-if="visibleArticles.length" class="intelligence-feed">
              <IntelligenceLead
                v-if="leadArticle"
                :article="leadArticle"
                :source="resolveSource(leadArticle, sources)"
                :topics="topics"
                :saved="savedIds.has(leadArticle.id)"
                :recommendation-reason="recommendationReason(leadArticle)"
                @save="toggleSaved"
              />
              <IntelligenceRow
                v-for="article in listArticles"
                :key="article.id"
                :article="article"
                :source="resolveSource(article, sources)"
                :topics="topics"
                :saved="savedIds.has(article.id)"
                :recommendation-reason="recommendationReason(article)"
                @save="toggleSaved"
              />

              <div v-if="visibleCount < displayArticles.length" class="load-more">
                <button class="button button--secondary" type="button" @click="visibleCount += 4">
                  加载更多情报
                </button>
                <span>已展示 {{ visibleArticles.length }} / {{ displayArticles.length }}</span>
              </div>
            </div>

            <div v-else class="empty-state" role="status">
              <h3>{{ content.state === 'error' ? '快照暂时无法读取' : '没有符合条件的情报' }}</h3>
              <p>你可以调整筛选条件，或查看最近一次有效内容快照。</p>
              <button class="button button--secondary" type="button" @click="clearFilters">
                清除筛选
              </button>
            </div>

            <section v-if="query.trim().length >= 2" class="archive-search" aria-live="polite">
              <div>
                <p class="section-kicker">PUBLIC ARCHIVE</p>
                <h3>历史快照匹配</h3>
                <span>{{
                  archiveSearching
                    ? '正在检索公开历史索引'
                    : `${archiveResults.length} 条历史标题匹配`
                }}</span>
              </div>
              <RouterLink v-for="item in archiveResults" :key="item.id" :to="`/article/${item.id}`">
                <strong>{{ item.title }}</strong>
                <small>
                  {{ item.sourceId }} ·
                  {{ item.publishedAt ? formatDateTime(item.publishedAt) : '时间未知' }}
                </small>
              </RouterLink>
              <p v-if="!archiveSearching && !archiveResults.length">
                公开历史索引只检索标题和来源，不等同于全文或语义检索。
              </p>
            </section>
          </div>
        </div>

        <SignalOverview
          :source-count="contributingSourceCount"
          :overseas-count="overseasCount"
          :new-count="filteredArticles.length"
          :updated-at="snapshot?.generatedAt ?? null"
          :topics="topicSignals"
          :demo="content.isDemo"
        />
      </section>
    </div>
  </main>
</template>

<style scoped>
.home-content-surface {
  position: relative;
  z-index: 2;
  margin-top: -2.75rem;
  border-radius: 2.25rem 2.25rem 0 0;
  background: var(--ne-color-bg-page);
  box-shadow: 0 -1rem 3.5rem rgb(10 9 27 / 8%);
}

.archive-search {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.5rem;
  padding: 1.25rem;
  border: 1px solid var(--ne-color-border-subtle);
  border-radius: var(--ne-radius-lg);
  background: var(--ne-color-bg-surface);
}

.archive-search > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}

.archive-search h3 {
  margin: 0.15rem 0 0;
}

.archive-search > a {
  display: grid;
  gap: 0.25rem;
  padding: 0.8rem 0;
  border-top: 1px solid var(--ne-color-border-subtle);
  color: inherit;
  text-decoration: none;
}

.archive-search small,
.archive-search span,
.archive-search > p {
  color: var(--ne-color-text-muted);
}

@media (max-width: 767px) {
  .home-content-surface {
    margin-top: -1.5rem;
    border-radius: 1.5rem 1.5rem 0 0;
  }
}
</style>
