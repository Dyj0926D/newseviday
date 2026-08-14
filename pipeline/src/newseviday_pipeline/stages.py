import hashlib
import re
from dataclasses import dataclass
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
PRODUCT_IMPACT_SOURCE_BASE = {
    "official": 0.22,
    "academic": 0.05,
    "research_institute": 0.12,
    "professional_media": 0.12,
    "independent_author": 0.08,
}
EVIDENCE_MATURITY_SOURCE_BASE = {
    "official": 0.50,
    "academic": 0.35,
    "research_institute": 0.45,
    "professional_media": 0.35,
    "independent_author": 0.25,
}
KEY_SIGNAL_CORROBORATION_REQUIRED_SOURCE_TYPES = {
    "professional_media",
    "independent_author",
}

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
POLICY_SUBJECT_PATTERNS = (
    "regulation",
    "regulator",
    "legislation",
    "law",
    "policy",
    "executive order",
    "standard",
    "compliance",
    "监管",
    "法规",
    "法案",
    "政策",
    "行政命令",
    "标准",
    "合规",
)
POLICY_ACTION_PATTERNS = (
    "takes effect",
    "effective on",
    "adopted",
    "approved",
    "issued",
    "signed",
    "requires",
    "prohibits",
    "enforcement",
    "compliance deadline",
    "生效",
    "出台",
    "实施",
    "通过",
    "发布",
    "禁止",
    "要求",
    "执法",
    "合规期限",
)
PRODUCT_RELEASE_PATTERNS = (
    "generally available",
    "general availability",
    "ga release",
    "rolled out",
    "now available",
    "official release",
    "launches",
    "launched",
    "introducing",
    "debut",
    "正式发布",
    "正式上线",
    "全面开放",
    "推出",
    "上线",
)
PRODUCT_SUBJECT_PATTERNS = (
    "model",
    "api",
    "product",
    "platform",
    "service",
    "feature",
    "agent",
    "app",
    "sdk",
    "tool",
    "模型",
    "接口",
    "产品",
    "平台",
    "服务",
    "功能",
    "智能体",
    "应用",
)
MAJOR_PRODUCT_SUBJECT_PATTERNS = (
    "model",
    "api",
    "product",
    "platform",
    "service",
    "agent",
    "模型",
    "接口",
    "产品",
    "平台",
    "服务",
    "智能体",
)
CAPABILITY_UPDATE_PATTERNS = (
    "update",
    "upgrade",
    "enhanced",
    "enhancement",
    "native support",
    "new capability",
    "breaking change",
    "deprecat",
    "pricing adjustment",
    "price change",
    "更新",
    "升级",
    "增强",
    "原生支持",
    "新增能力",
    "不兼容变更",
    "弃用",
    "价格调整",
)
BROAD_AVAILABILITY_PATTERNS = (
    "app, web, and api",
    "app, web and api",
    "all users",
    "all customers",
    "developers",
    "enterprise",
    "production environments",
    "open source",
    "open-source",
    "open weights",
    "全量用户",
    "所有用户",
    "开发者",
    "企业",
    "生产环境",
    "开源",
)
DECISION_CHANGE_PATTERNS = (
    "pricing",
    "price",
    "api",
    "breaking change",
    "deprecat",
    "migration",
    "compatibility",
    "effective on",
    "takes effect",
    "compliance",
    "定价",
    "价格",
    "接口",
    "不兼容",
    "弃用",
    "迁移",
    "兼容",
    "生效",
    "合规",
)
ADOPTION_PATTERNS = (
    "adoption",
    "adopted by",
    "active users",
    "paying users",
    "customers use",
    "downloads",
    "deployments",
    "usage grew",
    "usage growth",
    "market share",
    "widely used",
    "普及",
    "采用率",
    "活跃用户",
    "付费用户",
    "客户采用",
    "下载量",
    "部署量",
    "使用量增长",
    "市场份额",
    "广泛使用",
)
ADOPTION_SCALE_PATTERNS = (
    "million users",
    "billion users",
    "thousand customers",
    "millions of",
    "widely used",
    "百万用户",
    "千万用户",
    "亿用户",
    "数千客户",
    "广泛使用",
)
MARKET_STRUCTURE_PATTERNS = (
    "acquisition",
    "acquires",
    "acquired",
    "merger",
    "funding round",
    "investment",
    "strategic partnership",
    "收购",
    "并购",
    "合并",
    "融资",
    "投资",
    "战略合作",
)
RISK_INCIDENT_PATTERNS = (
    "security incident",
    "data breach",
    "vulnerability",
    "critical outage",
    "service outage",
    "recall",
    "regulatory investigation",
    "sanction",
    "安全事件",
    "数据泄露",
    "漏洞",
    "严重故障",
    "服务中断",
    "召回",
    "监管调查",
    "制裁",
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

EVENT_TYPE_POLICY = "policy_regulation"
EVENT_TYPE_PRODUCT_LAUNCH = "product_launch"
EVENT_TYPE_CAPABILITY_UPDATE = "capability_update"
EVENT_TYPE_ADOPTION = "adoption_momentum"
EVENT_TYPE_TECH_BREAKTHROUGH = "technical_breakthrough"
EVENT_TYPE_MARKET_STRUCTURE = "market_structure"
EVENT_TYPE_RISK = "security_risk"
EVENT_REASON_LABELS = {
    EVENT_TYPE_POLICY: "监管或政策规则发生实质变化",
    EVENT_TYPE_PRODUCT_LAUNCH: "新产品或服务进入正式可用阶段",
    EVENT_TYPE_CAPABILITY_UPDATE: "核心能力、接口或成本条件发生变化",
    EVENT_TYPE_ADOPTION: "采用与扩散达到显著规模",
    EVENT_TYPE_TECH_BREAKTHROUGH: "技术突破具有对照或量化证据",
    EVENT_TYPE_MARKET_STRUCTURE: "市场结构或关键合作关系发生变化",
    EVENT_TYPE_RISK: "风险事件可能影响产品或技术决策",
}


@dataclass(frozen=True)
class EventSignalProfile:
    event_types: tuple[str, ...]
    significance: float
    decision_impact: float
    adoption_momentum: float


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
        source_type=item.source_type,
        evidence_tier=item.evidence_tier,
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
    # Freshness is relative to this collection run, not to the newest article
    # returned by the sources. Otherwise a stale feed can make its newest item
    # look as if it was published in the last 24 hours.
    anchor = max(
        (article.collected_at for article in articles),
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


def _effective_source_type(article: Article) -> str:
    """Keep pre-migration arXiv fixtures and snapshots source-aware."""

    if article.source_id == ARXIV_SOURCE_ID and article.source_type == "official":
        return "academic"
    return article.source_type


def _contains_non_negated_any(text: str, patterns: tuple[str, ...]) -> bool:
    """Ignore simple local negations so absence statements do not become event evidence."""

    negation = re.compile(
        r"(?:\bno\b|\bnot\b|\bwithout\b|\blacks?\b|\bdoes not\b|\bdid not\b|未|没有|缺少)"
        r"[^.!?。！？]{0,120}$",
        re.IGNORECASE,
    )
    for pattern in patterns:
        for match in re.finditer(re.escape(pattern), text, re.IGNORECASE):
            prefix = text[max(0, match.start() - 144) : match.start()]
            if not negation.search(prefix):
                return True
    return False


def _event_signal_profile(article: Article, text: str) -> EventSignalProfile:
    """Detect decision-relevant change events without relying on one named product.

    Event magnitude is deliberately separated from profile affinity. A binding policy,
    broad product launch, demonstrated adoption shift, or material incident can therefore
    surface even when it is not a close lexical match for the user's preferred topics.
    """

    source_type = _effective_source_type(article)
    primary_source = article.evidence_tier == "primary"
    authoritative = source_type in {"official", "research_institute"} and primary_source
    research_backed = source_type in {"academic", "research_institute"} and primary_source
    quantitative = bool(QUANTITATIVE_PATTERN.search(text))
    has_benchmark = _contains_non_negated_any(text, BENCHMARK_PATTERNS)
    has_comparison = _contains_non_negated_any(text, COMPARISON_PATTERNS)
    has_artifact = _contains_non_negated_any(text, ARTIFACT_PATTERNS)
    has_broad_availability = _contains_non_negated_any(text, BROAD_AVAILABILITY_PATTERNS)
    has_decision_change = _contains_non_negated_any(text, DECISION_CHANGE_PATTERNS)
    has_major_product_subject = _contains_non_negated_any(
        text, MAJOR_PRODUCT_SUBJECT_PATTERNS
    )

    event_scores: dict[str, float] = {}
    decision_scores: list[float] = []
    adoption_momentum = 0.0

    if _contains_non_negated_any(text, POLICY_SUBJECT_PATTERNS) and _contains_non_negated_any(
        text, POLICY_ACTION_PATTERNS
    ):
        event_scores[EVENT_TYPE_POLICY] = (
            0.70 + (0.14 if authoritative else 0.0) + (0.08 if has_decision_change else 0.0)
        )
        decision_scores.append(0.82 + (0.10 if has_decision_change else 0.0))

    if _contains_non_negated_any(text, PRODUCT_RELEASE_PATTERNS) and _contains_non_negated_any(
        text, PRODUCT_SUBJECT_PATTERNS
    ):
        event_scores[EVENT_TYPE_PRODUCT_LAUNCH] = (
            0.60
            + (0.10 if authoritative else 0.0)
            + (0.12 if has_major_product_subject else 0.0)
            + (0.08 if has_broad_availability else 0.0)
            + (0.06 if quantitative or has_benchmark else 0.0)
        )
        decision_scores.append(
            0.56
            + (0.12 if has_major_product_subject else 0.0)
            + (0.10 if has_decision_change else 0.0)
            + (0.08 if has_broad_availability else 0.0)
        )

    if _contains_non_negated_any(text, CAPABILITY_UPDATE_PATTERNS) and _contains_non_negated_any(
        text, PRODUCT_SUBJECT_PATTERNS
    ):
        event_scores[EVENT_TYPE_CAPABILITY_UPDATE] = (
            0.52
            + (0.12 if authoritative else 0.0)
            + (0.10 if has_decision_change else 0.0)
            + (0.10 if has_broad_availability else 0.0)
            + (0.08 if quantitative or has_benchmark else 0.0)
        )
        decision_scores.append(
            0.52
            + (0.16 if has_decision_change else 0.0)
            + (0.10 if has_broad_availability else 0.0)
        )

    has_adoption_signal = _contains_non_negated_any(text, ADOPTION_PATTERNS)
    has_adoption_scale = quantitative or _contains_non_negated_any(
        text, ADOPTION_SCALE_PATTERNS
    )
    if has_adoption_signal and has_adoption_scale:
        adoption_momentum = (
            0.66
            + (0.12 if quantitative else 0.0)
            + (0.10 if authoritative or research_backed else 0.0)
            + (0.08 if _contains_non_negated_any(text, ADOPTION_SCALE_PATTERNS) else 0.0)
        )
        event_scores[EVENT_TYPE_ADOPTION] = 0.62 + 0.25 * adoption_momentum
        decision_scores.append(0.58 + 0.22 * adoption_momentum)

    if (
        _contains_non_negated_any(text, ADVANCEMENT_PATTERNS)
        and has_comparison
        and (quantitative or has_benchmark)
    ):
        event_scores[EVENT_TYPE_TECH_BREAKTHROUGH] = (
            0.60
            + (0.10 if research_backed else 0.0)
            + (0.08 if quantitative else 0.0)
            + (0.08 if has_artifact else 0.0)
        )
        decision_scores.append(0.48 + (0.12 if has_artifact else 0.0))

    if _contains_non_negated_any(text, MARKET_STRUCTURE_PATTERNS):
        event_scores[EVENT_TYPE_MARKET_STRUCTURE] = (
            0.64 + (0.12 if authoritative else 0.0) + (0.08 if quantitative else 0.0)
        )
        decision_scores.append(0.68 + (0.08 if quantitative else 0.0))

    if _contains_non_negated_any(text, RISK_INCIDENT_PATTERNS):
        event_scores[EVENT_TYPE_RISK] = (
            0.68
            + (0.10 if authoritative or research_backed else 0.0)
            + (0.08 if quantitative else 0.0)
        )
        decision_scores.append(0.82)

    ordered_types = tuple(
        event_type
        for event_type, _score in sorted(
            event_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    significance = max(event_scores.values(), default=0.0)
    significance += min(0.08, max(0, len(event_scores) - 1) * 0.04)
    return EventSignalProfile(
        event_types=ordered_types[:5],
        significance=_bounded(significance),
        decision_impact=_bounded(max(decision_scores, default=0.0)),
        adoption_momentum=_bounded(adoption_momentum),
    )


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
    of broad value. Event significance and decision impact are independent from
    profile affinity, while technical and engineering signals retain 22% weight.
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
    event_profile = _event_signal_profile(article, text)

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

    source_type = _effective_source_type(article)
    product_industry_impact = PRODUCT_IMPACT_SOURCE_BASE[source_type]
    product_industry_impact += 0.33 if _contains_any(text, PRODUCT_IMPACT_PATTERNS) else 0.0
    product_industry_impact += 0.16 if _contains_any(text, ENGINEERING_PATTERNS) else 0.0
    product_industry_impact += 0.14 if quantitative else 0.0
    product_industry_impact += 0.16 if event_profile.significance >= 0.7 else 0.0
    product_industry_impact += 0.12 * event_profile.adoption_momentum
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

    evidence_maturity = EVIDENCE_MATURITY_SOURCE_BASE[source_type]
    evidence_maturity += 0.18 if quantitative else 0.0
    evidence_maturity += 0.16 if _contains_any(text, BENCHMARK_PATTERNS) else 0.0
    evidence_maturity += 0.14 if _contains_any(text, ARTIFACT_PATTERNS) else 0.0
    evidence_maturity += 0.07 if abstract_length >= 500 else 0.0
    evidence_maturity += (
        0.12
        if event_profile.significance >= 0.7
        and article.evidence_tier == "primary"
        and source_type in {"official", "research_institute", "academic"}
        else 0.0
    )
    if abstract_length < 120:
        evidence_maturity = min(evidence_maturity, 0.3)

    return ContentScoreBreakdown(
        target_relevance=_bounded(target_relevance),
        event_significance=event_profile.significance,
        decision_impact=event_profile.decision_impact,
        adoption_momentum=event_profile.adoption_momentum,
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
        0.20 * values.target_relevance
        + 0.15 * values.event_significance
        + 0.08 * values.decision_impact
        + 0.05 * values.adoption_momentum
        + 0.08 * values.technical_advancement
        + 0.08 * values.engineering_applicability
        + 0.06 * values.technical_generality
        + 0.10 * values.product_industry_impact
        + 0.10 * values.freshness
        + 0.07 * values.evidence_maturity
        + 0.03 * values.completeness,
        4,
    )


def content_selection_reasons(article: Article, *, anchor: datetime) -> list[str]:
    """Expose the strongest observable ranking signals."""

    values = content_score_breakdown(article, anchor=anchor)
    event_profile = _event_signal_profile(article, _article_text(article))
    reasons: list[str] = [
        EVENT_REASON_LABELS[event_type]
        for event_type in event_profile.event_types[:2]
        if event_type in EVENT_REASON_LABELS
    ]
    if values.event_significance >= 0.8:
        reasons.append("重大变化信号明确")
    elif values.event_significance >= 0.7:
        reasons.append("变化事件较为显著")
    if values.decision_impact >= 0.75:
        reasons.append("可能影响产品或技术决策")
    if values.adoption_momentum >= 0.7:
        reasons.append("采用与扩散证据较强")
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

    event_profile = _event_signal_profile(article, _article_text(article))
    user_value = _bounded(
        0.25 * values.target_relevance
        + 0.20 * values.engineering_applicability
        + 0.30 * values.decision_impact
        + 0.25 * values.product_industry_impact
    )
    change_magnitude = _bounded(
        0.65 * values.event_significance
        + 0.20 * values.technical_advancement
        + 0.15 * values.adoption_momentum
    )
    actionability = _bounded(
        0.50 * values.decision_impact
        + 0.25 * values.engineering_applicability
        + 0.25 * values.product_industry_impact
    )
    score = round(
        0.20 * user_value
        + 0.30 * change_magnitude
        + 0.20 * actionability
        + 0.10 * values.technical_generality
        + 0.10 * values.freshness
        + 0.10 * values.evidence_maturity,
        4,
    )

    gate_failures: list[str] = []
    if not chinese_display_ready(article):
        gate_failures.append(CHINESE_READINESS_FAILURE)
    if _effective_source_type(article) in KEY_SIGNAL_CORROBORATION_REQUIRED_SOURCE_TYPES:
        gate_failures.append("媒体报道或作者观点不能单独作为 Key Signal")
    if values.event_significance < 0.7:
        gate_failures.append("事件显著性低于 70")
    if max(
        values.decision_impact,
        values.adoption_momentum,
        values.technical_advancement,
    ) < 0.6:
        gate_failures.append("缺少足以改变决策、采用或技术判断的证据")
    if values.target_relevance < 0.35 and values.product_industry_impact < 0.65:
        gate_failures.append("与 AI、产品或技术决策范围关联不足")
    if values.evidence_maturity < 0.5 or len((article.facts.abstract or "").strip()) < 120:
        gate_failures.append("证据成熟度不足")
    if _effective_source_type(article) == "academic" and (
        EVENT_TYPE_TECH_BREAKTHROUGH not in event_profile.event_types
        or values.target_relevance < 0.65
        or values.technical_generality < 0.55
    ):
        gate_failures.append("学术内容缺少高相关、可泛化的突破证据")
    if score < 0.65:
        gate_failures.append("Key Signal 专用得分低于 65")

    reasons: list[str] = [
        EVENT_REASON_LABELS[event_type]
        for event_type in event_profile.event_types[:2]
        if event_type in EVENT_REASON_LABELS
    ]
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
        event_types=list(event_profile.event_types),
        reasons=reasons[:5],
        gate_failures=gate_failures[:8],
    )


def key_signal_waiting_for_chinese(article: Article) -> bool:
    """Return whether Chinese presentation is the candidate's only Key Signal blocker."""

    assessment = article.key_signal or key_signal_assessment(article)
    return assessment.gate_failures == [CHINESE_READINESS_FAILURE]


def high_significance_event_candidate(article: Article) -> bool:
    """Allow notable events into limited Chinese enrichment before final editorial gating."""

    values = article.content_score_breakdown
    if values is None:
        return False
    source_type = _effective_source_type(article)
    evidence_floor = 0.35 if source_type == "professional_media" else 0.5
    if values.event_significance < 0.7 or values.evidence_maturity < evidence_floor:
        return False
    if len((article.facts.abstract or "").strip()) < 120:
        return False
    if values.target_relevance < 0.35 and values.product_industry_impact < 0.65:
        return False
    if source_type == "academic":
        assessment = article.key_signal or key_signal_assessment(article)
        return EVENT_TYPE_TECH_BREAKTHROUGH in assessment.event_types and (
            values.target_relevance >= 0.65 and values.technical_generality >= 0.55
        )
    return True


def apply_article_scoring(article: Article, *, anchor: datetime) -> Article:
    article.content_score_breakdown = content_score_breakdown(article, anchor=anchor)
    article.content_score = content_value_score(article, anchor=anchor)
    article.selection_reasons = content_selection_reasons(article, anchor=anchor)
    article.key_signal = key_signal_assessment(article)
    return article
