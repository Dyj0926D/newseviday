<script setup lang="ts">
import {
  PhArrowRight,
  PhCheckSquareOffset,
  PhFlask,
  PhGauge,
  PhWarningCircle,
} from '@phosphor-icons/vue';
import { computed, onMounted, ref } from 'vue';

import InnerPageHero from '../components/InnerPageHero.vue';
import InlineNotice from '../components/home/InlineNotice.vue';

interface EvalReport {
  schemaVersion: '1.0.0';
  run: {
    id: string;
    createdAt: string;
    datasetVersion: string;
    retrievalMode: string;
    sampleCount: number;
    metrics: {
      recallAt5: number;
      recallAt10: number;
      mrr: number;
      ndcgAt10: number;
      hitAt5: number;
      p50LatencyMs: number;
      p95LatencyMs: number;
    };
    gate: 'pass' | 'fail' | 'observe';
    corpusSnapshotId: string;
    embeddingModel: string;
  };
  datasetKind: 'demo' | 'production';
  reviewStatus: string;
  corpusHealth: {
    passed: boolean;
    articleCount: number;
    chunkCount: number;
    chunkCoverage: number;
    missingExpectedArticleIds: string[];
  };
  answerQuality: {
    citationCoverage: number | null;
    noAnswerAccuracy: number;
    status: string;
  };
  note: string;
}

const report = ref<EvalReport | null>(null);
const state = ref<'loading' | 'ready' | 'error'>('loading');
const percent = new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 2 });
const generatedAt = computed(() =>
  report.value
    ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(
        new Date(report.value.run.createdAt),
      )
    : '—',
);
const retrievalMetrics = computed(() => {
  const metrics = report.value?.run.metrics;
  return metrics
    ? [
        { name: 'Recall@5', value: percent.format(metrics.recallAt5), target: '目标 ≥ 75%' },
        { name: 'Hit@5', value: percent.format(metrics.hitAt5), target: '目标 ≥ 85%' },
        { name: 'MRR', value: metrics.mrr.toFixed(4), target: '观察项' },
        { name: 'NDCG@10', value: metrics.ndcgAt10.toFixed(4), target: '观察项' },
      ]
    : [];
});

const datasetPlan = [
  ['单一事实定位', 7],
  ['多来源归纳', 7],
  ['国内外对比', 5],
  ['时间变化', 4],
  ['兴趣主题筛选', 3],
  ['无答案与越界', 4],
] as const;

