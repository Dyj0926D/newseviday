# RAG 人工复核清单

## 1. 当前结论

离线 `bounded_v1` Agentic RAG 已具备问题路由、最多两轮检索、双主体查询拆分、来源覆盖检查和拒答。v3 固定 24 题试运行集的 Recall@5 为 1.0、Hit@5 为 1.0、MRR 为 0.9167、NDCG@10 为 0.9385；有限步骤证据门禁的无答案识别为 1.0，旧单阈值基线为 0.25。

2026-08-24 已完成 v2 的 A–C 批次人工复核：q01–q09 通过，q10–q12 暴露三项缺陷，q13–q24 拒答识别 12/12 正确。v3 完成工程修复后，用户于 2026-08-28 确认 q10–q12 全部通过；24 题检索证据与拒答判断已完成签字。回答引用复核尚未开始，因此在线 RAG 继续关闭。

## 2. 复核材料

固定输入：

- 黄金题：`pipeline/eval/rag-gold-trial-v3.json`
- 固定语料：`apps/web/public/data/versions/snapshot-20260805T035314Z-a2c2f64d-ai-07822422.json`
- 本地复核包：`data/runtime/rag/human-review-20260824-v3.json`
- 本地评测报告：`data/runtime/rag/eval-20260824-v3.json`

可重复生成：

```powershell
pipeline\.venv\Scripts\newseviday-pipeline.exe eval-rag `
  apps/web/public/data/versions/snapshot-20260805T035314Z-a2c2f64d-ai-07822422.json `
  pipeline/eval/rag-gold-trial-v3.json `
  --report data/runtime/rag/eval-human-review.json `
  --review-packet data/runtime/rag/human-review.json
```

复核包为每题列出路由、检索轮次、证据充分性判断、前五个候选 Chunk、文章标题、分数和证据摘录，并预留三个空白人工字段。

## 3. 复核顺序

| 批次 | 题目 | 要确认的内容 | 通过标准 |
| --- | --- | --- | --- |
| A | q01–q10 | 单一事实、Agent 工程、AI 安全与 RAG 问题的期望文章是否正确 | 10/10 通过；q10 修订后的证据口径已复核 |
| B | q11–q12 | 多来源归纳是否覆盖了全部必要文章 | 2/2 通过；双主体拆分与两侧来源保留已复核 |
| C | q13–q24 | 越界、未来、价格、医疗、投资和证据缺失问题是否应拒答 | 已复核：12/12 正确拒答，全部安全边界题通过 |
| D | 开放受控回答后 | 回答中的每项事实是否被引用支持 | 引用可打开；引用覆盖率不低于 90%；不得用未注入事实补全答案 |

## 4. 人工字段填写规则

- `retrievalEvidenceCorrect`：前五候选中存在足够且相关的证据时填 `true`；否则填 `false` 并在 `notes` 记录漏召回或误召回。
- `answerabilityDecisionCorrect`：`evidenceSufficient` 与人工判断一致时填 `true`。
- `citationSupportsAnswer`：当前不生成模型答案，先保持 `null`；进入受控回答复核后再填写。
- `notes`：记录黄金题错误、期望文章不完整、路由错误、拒答过严、拒答过松或引用不忠实。

## 5. 上线 Gate

只有以下条件全部满足，才进入小流量在线 RAG 验证：

- 24 题题意和期望文章完成人工复核；
- Recall@5 ≥ 0.75、Hit@5 ≥ 0.85、p95 ≤ 4 秒；
- 无答案识别 ≥ 80%，全部安全边界题正确拒答；
- 回答引用覆盖率 ≥ 90%，抽检中没有无证据关键结论；
- DeepSeek 调用继续受 Turnstile、D1 限额、并发租约和月度预算保护。

当前状态：v3 的24题检索证据与拒答判断已全部通过人工复核，工程回归达到 Recall@5 1.0、Hit@5 1.0。D 生成回答引用复核尚未开始，生产 Gate 保持关闭。
