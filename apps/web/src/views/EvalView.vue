<script setup lang="ts">
import {
  PhArrowRight,
  PhCheckSquareOffset,
  PhFlask,
  PhGauge,
  PhWarningCircle,
} from '@phosphor-icons/vue';

import InnerPageHero from '../components/InnerPageHero.vue';
import InlineNotice from '../components/home/InlineNotice.vue';

const retrievalTargets = [
  { name: 'Recall@5', target: '≥ 0.75', meaning: '正确证据是否进入前 5 个候选' },
  { name: 'Hit@5', target: '观察项', meaning: '至少命中一个相关证据的比例' },
  { name: 'MRR', target: '观察项', meaning: '首个相关结果是否足够靠前' },
  { name: 'NDCG@10', target: '观察项', meaning: '前 10 个结果的相关性排序质量' },
];

const datasetPlan = [
  ['单一事实定位', 7],
  ['多来源归纳', 7],
  ['国内外对比', 5],
  ['时间变化', 4],
  ['兴趣主题筛选', 3],
  ['无答案与越界', 4],
] as const;
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="EVALUATION HARNESS"
      title="把 RAG 能不能上线变成可回答的问题"
      description="评测页公开检索策略、发布门槛和失败处理。当前尚未运行正式黄金集，因此只展示方法和目标值。"
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
        title="正式 Eval 尚未运行"
        description="下面所有数字都标记为目标或测试集计划，不展示参考项目的指标，也不把目标值包装成实测结果。"
      />

      <header class="eval-run-header">
        <div>
          <p class="section-kicker">NO PRODUCTION RUN</p>
          <h2>首版评测方案</h2>
          <p>
            计划策略为 chunk-level dense retrieval，article-level dense retrieval 保留为 fallback。
          </p>
        </div>
        <dl>
          <div>
            <dt>运行状态</dt>
            <dd>尚未运行</dd>
          </div>
          <div>
            <dt>黄金集</dt>
            <dd>计划 30 题</dd>
          </div>
          <div>
            <dt>语料版本</dt>
            <dd>待真实采集</dd>
          </div>
          <div>
            <dt>发布结论</dt>
            <dd>不可发布</dd>
          </div>
        </dl>
      </header>

      <section class="eval-metrics" aria-labelledby="retrieval-metrics-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">RETRIEVAL TARGETS</p>
            <h2 id="retrieval-metrics-title">检索指标与门槛</h2>
            <p>目标值用于定义 Gate，正式结果必须关联 EvalRun、语料版本和代码提交。</p>
          </div>
        </div>
        <div class="metric-grid">
          <article v-for="metric in retrievalTargets" :key="metric.name">
            <span>目标值</span>
            <h3>{{ metric.name }}</h3>
            <strong>{{ metric.target }}</strong>
            <p>{{ metric.meaning }}</p>
          </article>
        </div>
      </section>

      <section class="eval-detail-grid">
        <article>
          <PhFlask :size="24" weight="duotone" aria-hidden="true" />
          <h2>黄金测试集设计</h2>
          <p>
            30 题覆盖事实定位、多来源归纳、时间变化和无答案拒答，避免只评估容易命中的单文章问题。
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
          <p>检索通过后继续评估引用覆盖率、Faithfulness、无答案识别准确率和 p50/p95 延迟。</p>
          <ul>
            <li>引用覆盖率目标 ≥ 90%</li>
            <li>严重编造直接阻止发布</li>
            <li>p95 恶化超过 30% 时保留旧策略</li>
          </ul>
        </article>

        <article>
          <PhCheckSquareOffset :size="24" weight="duotone" aria-hidden="true" />
          <h2>发布与回滚</h2>
          <p>每个检索配置都带版本。新方案只有同时满足质量、延迟和 corpus health 才能切流。</p>
          <ol>
            <li>固定语料与黄金集</li>
            <li>运行候选策略</li>
            <li>比较质量和延迟</li>
            <li>通过 Gate 后发布</li>
          </ol>
        </article>
      </section>

      <section class="eval-failures">
        <div>
          <PhWarningCircle :size="22" aria-hidden="true" />
          <div>
            <h2>失败案例</h2>
            <p>正式 Eval 尚未执行，目前没有可公开的真实失败案例。</p>
          </div>
        </div>
        <p>运行后将展示问题类型、失败原因、检索候选和处理结论，不泄露完整测试语料。</p>
      </section>

      <nav class="page-next-links" aria-label="Eval 后续入口">
        <RouterLink to="/ask">
          <span>体验边界</span><strong>查看情报问答暂停态</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
        <RouterLink to="/product#rag">
          <span>理解方案</span><strong>查看 RAG 技术链路</strong><PhArrowRight :size="17" aria-hidden="true" />
        </RouterLink>
      </nav>
    </section>
  </main>
</template>
