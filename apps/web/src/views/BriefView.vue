<script setup lang="ts">
import { PhArrowRight, PhArrowUpRight, PhCalendarBlank } from '@phosphor-icons/vue';
import { computed } from 'vue';

import InnerPageHero from '../components/InnerPageHero.vue';
import InlineNotice from '../components/home/InlineNotice.vue';
import { displayTitle, formatDateTime, resolveSource } from '../lib/intelligence';
import { useContentStore } from '../stores/content';

const content = useContentStore();
const brief = computed(() => content.snapshot?.briefs[0] ?? null);
const sectionEvidence = computed(() => {
  const index = new Map<
    string,
    Array<{ evidenceId: string; articleId: string; title: string; source: string; url: string }>
  >();
  for (const section of brief.value?.sections ?? []) {
    const items = section.evidenceIds.flatMap((evidenceId) => {
      const evidence = content.snapshot?.evidence.find((item) => item.id === evidenceId);
      const article = content.snapshot?.articles.find((item) => item.id === evidence?.articleId);
      if (!evidence || !article) return [];
      return [
        {
          evidenceId,
          articleId: article.id,
          title: displayTitle(article),
          source: resolveSource(article, content.snapshot?.sources ?? [])?.name ?? article.sourceId,
          url: evidence.url,
        },
      ];
    });
    index.set(section.heading, items);
  }
  return index;
});

function formatPeriod(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value));
}
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="7-DAY TREND BRIEF"
      title="把分散信号整理成可验证的趋势"
      description="从近 7 天情报中提炼变化、影响和观察问题，每个判断都回到相关来源。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" to="/ask">
          带着趋势继续追问
          <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </template>
    </InnerPageHero>

    <section v-if="content.state === 'loading'" class="page-container inner-loading" role="status">
      <span></span><span></span><span></span>
    </section>

    <section v-else-if="!brief" class="page-container empty-state page-empty">
      <h2>当前没有可用简报</h2>
      <p>内容不足或生成失败时不会覆盖上一版成功快照。</p>
      <RouterLink class="button button--secondary" to="/">返回最新情报</RouterLink>
    </section>

    <template v-else>
      <section class="page-container brief-header" aria-labelledby="brief-title">
        <div>
          <p class="section-kicker">LATEST BRIEF</p>
          <h2 id="brief-title">{{ brief.title }}</h2>
        </div>
        <dl>
          <div>
            <dt>覆盖时间</dt>
            <dd>{{ formatPeriod(brief.periodStart) }} 至 {{ formatPeriod(brief.periodEnd) }}</dd>
          </div>
          <div>
            <dt>生成时间</dt>
            <dd>{{ formatDateTime(brief.publishedAt) }}</dd>
          </div>
          <div>
            <dt>快照来源</dt>
            <dd>{{ content.snapshot?.sourceCount ?? 0 }} 个</dd>
          </div>
          <div>
            <dt>整理方式</dt>
            <dd>
              {{
                brief.generatedBy?.model === 'demo-fixture'
                  ? '内容示例'
                  : (brief.generatedBy?.model ?? '规则生成')
              }}
            </dd>
          </div>
        </dl>
      </section>

      <section class="page-container brief-layout">
        <div class="brief-main">
          <InlineNotice
            title="当前为趋势内容预览"
            description="结论用于体验简报结构和证据回链，不用于实时市场判断。"
          />

          <article
            v-for="(section, index) in brief.sections"
            :key="section.heading"
            class="trend-block"
          >
            <div class="trend-block__number">{{ String(index + 1).padStart(2, '0') }}</div>
            <div class="trend-block__content">
              <p class="trend-block__label">主要趋势</p>
              <h2>{{ section.heading }}</h2>
              <div class="trend-copy">
                <h3>发生了什么变化</h3>
                <p>{{ section.body }}</p>
              </div>
              <div class="trend-evidence">
                <h3>变化依据</h3>
                <RouterLink
                  v-for="(item, evidenceIndex) in sectionEvidence.get(section.heading) ?? []"
                  :key="item.evidenceId"
                  :to="`/article/${item.articleId}`"
                >
                  <span>[{{ evidenceIndex + 1 }}] {{ item.source }}</span>
                  <strong>{{ item.title }}</strong>
                  <PhArrowUpRight :size="17" aria-hidden="true" />
                </RouterLink>
              </div>
              <p class="trend-uncertainty">
                不确定性：当前内容为预览样例，需要结合更多来源重新验证趋势强度。
              </p>
            </div>
          </article>
        </div>

        <aside class="brief-sidebar">
          <section>
            <div class="brief-sidebar__heading">
              <PhCalendarBlank :size="20" aria-hidden="true" />
              <h2>阅读说明</h2>
            </div>
            <ul>
              <li>每个判断关联原始来源</li>
              <li>单一来源会明确标记</li>
              <li>证据不足时不生成强结论</li>
              <li>更新失败时保留上一版内容</li>
            </ul>
          </section>
          <RouterLink class="button button--secondary" to="/">查看全部情报</RouterLink>
        </aside>
      </section>
    </template>
  </main>
</template>
