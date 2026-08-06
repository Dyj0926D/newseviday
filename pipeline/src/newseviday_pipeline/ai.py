import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel

from newseviday_pipeline.ai_models import ArticleEnrichment, ProfileEnhancement
from newseviday_pipeline.models import Article, ContentSnapshot, GeneratedText, TopicConfig
from newseviday_pipeline.stages import key_signal_assessment
from newseviday_pipeline.terminology import TerminologyConfig

PROMPT_VERSION = "article-enrichment-v3"
PROFILE_PROMPT_VERSION = "profile-enhancement-v1"
MIN_ENRICHMENT_EVIDENCE_CHARS = 120
SchemaModel = TypeVar("SchemaModel", bound=BaseModel)


class StructuredCompletionClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete_json(self, *, system: str, user: str) -> Mapping[str, Any]: ...


def _json_object(value: str) -> Mapping[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.IGNORECASE)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("model_output_must_be_json_object")
    return payload


class DeepSeekStructuredClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: int = 30,
        thinking_enabled: bool = False,
    ) -> None:
        if not api_key or not model:
            raise ValueError("deepseek_configuration_incomplete")
        if not base_url.startswith("https://"):
            raise ValueError("deepseek_base_url_must_be_https")
        self.api_key = api_key
        self._model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.thinking_enabled = thinking_enabled

    @property
    def model(self) -> str:
        return self._model

    def complete_json(self, *, system: str, user: str) -> Mapping[str, Any]:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "thinking": {"type": "enabled" if self.thinking_enabled else "disabled"},
                "response_format": {"type": "json_object"},
                **({} if self.thinking_enabled else {"temperature": 0.1}),
                "max_tokens": 1_200,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("invalid_deepseek_completion") from error
        return _json_object(str(content))

    @classmethod
    def from_environment(cls) -> "DeepSeekStructuredClient":
        return cls(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            model=os.environ.get("DEEPSEEK_MODEL", ""),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            thinking_enabled=os.environ.get("DEEPSEEK_THINKING_ENABLED", "false").lower()
            == "true",
        )


class FileAiCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str, schema: type[SchemaModel]) -> SchemaModel | None:
        path = self._path(key)
        if not path.exists():
            return None
        return schema.model_validate_json(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: BaseModel) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            value.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            indent=2,
        )
        handle, name = tempfile.mkstemp(dir=self.directory, prefix="ai-", suffix=".tmp")
        temporary = Path(name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content + "\n")
            temporary.replace(self._path(key))
        finally:
            temporary.unlink(missing_ok=True)


def _cache_key(content_hash: str, model: str, prompt_version: str) -> str:
    value = f"{content_hash}:{model}:{prompt_version}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _terminology_instruction(evidence: str, config: TerminologyConfig | None) -> str:
    if config is None:
        return ""
    source_text = evidence.casefold()
    relevant = [rule for rule in config.terms if rule.source.casefold() in source_text]
    if not relevant:
        return ""
    mappings = "\n".join(
        f"- {rule.source} -> {rule.preferred_zh}" for rule in relevant
    )
    return (
        "\n术语规范：原文已经出现下列术语。titleZh 或 summaryZh 必须保留该概念，"
        "并使用指定中文写法：\n"
        f"{mappings}\n"
    )


def _source_diverse_order(articles: list[Article]) -> list[Article]:
    groups: dict[str, list[Article]] = {}
    for article in articles:
        groups.setdefault(article.source_id, []).append(article)
    topic_counts: dict[str, int] = {}
    for article in articles:
        for topic_id in article.topic_scores:
            topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1

    def priority(article: Article) -> float:
        if article.content_score is None:
            return 0.0
        underrepresented_bonus = max(
            (1 / max(1, topic_counts.get(topic_id, 1)) for topic_id in article.topic_scores),
            default=0.0,
        )
        cross_language_bonus = 0.08 if article.language.casefold().startswith("en") else 0.0
        return article.content_score + 0.12 * underrepresented_bonus + cross_language_bonus

    for group in groups.values():
        group.sort(key=priority, reverse=True)
    maximum = max((len(group) for group in groups.values()), default=0)
    return [
        group[index]
        for index in range(maximum)
        for group in groups.values()
        if index < len(group)
    ]


