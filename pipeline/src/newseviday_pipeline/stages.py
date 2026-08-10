import hashlib
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from newseviday_pipeline.extraction import clean_html_text
from newseviday_pipeline.models import (
    Article,
    ArticleFacts,
    ContentScoreBreakdown,
    Evidence,
    KeySignalAssessment,
    RawFeedItem,
    TopicConfig,
)

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

TOPIC_AFFINITY = {
    "data-platform": 1.0,
    "data-agent": 1.0,
    "semantic-layer": 1.0,
    "intelligent-lakehouse": 0.95,
    "metadata-governance": 0.9,
    "rag-eval": 0.8,
    "ai-products-agents": 0.75,
    "foundation-models": 0.45,
}
PRIMARY_PRODUCT_TOPICS = {
    "data-platform",
    "data-agent",
    "semantic-layer",
    "intelligent-lakehouse",
    "metadata-governance",
}
ARXIV_SOURCE_ID = "arxiv-cs-ai"
DEFAULT_SOURCE_LIMITS = {ARXIV_SOURCE_ID: 6}
ARXIV_MIN_TARGET_RELEVANCE = 0.6
ARXIV_NARROW_DOMAIN_MIN_TARGET_RELEVANCE = 0.65

ADVANCEMENT_PATTERNS = (
    "we introduce",
    "we propose",
    "we present",
    "new architecture",
    "new benchmark",
    "state-of-the-art",
    "state of the art",
    "novel method",
    "首次",
    "提出",
)
COMPARISON_PATTERNS = (
    "outperform",
    "surpass",
    "improv",
    "reduc",
    "increase",
    "compared with",
    "baseline",
    "提升",
    "降低",
    "超过",
)
BENCHMARK_PATTERNS = (
    "benchmark",
    "evaluation",
    "evaluated",
    "experiment",
    "dataset",
    "test set",
    "评测",
    "数据集",
)
ARTIFACT_PATTERNS = (
    "open source",
    "open-source",
    "github.com",
    "code:",
    "release our",
    "release the code",
    "apache 2.0",
    "开源",
)
ENGINEERING_PATTERNS = (
    "production",
    "deploy",
    "integration",
    "workflow",
    "runtime",
    "api",
    "platform",
    "pipeline",
    "inference",
    "database",
    "工程",
    "部署",
    "工作流",
)
EFFICIENCY_PATTERNS = (
    "latency",
    "throughput",
    "cost",
    "efficient",
    "efficiency",
    "reliability",
    "scalab",
    "token",
    "延迟",
    "成本",
    "可靠",
)
GENERALITY_PATTERNS = (
    "general-purpose",
    "general purpose",
    "multi-domain",
    "multiple domains",
    "across domains",
    "across models",
    "across datasets",
    "across tasks",
    "framework",
    "platform",
    "foundation model",
    "通用",
    "跨领域",
)
PRODUCT_IMPACT_PATTERNS = (
    "product launch",
    "announcing",
    "launch",
    "release",
    "acquisition",
    "pricing",
    "api",
    "enterprise",
    "customer",
    "developer",
    "workflow",
    "security",
    "governance",
    "发布",
    "企业",
    "开发者",
)
NARROW_DOMAIN_PATTERNS = (
    "modern greek",
    "wireless propagation",
    "channel estimation",
    "beam prediction",
    "police language",
    "race and gender",
    "vr simulations",
    "chiplet",
    "quantum circuit",
    "clinical",
    "heart failure",
    "heart-failure",
    "healthcare",
    "medical",
)
QUANTITATIVE_PATTERN = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:%|x|ms|million|billion)|\b\d+(?:\.\d+)?\s*s\b|\d+(?:\.\d+)?\s*倍)",
    re.IGNORECASE,
)
CHINESE_CHARACTER_PATTERN = re.compile(r"[\u3400-\u9fff]")
CHINESE_READINESS_FAILURE = "缺少可展示的中文标题或导读"


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split()).strip()


