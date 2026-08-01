# NewsEviday Python Pipeline

该目录承载确定性内容管道。首版由 Python 负责配置校验、采集、清洗、去重、规则筛选、快照和 Eval，模型调用位于独立阶段并受开关控制。

当前只提供工程骨架和 `doctor` 检查，不会自动采集或调用大模型。

```powershell
python -m uv sync --project pipeline
python -m uv run --project pipeline newseviday-pipeline doctor
python -m uv run --project pipeline newseviday-pipeline run --dry-run
```