def enrich_snapshot(
    snapshot: ContentSnapshot,
    *,
    client: StructuredCompletionClient,
    cache: FileAiCache,
    topics: list[TopicConfig],
    terminology: TerminologyConfig | None = None,
    max_model_calls: int = 5,
    now: datetime | None = None,
) -> tuple[ContentSnapshot, int]:
    if not 0 <= max_model_calls <= 10:
        raise ValueError("max_model_calls_must_be_between_0_and_10")
    generated_at = now or datetime.now(UTC)
    result = snapshot.model_copy(deep=True)
    model_calls = 0
    allowed_topics = {topic.id for topic in topics}
    topic_description = ", ".join(f"{topic.id}={topic.label}" for topic in topics)
    for article in _source_diverse_order(result.articles):
        evidence = article.facts.abstract or article.facts.title
        if len(evidence.strip()) < MIN_ENRICHMENT_EVIDENCE_CHARS:
            continue
        terminology_instruction = _terminology_instruction(evidence, terminology)
        terminology_signature = hashlib.sha256(
            terminology_instruction.encode("utf-8")
        ).hexdigest()[:12]
        key = _cache_key(
            article.content_hash,
            client.model,
            f"{PROMPT_VERSION}:{terminology_signature}",
        )
        enrichment = cache.get(key, ArticleEnrichment)
        if enrichment is None:
            if model_calls >= max_model_calls:
                continue
            payload = client.complete_json(
                system=(
                    "你是 NewsEviday 的结构化情报编辑。只根据给定资料输出 JSON。"
                    "不得补充资料外的发布日期、数字、客户或因果结论。"
                ),
                user=(
                    f"允许的 topicIds：{topic_description}\n"
                    f"原始语言：{article.language}\n原始标题：{article.facts.title}\n"
                    "<untrusted-evidence>\n"
                    f"{evidence[:8_000]}\n"
                    "</untrusted-evidence>\n"
                    f"{terminology_instruction}"
                    "输出 titleZh、summaryZh、whyItMatters、keyPoints、topicIds。"
                    "summaryZh 控制在 120–220 个中文字符，提炼主要变化，避免复述整段摘要；"
                    "whyItMatters 控制在 40–100 个中文字符；"
                    "keyPoints 输出 2–4 条，每条不超过 40 个中文字符。"
                ),
            )
            enrichment = ArticleEnrichment.model_validate(payload)
            cache.put(key, enrichment)
            model_calls += 1
        article.ai = GeneratedText(
            title_zh=enrichment.title_zh,
            summary_zh=enrichment.summary_zh,
            why_it_matters=enrichment.why_it_matters,
            key_points=enrichment.key_points,
            model=client.model,
            prompt_version=PROMPT_VERSION,
            generated_at=generated_at,
        )
        article.topic_scores.update(
            {topic_id: 1.0 for topic_id in enrichment.topic_ids if topic_id in allowed_topics}
        )
    suffix = hashlib.sha256(
        f"{snapshot.snapshot_id}:{client.model}:{PROMPT_VERSION}".encode()
    ).hexdigest()[:8]
    for article in result.articles:
        if article.content_score_breakdown is not None:
            article.key_signal = key_signal_assessment(article)
    result.snapshot_id = f"{snapshot.snapshot_id}-ai-{suffix}"
    result.generated_at = generated_at
    return result, model_calls


def enhance_profile(
    value: Mapping[str, str],
    *,
    client: StructuredCompletionClient,
    topics: list[TopicConfig],
) -> ProfileEnhancement:
    safe_input = {key: str(item)[:500] for key, item in value.items()}
    allowed = ", ".join(f"{topic.id}={topic.label}" for topic in topics)
    payload = client.complete_json(
        system=(
            "你只负责整理用户主动输入的职业与兴趣，不推断年龄、性别、公司、地点、健康、"
            "政治或其他敏感属性。只输出 JSON。"
        ),
        user=(
            f"可选主题：{allowed}\n用户输入：{json.dumps(safe_input, ensure_ascii=False)}\n"
            "输出 role、work、goal、description、interests、inferredTerms、warnings。"
        ),
    )
    result = ProfileEnhancement.model_validate(payload)
    allowed_ids = {topic.id for topic in topics}
    result.interests = [item for item in result.interests if item.topic_id in allowed_ids]
    return result