def canonicalize_url(value: str, *, preserve_fragment: bool = False) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("article_url_must_be_http")
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_QUERY_KEYS
        )
    )
    path = parts.path.rstrip("/") or "/"
    fragment = parts.fragment if preserve_fragment else ""
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, query, fragment))


def normalize_item(
    item: RawFeedItem,
    *,
    collected_at: datetime | None = None,
) -> tuple[Article, Evidence]:
    collected = collected_at or datetime.now(UTC)
    title = normalize_text(item.title)
    extracted = clean_html_text(item.content_html) if item.content_html else ""
    abstract = normalize_text(extracted or item.summary or "")[:2_500] or None
    canonical_url = canonicalize_url(item.url, preserve_fragment=item.preserve_fragment)
    digest_input = f"{title.casefold()}\n{(abstract or '').casefold()}"
    content_hash = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    article_id = f"article-{hashlib.sha256(canonical_url.encode('utf-8')).hexdigest()[:20]}"
    evidence_id = f"evidence-{content_hash[:20]}"
    article = Article(
        id=article_id,
        source_id=item.source_id,
        canonical_url=canonical_url,
        language=item.language,
        published_at=item.published_at,
        collected_at=collected,
        facts=ArticleFacts(
            title=title,
            authors=[normalize_text(author) for author in item.authors if normalize_text(author)],
            abstract=abstract,
        ),
        evidence_ids=[evidence_id],
        content_hash=content_hash,
    )
    evidence = Evidence(
        id=evidence_id,
        article_id=article_id,
        source_id=item.source_id,
        url=canonical_url,
        excerpt=(abstract or title)[:2_000],
        retrieved_at=collected,
    )
    return article, evidence


