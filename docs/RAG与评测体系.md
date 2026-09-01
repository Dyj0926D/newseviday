# RAG 与评测体系

## 当前实现

NewsEviday 的在线问答链路由六个受限步骤组成：

```text
问题校验 → 问题路由 → 最多两轮检索 → 证据缺口检查 → 上下文组装 → 流式回答和引用
```

Worker 会把问题路由为单事实、对比、时序或范围外请求。显式双主体问题会拆成两个带主题锚点的跨语言子查询，融合时保留每轮首要且不同的来源；证据门禁要求两个子问题都被前五候选覆盖。系统最多执行两轮检索，再检查时间边界、产品范围以及价格、数量等必需证据。任一条件不满足时直接拒答，不调用模型。证据满足要求时，系统只把选中的内容放入受边界标记的证据块，并要求模型使用 `[1]` 形式引用来源。

当前实现可以称为“有限步骤 Agentic RAG（`bounded_v1`）”。它具备路由、有限查询改写、多轮检索、证据充分性判断、提前停止和 Trace，但没有开放式工具调用、自主浏览或无限循环，因此不称为通用研究 Agent。

## Eval Harness

评测管道提供：

- 版本化黄金题数据结构；
- 语料规模、分块覆盖率和缺失文章检查；
- Recall@5、Recall@10、MRR、NDCG@10、Hit@5；
- p50、p95 检索延迟；
- 无答案问题、旧单阈值基线和证据充分性门禁对比；
- `pass`、`fail`、`observe` 质量 Gate；
- 可替换的 Hashing Baseline 和 OpenAI-compatible Embedding 适配层；
- JSON 评测报告，供网页评测页和 CI 使用。
- 生成回答 Eval Harness：缓存受控模型调用，记录 retriever input、ranked candidates、injected context、answer、逐句 citation 和人工标签；
- MultiHop-RAG 公开检索适配器与 RAGBench 回答标签校准适配器，均固定数据 revision 和许可证。

## 当前生产试运行结果

| 字段 | 当前值 |
| --- | --- |
| 数据集 | `rag-gold-trial-v3` |
| 问题数 | 24，其中可回答 12、无答案/越界/安全边界 12 |
| 语料 | 固定生产快照，40 篇文章、69 个分块 |
| 检索器 | `chunk_bm25`；`hashing-chargram-v1` 作为回滚对照 |
| 评测状态 | `human_reviewed` |
| Gate | `fail` |

| 指标 | 结果 |
| --- | ---: |
| Recall@5 | 1.0000 |
| Recall@10 | 1.0000 |
| MRR | 0.9167 |
| NDCG@10 | 0.9385 |
| Hit@5 | 1.0000 |
| 证据门禁无答案识别 | 1.0000 |
| 旧单阈值拒答基线 | 0.2500 |
| 可回答问题通过率 | 1.0000 |
| 平均检索轮次 | 1.21 / 2 |
| 本地 p95 | 60 ms |

v3 的指标按 Agentic 多轮融合后的前五候选计算。2026-08-28 已完成 24 题检索证据与拒答判断签字。2026-09-01 把线上与离线默认检索统一为分块 BM25；同一内部集保持 Recall@5/10 1.0、MRR 0.9167，并消除了原先“线上文章级、离线分块级”的口径错位。生成回答的引用覆盖、引用有效性、忠实度、答案正确性和完整性尚未完成人工 Gate，所以总 Gate 仍为 `fail`。旧单阈值结果继续保留，用来说明为什么不能只调相似度阈值。

## 公开权威基准

[MultiHop-RAG](https://github.com/yixuantt/MultiHop-RAG) 是 COLM 2024 接收的跨文档 RAG 数据集，包含 2,556 道问题；当前固定 [Hugging Face 数据版本](https://huggingface.co/datasets/yixuantt/MultiHopRAG) revision `71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82`。其中 301 道无证据题不参与纯检索指标，其余 2,255 道全量运行结果如下：

| 指标 | BM25 结果 |
| --- | ---: |
| Recall@5 | 0.7394 |
| Recall@10 | 0.8604 |
| Hit@5 | 0.9805 |
| MRR | 0.8418 |
| NDCG@10 | 0.7601 |
| p50 / p95 | 18 / 33 ms |

对照实验中，article-level hashing 在固定 120 题样本上的 Recall@5 仅 0.2681，BM25 为 0.7646；简单 RRF 混合受到弱 dense 路径拖累，Recall@5 为 0.4875。因此 MVP 选择 BM25 主路径并保留 dense 回滚，不把“混合检索”本身当成质量保证。

[RAGBench](https://huggingface.co/datasets/galileo-ai/ragbench) 固定 revision `97808f3e5fd16ede40bbff6c2949af8139b2eb7b`。当前接入其 TechQA test 的逐句支持、回答相关性、证据利用率和完整性字段，用于校准 Eval Harness 数据结构；RAGBench 自带回答与标签不记作 NewsEviday 模型成绩。

## 生成回答发布 Gate

生成回答采用分批缓存：每次最多 5 次 DeepSeek 调用，重复运行复用已生成答案。每个可回答问题记录完整 Trace，并按以下条件发布：

| Gate | 阈值 |
| --- | ---: |
| 事实句引用覆盖率 | ≥ 95% |
| 引用编号有效率 | 100% |
| 人工引用忠实度 | ≥ 90% |
| 人工答案正确率 | ≥ 90% |
| 人工答案完整率 | ≥ 90% |
| 检索 Recall@5 / Hit@5 | ≥ 75% / ≥ 85% |
| p95 | ≤ 4 秒 |

任一答案未生成、任一人工标签未填写、出现无效引用或成本记录不完整时，Gate 保持 `pending/fail`。

## 有限步骤 Agentic RAG 边界

`bounded_v1` 已实现：

1. 问题路由：单事实、对比、时序、信息不足；
2. 最多两个子问题和两轮检索；
3. 证据缺口检查与提前停止；
4. Trace 记录路由、轮次、候选、注入内容 ID、停止原因和耗时，不记录问题原文；
5. 固定步数、Token、时间和成本上限；
6. 评测报告同时保留旧单阈值基线，避免指标口径被替换后失去对照。

在线 Worker 与离线 Harness 已统一为 `chunk_bm25`，`article_dense` 可通过 `RAG_RETRIEVAL_MODE` 一键回滚。当前仍保持总开关关闭；回答人工 Gate 通过后，先进入 Cloudflare Preview 受控验证，再决定是否公开。

## 运行评测

```powershell
python -m uv run --project pipeline newseviday-pipeline eval-rag `
  apps/web/public/data/versions/snapshot-20260805T035314Z-a2c2f64d-ai-07822422.json `
  pipeline/eval/rag-gold-trial-v3.json --retrieval-mode chunk_bm25

python -m uv run --project pipeline newseviday-pipeline eval-rag-answers `
  apps/web/public/data/versions/snapshot-20260805T035314Z-a2c2f64d-ai-07822422.json `
  pipeline/eval/rag-gold-trial-v3.json --retrieval-mode chunk_bm25 `
  --allow-model --max-model-calls 5

python -m uv run --project pipeline newseviday-pipeline eval-public-rag `
  --allow-network --sample-size 0 --retrieval-mode bm25
```
