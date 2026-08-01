# NewsEviday Python Pipeline

Python 负责可复现、低成本的内容处理：Feed 解析、规范化、精确去重、模糊去重、主题筛选和快照发布。AI 不在这条默认路径中，避免把可确定的问题交给付费模型。

## 命令

```powershell
python -m uv sync --project pipeline --frozen
python -m uv run --project pipeline newseviday-pipeline doctor
python -m uv run --project pipeline newseviday-pipeline run --dry-run
```

离线 fixture 闭环：

```powershell
python -m uv run --project pipeline newseviday-pipeline run `
  --fixture pipeline/tests/fixtures/arxiv-feed.xml `
  --output data/local-preview `
  --source-id arxiv-cs-ai `
  --language en

python -m uv run --project pipeline newseviday-pipeline validate-snapshot `
  data/local-preview/current.json
```

没有 `--fixture` 或 `--dry-run` 时命令拒绝执行。当前没有开放网络采集，也不会调用大模型。

## 去重策略

1. URL 统一 scheme/host、去 fragment 和常见跟踪参数；
2. 规范化标题与摘要生成 SHA-256；
3. URL/Hash 精确去重；
4. 字符三元组倒排生成相似候选；
5. `SequenceMatcher` 做最终模糊判断；
6. 每批最多 500 条，超过即失败。

后续用标注集评估重复识别的 precision/recall。Embedding 只在规则方案不足时加入候选召回，不直接替换可解释规则。

## 快照安全

发布前先由 Pydantic 校验。版本文件不可变，`current.json` 通过同目录临时文件原子替换。校验失败不会覆盖已有快照。
