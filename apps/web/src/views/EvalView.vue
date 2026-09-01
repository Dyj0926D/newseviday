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
import { useContentStore } from '../stores/content';

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
    lowScoreRefusalAccuracy?: number;
    answerablePassRate?: number;
    agentMode?: string;
    averageRetrievalRounds?: number;
    status: string;
  };
  note: string;
}

interface PublicEvalReport {
  schemaVersion: '1.0.0';
  benchmark: string;
  datasetRevision: string;
  retrievalMode: string;
  corpusDocumentCount: number;
  evaluatedQuestionCount: number;
  excludedNullQuestionCount: number;
  metrics: EvalReport['run']['metrics'];
  note: string;
}

const report = ref<EvalReport | null>(null);
const publicReport = ref<PublicEvalReport | null>(null);
const state = ref<'loading' | 'ready' | 'error'>('loading');
const content = useContentStore();
const percent = new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 2 });
const generatedAt = computed(() =>
  report.value
    ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(
        new Date(report.value.run.createdAt),
      )
    : '暂无',
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
const gateLabel = computed(() => {
  if (!report.value) return '暂无结论';
  if (report.value.run.gate === 'pass') return '达到发布门槛';
  if (report.value.run.gate === 'fail') return '未达到发布门槛';
  return '观察结果';
});
const retrievalModeLabel = computed(() => {
  if (!report.value) return '暂无';
  if (report.value.run.retrievalMode === 'chunk_dense') return '分块检索基线';
  if (report.value.run.retrievalMode === 'chunk_bm25') return '分块 BM25 检索';
  if (report.value.run.retrievalMode === 'article_dense') return '文章检索基线';
  return report.value.run.retrievalMode;
});
const reportMatchesCurrentSnapshot = computed(
  () => Boolean(report.value && report.value.run.corpusSnapshotId === content.snapshot?.snapshotId),
);
const reportNotice = computed(() => {
  if (!report.value) return '';
  if (reportMatchesCurrentSnapshot.value) return report.value.note;
  return `该报告基于快照 ${report.value.run.corpusSnapshotId}，当前页面内容已更新为 ${content.snapshot?.snapshotId ?? '未知快照'}。指标仅代表固定语料基线，当前生产快照的黄金集仍在补充。`;
});

const datasetPlan = [
  ['单一事实定位', 6],
  ['Agent 工程', 1],
  ['AI 安全', 2],
  ['RAG 与检索', 1],
  ['多来源归纳', 2],
  ['无答案、越界与安全边界', 12],
] as const;

onMounted(async () => {
  const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');
  try {
    const [response, publicResponse] = await Promise.all([
      fetch(`${basePath}/data/eval/latest.json`, {
        headers: { Accept: 'application/json' },
        cache: 'no-cache',
      }),
      fetch(`${basePath}/data/eval/multihop-bm25.json`, {
        headers: { Accept: 'application/json' },
        cache: 'no-cache',
      }),
      content.refresh(),
    ]);
    if (!response.ok) throw new Error('eval_report_unavailable');
    const value = (await response.json()) as EvalReport;
    if (value.schemaVersion !== '1.0.0' || !value.run?.metrics) {
      throw new Error('eval_report_invalid');
    }
    report.value = value;
    if (publicResponse.ok) {
      const publicValue = (await publicResponse.json()) as PublicEvalReport;
      if (publicValue.schemaVersion === '1.0.0' && publicValue.metrics) {
        publicReport.value = publicValue;
      }
    }
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
      title="用可复现评测约束检索质量"
      description="公开数据版本、检索策略、质量指标和发布结论，让每次策略变化都可以比较和回滚。"
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
        :title="reportMatchesCurrentSnapshot ? '当前结果来自小规模验证集' : '当前结果属于固定评测基线'"
        :description="reportNotice"
      />

      <header class="eval-run-header">
        <div>
          <p class="section-kicker">{{ report ? 'MEASURED' : 'NO RUN' }}</p>
          <h2>{{ report ? '最近一次可复现检索评测' : '评测方法已就绪' }}</h2>
          <p>离线评测使用版本化分块检索与有限步骤证据门禁；在线证据问答需要单独通过发布验证。</p>
        </div>
        <dl>
          <div>
            <dt>评测状态</dt>
            <dd>{{ report ? '已完成' : '暂无报告' }}</dd>
          </div>
          <div>
            <dt>样本规模</dt>
            <dd>{{ report?.run.sampleCount ?? 0 }} 题</dd>
          </div>
          <div>
            <dt>数据版本</dt>
            <dd>{{ report?.run.datasetVersion ?? '暂无' }}</dd>
          </div>
          <div>
            <dt>质量结论</dt>
            <dd>{{ gateLabel }}</dd>
          </div>
        </dl>
      </header>

      <section v-if="report" class="eval-metrics" aria-labelledby="retrieval-metrics-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">MEASURED RETRIEVAL</p>
            <h2 id="retrieval-metrics-title">生产试运行集实测结果</h2>
            <p>{{ retrievalModeLabel }} · {{ report.run.embeddingModel }} · {{ generatedAt }}</p>
          </div>
        </div>
        <div class="metric-grid">
          <article v-for="metric in retrievalMetrics" :key="metric.name">
            <span>{{ metric.target }}</span>
            <h3>{{ metric.name }}</h3>
            <strong>{{ metric.value }}</strong>
            <p>当前验证集实测</p>
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

      <section v-if="publicReport" class="eval-metrics" aria-labelledby="public-metrics-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">OPEN BENCHMARK</p>
            <h2 id="public-metrics-title">跨文档公开基准</h2>
            <p>
              {{ publicReport.benchmark }} · {{ publicReport.evaluatedQuestionCount }} 道可回答问题 ·
              {{ publicReport.corpusDocumentCount }} 篇语料
            </p>
          </div>
        </div>
        <div class="metric-grid">
          <article>
            <span>跨文档召回</span><h3>Recall@5</h3>
            <strong>{{ percent.format(publicReport.metrics.recallAt5) }}</strong>
            <p>全量可回答问题实测</p>
          </article>
          <article>
            <span>前五命中</span><h3>Hit@5</h3>
            <strong>{{ percent.format(publicReport.metrics.hitAt5) }}</strong>
            <p>全量可回答问题实测</p>
          </article>
          <article>
            <span>首条相关证据</span><h3>MRR</h3>
            <strong>{{ publicReport.metrics.mrr.toFixed(4) }}</strong>
            <p>BM25 低成本基线</p>
          </article>
          <article>
            <span>前十排序质量</span><h3>NDCG@10</h3>
            <strong>{{ publicReport.metrics.ndcgAt10.toFixed(4) }}</strong>
            <p>BM25 低成本基线</p>
          </article>
        </div>
        <div class="eval-secondary-metrics">
          <span>Recall@10 <strong>{{ percent.format(publicReport.metrics.recallAt10) }}</strong></span>
          <span>p95 <strong>{{ publicReport.metrics.p95LatencyMs }} ms</strong></span>
          <span>无证据题 <strong>{{ publicReport.excludedNullQuestionCount }} 题</strong></span>
          <span>版本 <strong>{{ publicReport.datasetRevision.slice(0, 8) }}</strong></span>
        </div>
        <p>{{ publicReport.note }}</p>
      </section>

      <section class="eval-detail-grid">
        <article>
          <PhFlask :size="24" weight="duotone" aria-hidden="true" />
          <h2>黄金测试集设计</h2>
          <p>验证集固定在同一生产快照，覆盖事实定位、多来源归纳和无答案拒答；24题检索证据与拒答判断已完成人工复核。</p>
          <dl class="dataset-plan">
            <div v-for="item in datasetPlan" :key="item[0]">
              <dt>{{ item[0] }}</dt>
              <dd>{{ item[1] }} 题</dd>
            </div>
          </dl>
        </article>

        <article>
          <PhGauge :size="24" weight="duotone" aria-hidden="true" />
          <h2>证据充分性门禁</h2>
          <p>系统最多进行两轮检索，并检查问题范围、时间边界和必需证据；生成回答已进入逐句引用评测。</p>
          <ul>
            <li>引用覆盖率：{{ report?.answerQuality.citationCoverage ?? '评测进行中' }}</li>
            <li>
              证据门禁无答案识别：{{ report ? percent.format(report.answerQuality.noAnswerAccuracy) : '暂无' }}
            </li>
            <li v-if="report?.answerQuality.lowScoreRefusalAccuracy !== undefined">
              旧阈值拒答基线：{{ percent.format(report.answerQuality.lowScoreRefusalAccuracy) }}
            </li>
            <li v-if="report?.answerQuality.answerablePassRate !== undefined">
              可回答问题通过率：{{ percent.format(report.answerQuality.answerablePassRate) }}
            </li>
            <li v-if="report?.answerQuality.averageRetrievalRounds !== undefined">
              平均检索轮次：{{ report.answerQuality.averageRetrievalRounds.toFixed(2) }} / 2
            </li>
            <li>严重编造直接阻止发布</li>
          </ul>
        </article>

        <article>
          <PhCheckSquareOffset :size="24" weight="duotone" aria-hidden="true" />
          <h2>发布与回滚</h2>
          <p>每个检索配置都绑定数据、分块、Embedding 和测试集版本，确保结果可比较、可回滚。</p>
          <ol>
            <li>固定语料与黄金集</li>
            <li>运行候选策略</li>
            <li>比较质量和延迟</li>
            <li>达到质量门槛后发布</li>
          </ol>
        </article>
      </section>

      <section class="eval-failures">
        <div>
          <PhWarningCircle :size="22" aria-hidden="true" />
          <div>
            <h2>当前限制</h2>
            <p>内部集规模较小，已增加 MultiHop-RAG 全量可回答问题作为跨文档迁移对照；模型回答仍需完成逐句引用人工复核。</p>
          </div>
        </div>
        <p>当前结论仅用于比较检索策略，不能替代正式内容和在线链路的发布验收。</p>
      </section>

      <nav class="page-next-links" aria-label="质量评测后续入口">
        <RouterLink to="/ask">
          <span>体验能力</span><strong>查看证据问答</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
        <RouterLink to="/product#rag">
          <span>理解方案</span><strong>查看 RAG 技术链路</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
      </nav>
    </section>
  </main>
</template>