onMounted(async () => {
  const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');
  try {
    const response = await fetch(`${basePath}/data/eval/latest.json`, {
      headers: { Accept: 'application/json' },
      cache: 'no-cache',
    });
    if (!response.ok) throw new Error('eval_report_unavailable');
    const value = (await response.json()) as EvalReport;
    if (value.schemaVersion !== '1.0.0' || !value.run?.metrics) {
      throw new Error('eval_report_invalid');
    }
    report.value = value;
    state.value = 'ready';
  } catch {
    state.value = 'error';
  }
});
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="EVALUATION HARNESS"
      title="把 RAG 能不能上线变成可回答的问题"
      description="评测页公开语料版本、检索策略、指标和发布结论。Demo 工程基线与生产 Gate 分开标记。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" to="/product#evaluation">
          查看技术设计
          <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </template>
    </InnerPageHero>

    <section class="page-container eval-shell">
      <InlineNotice
        v-if="state === 'loading'"
        title="正在读取评测报告"
        description="报告来自随代码发布的版本化 JSON，不会触发在线模型调用。"
      />
      <InlineNotice
        v-else-if="state === 'error'"
        title="评测报告当前不可用"
        description="页面不会用目标值代替实测结果。你仍可查看下方的评测方法和发布边界。"
      />
      <InlineNotice
        v-else
        title="这是 Demo 工程基线，不是生产结论"
        :description="report?.note ?? ''"
      />

      <header class="eval-run-header">
        <div>
          <p class="section-kicker">{{ report ? report.run.gate.toUpperCase() : 'NO RUN' }}</p>
          <h2>{{ report ? '最近一次可复现评测' : '评测方法已就绪' }}</h2>
          <p>
            chunk-level dense retrieval 为当前基线；article-level dense retrieval 保留为 fallback。
          </p>
        </div>
        <dl>
          <div>
            <dt>运行状态</dt>
            <dd>{{ report ? '已完成' : '暂无报告' }}</dd>
          </div>
          <div>
            <dt>测试集</dt>
            <dd>{{ report?.run.sampleCount ?? 0 }} 题</dd>
          </div>
          <div>
            <dt>语料版本</dt>
            <dd>{{ report?.run.corpusSnapshotId ?? '—' }}</dd>
          </div>
          <div>
            <dt>发布结论</dt>
            <dd>{{ report?.run.gate ?? '不可发布' }}</dd>
          </div>
        </dl>
      </header>

      <section v-if="report" class="eval-metrics" aria-labelledby="retrieval-metrics-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">MEASURED RETRIEVAL</p>
            <h2 id="retrieval-metrics-title">Demo 快照实测结果</h2>
            <p>
              {{ report.run.embeddingModel }} · {{ report.run.datasetVersion }} · {{ generatedAt }}
            </p>
          </div>
        </div>
        <div class="metric-grid">
          <article v-for="metric in retrievalMetrics" :key="metric.name">
            <span>{{ metric.target }}</span>
            <h3>{{ metric.name }}</h3>
            <strong>{{ metric.value }}</strong>
            <p>当前 Demo 工程基线实测</p>
          </article>
        </div>
        <div class="eval-secondary-metrics">
          <span>Recall@10 <strong>{{ percent.format(report.run.metrics.recallAt10) }}</strong></span>
          <span>p50 <strong>{{ Math.max(1, report.run.metrics.p50LatencyMs) }} ms</strong></span>
          <span>p95 <strong>{{ Math.max(1, report.run.metrics.p95LatencyMs) }} ms</strong></span>
          <span>Chunk 覆盖
            <strong>{{ percent.format(report.corpusHealth.chunkCoverage) }}</strong></span>
        </div>
      </section>

      <section class="eval-detail-grid">
        <article>
          <PhFlask :size="24" weight="duotone" aria-hidden="true" />
          <h2>黄金测试集设计</h2>
          <p>
            当前 30 题为工程草稿，覆盖事实、多来源、时间变化和无答案拒答；人工复核完成前只用于观察。
          </p>
          <dl class="dataset-plan">
            <div v-for="item in datasetPlan" :key="item[0]">
              <dt>{{ item[0] }}</dt>
              <dd>{{ item[1] }} 题</dd>
            </div>
          </dl>
        </article>

        <article>
          <PhGauge :size="24" weight="duotone" aria-hidden="true" />
          <h2>端到端质量</h2>
          <p>检索基线已运行；生成回答的引用覆盖率仍待人工评测，当前不会把它展示为 0 或伪造结果。</p>
          <ul>
            <li>引用覆盖率：{{ report?.answerQuality.citationCoverage ?? '待评测' }}</li>
            <li>
              Demo 无答案识别：{{
                report ? percent.format(report.answerQuality.noAnswerAccuracy) : '—'
              }}
            </li>
            <li>严重编造直接阻止发布</li>
          </ul>
        </article>

        <article>
          <PhCheckSquareOffset :size="24" weight="duotone" aria-hidden="true" />
          <h2>发布与回滚</h2>
          <p>每个检索配置都带语料、分块、Embedding 和测试集版本；Demo 数据永远只进入 observe。</p>
          <ol>
            <li>固定语料与黄金集</li>
            <li>运行候选策略</li>
            <li>比较质量和延迟</li>
            <li>生产集通过 Gate 后发布</li>
          </ol>
        </article>
      </section>

      <section class="eval-failures">
        <div>
          <PhWarningCircle :size="22" aria-hidden="true" />
          <div>
            <h2>当前限制</h2>
            <p>黄金题尚待人工复核；Demo 仅 6 篇文章；引用覆盖与模型回答质量尚未评测。</p>
          </div>
        </div>
        <p>因此当前 Gate 为 observe。即使离线检索数字达到目标，也不会标记为生产可发布。</p>
      </section>

      <nav class="page-next-links" aria-label="Eval 后续入口">
        <RouterLink to="/ask">
          <span>体验边界</span><strong>查看情报问答与暂停态</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
        <RouterLink to="/product#rag">
          <span>理解方案</span><strong>查看 RAG 技术链路</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
      </nav>
    </section>
  </main>
</template>