def exact_deduplicate(articles: list[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    result: list[Article] = []
    for article in articles:
        if article.canonical_url in seen_urls or article.content_hash in seen_hashes:
            continue
        seen_urls.add(article.canonical_url)
        seen_hashes.add(article.content_hash)
        result.append(article)
    return result


def _comparison_text(article: Article) -> str:
    value = f"{article.facts.title} {(article.facts.abstract or '')[:500]}".casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def _trigrams(value: str) -> set[str]:
    if len(value) < 3:
        return {value} if value else set()
    return {value[index : index + 3] for index in range(len(value) - 2)}


def fuzzy_similarity(left: Article, right: Article) -> float:
    return SequenceMatcher(
        None,
        _comparison_text(left),
        _comparison_text(right),
        autojunk=False,
    ).ratio()


def fuzzy_deduplicate(
    articles: list[Article],
    *,
    similarity_threshold: float = 0.92,
    max_batch_size: int = 500,
) -> list[Article]:
    if len(articles) > max_batch_size:
        raise ValueError(f"fuzzy_dedup_batch_exceeds_{max_batch_size}")
    accepted: list[Article] = []
    accepted_text: list[str] = []
    accepted_trigrams: list[set[str]] = []
    trigram_index: dict[str, set[int]] = {}
    for article in articles:
        candidate = _comparison_text(article)
        candidate_trigrams = _trigrams(candidate)
        possible_matches: set[int] = set()
        for trigram in candidate_trigrams:
            possible_matches.update(trigram_index.get(trigram, set()))
        if len(candidate) < 3:
            possible_matches.update(range(len(accepted_text)))
        plausible_matches = (
            index
            for index in possible_matches
            if len(candidate_trigrams & accepted_trigrams[index])
            / max(1, min(len(candidate_trigrams), len(accepted_trigrams[index])))
            >= 0.45
        )
        duplicate = any(
            SequenceMatcher(None, candidate, accepted_text[index], autojunk=False).ratio()
            >= similarity_threshold
            for index in plausible_matches
        )
        if not duplicate:
            accepted_index = len(accepted)
            accepted.append(article)
            accepted_text.append(candidate)
            accepted_trigrams.append(candidate_trigrams)
            for trigram in candidate_trigrams:
                trigram_index.setdefault(trigram, set()).add(accepted_index)
    return accepted


def select_by_topics(
    articles: list[Article],
    topics: list[TopicConfig],
    *,
    minimum_score: float = 0.1,
) -> list[Article]:
    selected: list[Article] = []
    for article in articles:
        haystack = f"{article.facts.title}\n{article.facts.abstract or ''}".casefold()
        scores: dict[str, float] = {}
        for topic in topics:
            matches = sum(1 for keyword in topic.keywords if keyword.casefold() in haystack)
            if matches:
                scores[topic.id] = round(topic.weight * min(1.0, matches / 2), 4)
        article.topic_scores = scores
        if not topics or max(scores.values(), default=0) >= minimum_score:
            selected.append(article)
    return selected


def apply_content_quotas(
    articles: list[Article],
    *,
    max_total: int = 40,
    max_per_source: int = 8,
    source_limits: dict[str, int] | None = None,
) -> list[Article]:
    if max_total < 1 or max_per_source < 1:
        raise ValueError("content_quotas_must_be_positive")
    effective_source_limits = {**DEFAULT_SOURCE_LIMITS, **(source_limits or {})}
    if any(limit < 1 for limit in effective_source_limits.values()):
        raise ValueError("source_limits_must_be_positive")
    anchor = max(
        (article.published_at or article.collected_at for article in articles),
        default=datetime.now(UTC),
    )
    eligible: list[Article] = []
    for article in articles:
        apply_article_scoring(article, anchor=anchor)
        if article.source_id == ARXIV_SOURCE_ID and article.content_score_breakdown is not None:
            minimum_relevance = (
                ARXIV_NARROW_DOMAIN_MIN_TARGET_RELEVANCE
                if _contains_any(_article_text(article), NARROW_DOMAIN_PATTERNS)
                else ARXIV_MIN_TARGET_RELEVANCE
            )
            if article.content_score_breakdown.target_relevance < minimum_relevance:
                continue
        eligible.append(article)
    ranked = sorted(
        eligible,
        key=lambda article: (
            article.content_score or 0.0,
            article.published_at or article.collected_at,
        ),
        reverse=True,
    )
    counts: dict[str, int] = {}
    result: list[Article] = []
    for article in ranked:
        if len(result) >= max_total:
            break
        source_limit = effective_source_limits.get(article.source_id, max_per_source)
        if counts.get(article.source_id, 0) >= source_limit:
            continue
        result.append(article)
        counts[article.source_id] = counts.get(article.source_id, 0) + 1
    return result


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _bounded(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 4)


def _article_text(article: Article) -> str:
    return f"{article.facts.title}\n{article.facts.abstract or ''}".casefold()


def _contains_chinese(value: str | None) -> bool:
    return bool(value and CHINESE_CHARACTER_PATTERN.search(value))


def chinese_display_ready(article: Article) -> bool:
    """Return whether the feed can show a Chinese title and digest without another call."""

    if (
        article.ai is not None
        and _contains_chinese(article.ai.title_zh)
        and _contains_chinese(article.ai.summary_zh)
    ):
        return True
    if article.language.casefold().startswith("zh"):
        return _contains_chinese(article.facts.title) and _contains_chinese(article.facts.abstract)
    return False


def content_score_breakdown(
    article: Article,
    *,
    anchor: datetime,
) -> ContentScoreBreakdown:
    """Calculate source-aware editorial signals without model calls.

    The score treats a complete paper abstract as expected structure, not proof
    of broad value. Technical advancement, engineering applicability and
    generality together contribute 25% of the final score.
    """

    text = _article_text(article)
    topic_values = [
        min(1.0, score) * TOPIC_AFFINITY.get(topic_id, 0.35)
        for topic_id, score in article.topic_scores.items()
    ]
    target_relevance = max(topic_values, default=0.0)
    target_relevance += min(0.08, max(0, len(topic_values) - 1) * 0.03)
    has_primary_product_topic = bool(PRIMARY_PRODUCT_TOPICS.intersection(article.topic_scores))
    narrow_domain = _contains_any(text, NARROW_DOMAIN_PATTERNS)
    if narrow_domain:
        target_relevance = min(target_relevance, 0.45)

    quantitative = bool(QUANTITATIVE_PATTERN.search(text))
    technical_advancement = 0.12
    technical_advancement += 0.23 if _contains_any(text, ADVANCEMENT_PATTERNS) else 0.0
    technical_advancement += 0.22 if quantitative else 0.0
    technical_advancement += 0.18 if _contains_any(text, COMPARISON_PATTERNS) else 0.0
    technical_advancement += 0.15 if _contains_any(text, BENCHMARK_PATTERNS) else 0.0
    technical_advancement += 0.1 if _contains_any(text, ARTIFACT_PATTERNS) else 0.0

    engineering_applicability = 0.08
    engineering_applicability += 0.3 if _contains_any(text, ENGINEERING_PATTERNS) else 0.0
    engineering_applicability += 0.22 if _contains_any(text, EFFICIENCY_PATTERNS) else 0.0
    engineering_applicability += 0.18 if _contains_any(text, ARTIFACT_PATTERNS) else 0.0
    engineering_applicability += 0.14 if _contains_any(text, PRODUCT_IMPACT_PATTERNS) else 0.0
    if narrow_domain and not has_primary_product_topic:
        engineering_applicability = min(engineering_applicability, 0.4)

    technical_generality = 0.18
    technical_generality += 0.35 if _contains_any(text, GENERALITY_PATTERNS) else 0.0
    technical_generality += 0.15 if _contains_any(text, ARTIFACT_PATTERNS) else 0.0
    technical_generality += 0.12 if len(article.topic_scores) >= 2 else 0.0
    if narrow_domain:
        technical_generality *= 0.45

    official_product_source = article.source_id != ARXIV_SOURCE_ID
    product_industry_impact = 0.22 if official_product_source else 0.05
    product_industry_impact += 0.33 if _contains_any(text, PRODUCT_IMPACT_PATTERNS) else 0.0
    product_industry_impact += 0.16 if _contains_any(text, ENGINEERING_PATTERNS) else 0.0
    product_industry_impact += 0.14 if quantitative else 0.0
    if narrow_domain:
        product_industry_impact = min(product_industry_impact, 0.35)

    published = article.published_at or article.collected_at
    age_hours = max(0.0, (anchor - published).total_seconds() / 3_600)
    freshness = max(0.0, 1.0 - age_hours / (24 * 7))

    abstract_length = len(article.facts.abstract or "")
    completeness = (
        1.0
        if abstract_length >= 240
        else 0.65
        if abstract_length >= 120
        else 0.35
        if abstract_length > 0
        else 0.0
    )

    evidence_maturity = 0.35 if article.source_id == ARXIV_SOURCE_ID else 0.5
    evidence_maturity += 0.18 if quantitative else 0.0
    evidence_maturity += 0.16 if _contains_any(text, BENCHMARK_PATTERNS) else 0.0
    evidence_maturity += 0.14 if _contains_any(text, ARTIFACT_PATTERNS) else 0.0
    evidence_maturity += 0.07 if abstract_length >= 500 else 0.0
    if abstract_length < 120:
        evidence_maturity = min(evidence_maturity, 0.3)

    return ContentScoreBreakdown(
        target_relevance=_bounded(target_relevance),
        technical_advancement=_bounded(technical_advancement),
        engineering_applicability=_bounded(engineering_applicability),
        technical_generality=_bounded(technical_generality),
        product_industry_impact=_bounded(product_industry_impact),
        freshness=_bounded(freshness),
        evidence_maturity=_bounded(evidence_maturity),
        completeness=_bounded(completeness),
    )


def content_value_score(article: Article, *, anchor: datetime) -> float:
    values = content_score_breakdown(article, anchor=anchor)
    return round(
        0.30 * values.target_relevance
        + 0.10 * values.technical_advancement
        + 0.08 * values.engineering_applicability
        + 0.07 * values.technical_generality
        + 0.15 * values.product_industry_impact
        + 0.15 * values.freshness
        + 0.10 * values.evidence_maturity
        + 0.05 * values.completeness,
        4,
    )


def content_selection_reasons(article: Article, *, anchor: datetime) -> list[str]:
    """Expose the strongest observable ranking signals."""

    values = content_score_breakdown(article, anchor=anchor)
    reasons: list[str] = []
    if values.target_relevance >= 0.7:
        reasons.append("目标主题高度相关")
    elif values.target_relevance >= 0.45:
        reasons.append("目标主题相关")
    if values.technical_advancement >= 0.7:
        reasons.append("技术改进信号明确")
    if values.engineering_applicability >= 0.65:
        reasons.append("具备工程落地价值")
    if values.technical_generality >= 0.65:
        reasons.append("适用范围较广")
    if values.product_industry_impact >= 0.65:
        reasons.append("产品或行业影响较高")
    if values.freshness >= 0.85:
        reasons.append("24 小时内发布")
    elif values.freshness >= 0.55:
        reasons.append("近期发布")
    if values.evidence_maturity >= 0.7:
        reasons.append("证据与对照较充分")
    elif values.completeness == 0:
        reasons.append("仅保留来源标题")
    return reasons[:5]


def key_signal_assessment(article: Article) -> KeySignalAssessment:
    values = article.content_score_breakdown
    if values is None:
        raise ValueError("content_score_breakdown_required")

    user_value = _bounded(
        0.5 * values.target_relevance
        + 0.3 * values.engineering_applicability
        + 0.2 * values.product_industry_impact
    )
    change_magnitude = _bounded(
        0.6 * values.technical_advancement + 0.4 * values.product_industry_impact
    )
    actionability = _bounded(
        0.6 * values.engineering_applicability + 0.4 * values.product_industry_impact
    )
    score = round(
        0.30 * user_value
        + 0.25 * change_magnitude
        + 0.20 * actionability
        + 0.15 * values.technical_generality
        + 0.10 * values.freshness,
        4,
    )

    gate_failures: list[str] = []
    if not chinese_display_ready(article):
        gate_failures.append(CHINESE_READINESS_FAILURE)
    if (article.content_score or 0.0) < 0.75:
        gate_failures.append("内容总分低于 75")
    if values.target_relevance < 0.65:
        gate_failures.append("目标用户相关性低于 65")
    if max(values.engineering_applicability, values.product_industry_impact) < 0.7:
        gate_failures.append("工程价值与行业影响均低于 70")
    if values.evidence_maturity < 0.5 or len((article.facts.abstract or "").strip()) < 120:
        gate_failures.append("证据成熟度不足")
    if score < 0.72:
        gate_failures.append("Key Signal 专用得分低于 72")

    reasons: list[str] = []
    if user_value >= 0.7:
        reasons.append("目标用户价值较高")
    if change_magnitude >= 0.7:
        reasons.append("变化幅度较大")
    if actionability >= 0.65:
        reasons.append("具备可行动性")
    if values.technical_generality >= 0.65:
        reasons.append("技术普适性较强")
    if values.freshness >= 0.85:
        reasons.append("24 小时内发布")

    return KeySignalAssessment(
        eligible=not gate_failures,
        score=score,
        user_value=user_value,
        change_magnitude=change_magnitude,
        actionability=actionability,
        generality=values.technical_generality,
        freshness=values.freshness,
        reasons=reasons[:5],
        gate_failures=gate_failures[:8],
    )


def key_signal_waiting_for_chinese(article: Article) -> bool:
    """Return whether Chinese presentation is the candidate's only Key Signal blocker."""

    assessment = article.key_signal or key_signal_assessment(article)
    return assessment.gate_failures == [CHINESE_READINESS_FAILURE]


def apply_article_scoring(article: Article, *, anchor: datetime) -> Article:
    article.content_score_breakdown = content_score_breakdown(article, anchor=anchor)
    article.content_score = content_value_score(article, anchor=anchor)
    article.selection_reasons = content_selection_reasons(article, anchor=anchor)
    article.key_signal = key_signal_assessment(article)
    return article
