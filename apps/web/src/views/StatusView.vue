<script setup lang="ts">
import {
  PhArrowRight,
  PhArchive,
  PhDatabase,
  PhRobot,
  PhShieldCheck,
  PhWarningCircle,
} from '@phosphor-icons/vue';
import { computed } from 'vue';

import InnerPageHero from '../components/InnerPageHero.vue';
import { formatDateTime } from '../lib/intelligence';
import { useContentStore } from '../stores/content';
import { useRuntimeStore } from '../stores/runtime';

const content = useContentStore();
const runtime = useRuntimeStore();
const isRefreshing = computed(
  () => content.state === 'loading' || runtime.requestState === 'loading',
);
const contributingSources = computed(() => {
  const sourceIds = new Set((content.snapshot?.articles ?? []).map((article) => article.sourceId));
  return (content.snapshot?.sources ?? []).filter((source) => sourceIds.has(source.id));
});
const aiArticleCount = computed(
  () => (content.snapshot?.articles ?? []).filter((article) => Boolean(article.ai)).length,
);
const ragAvailable = computed(
  () => runtime.status?.rag.state === 'available' || runtime.status?.rag.state === 'saving-mode',
);
const protectionReady = computed(
  () =>
    runtime.status?.protection?.persistentGuardrails === 'available' &&
    runtime.status?.protection?.turnstile === 'enabled',
);

async function refreshStatus(): Promise<void> {
  await Promise.all([content.refresh(true), runtime.refresh()]);
}
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="PUBLIC SYSTEM STATUS"
      title="查看内容更新时间与可用能力"
      description="这里公开最近一次内容快照、来源范围和在线能力状态，不展示敏感配置。"
    >
      <template #actions>
        <button
          class="button button--secondary"
          type="button"
          :disabled="isRefreshing"
          @click="refreshStatus"
        >
          {{ isRefreshing ? '正在确认' : '重新确认状态' }}
        </button>
      </template>
    </InnerPageHero>

    <section class="page-container status-shell">
      <div class="status-summary">
        <article>
          <PhArchive :size="22" weight="duotone" aria-hidden="true" />
          <span>内容服务</span>
          <strong>{{ runtime.modeLabel }}</strong>
          <p>最近一次有效内容可持续访问</p>
        </article>
        <article>
          <PhDatabase :size="22" weight="duotone" aria-hidden="true" />
          <span>内容快照</span>
          <strong>{{ content.snapshot?.state === 'ready' ? '可用' : '不可用' }}</strong>
          <p>{{ content.snapshot?.articles.length ?? 0 }} 条公开情报</p>
        </article>
        <article>
          <PhRobot :size="22" weight="duotone" aria-hidden="true" />
          <span>证据问答</span>
          <strong>{{ ragAvailable ? '可用' : '准备中' }}</strong>
          <p>
            {{ ragAvailable ? '引用式问答可用' : '当前仅展示已有内容' }}
          </p>
        </article>
        <article>
          <PhShieldCheck :size="22" weight="duotone" aria-hidden="true" />
          <span>生成保护</span>
          <strong>{{ protectionReady ? '已就绪' : '未启用' }}</strong>
          <p>{{ protectionReady ? '限额、预算与人机校验生效' : '生成能力保持关闭' }}</p>
        </article>
      </div>

      <section class="status-details">
        <div class="section-heading">
          <div>
            <p class="section-kicker">CONTENT SNAPSHOT</p>
            <h2>当前数据快照</h2>
            <p>这里只确认快照中包含什么，不推断每个外部来源此刻仍然在线。</p>
          </div>
        </div>
        <dl class="status-facts">
          <div>
            <dt>快照 ID</dt>
            <dd>{{ content.snapshot?.snapshotId ?? '未知' }}</dd>
          </div>
          <div>
            <dt>最后整理时间</dt>
            <dd>{{ content.snapshot ? formatDateTime(content.snapshot.generatedAt) : '未知' }}</dd>
          </div>
          <div>
            <dt>内容来源</dt>
            <dd>{{ contributingSources.length }}</dd>
          </div>
          <div>
            <dt>简报数量</dt>
            <dd>{{ content.snapshot?.briefs.length ?? 0 }}</dd>
          </div>
        </dl>
      </section>

      <section class="source-status-section">
        <div class="section-heading">
          <div>
            <p class="section-kicker">SOURCE CATALOG</p>
            <h2>快照内来源</h2>
            <p>“快照可用”仅表示当前内容中保留了对应来源元数据。</p>
          </div>
        </div>
        <div class="source-status-list">
          <article v-for="source in contributingSources" :key="source.id">
            <span class="source-mark">{{ source.name.slice(0, 1) }}</span>
            <div>
              <strong>{{ source.name }}</strong><small>{{ source.region }} · {{ source.language }}</small>
            </div>
            <span class="status-text">快照可用</span>
            <a :href="source.homepageUrl" target="_blank" rel="noreferrer">访问来源</a>
          </article>
        </div>
      </section>

      <section class="known-issues">
        <div>
          <PhWarningCircle :size="22" aria-hidden="true" />
          <div>
            <h2>当前说明</h2>
            <p>以下信息帮助你判断内容时效和能力范围。</p>
          </div>
        </div>
        <ul>
          <li>
            <template v-if="content.isDemo">
              <strong>内容预览</strong><span>当前
                {{ content.snapshot?.articles.length ?? 0 }}
                条内容用于体验产品流程，不用于实时判断。</span>
            </template>
            <template v-else>
              <strong>受控生产快照</strong><span>当前
                {{ content.snapshot?.articles.length ?? 0 }} 条内容来自
                {{ contributingSources.length }} 个实际贡献来源，其中
                {{ aiArticleCount }} 篇经 AI 结构化整理。</span>
            </template>
          </li>
          <li>
            <strong>更新方式</strong><span>定时采集候选内容，质量检查通过后发布；任务失败或暂停时保留最近一次有效快照。</span>
          </li>
          <li>
            <strong>备用访问</strong><span>主站异常时可使用静态备用站浏览最近一次内容。</span>
          </li>
        </ul>
      </section>

      <nav class="page-next-links" aria-label="状态页后续入口">
        <RouterLink to="/">
          <span>返回内容</span><strong>浏览最新情报</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
        <RouterLink to="/product#cost-security">
          <span>了解边界</span><strong>查看成本与安全设计</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
      </nav>
    </section>
  </main>
</template>
