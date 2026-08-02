import hashlib
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from newseviday_pipeline.extraction import clean_html_text
from newseviday_pipeline.models import (
    Article,
    ArticleFacts,
    Evidence,
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


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split()).strip()


def canonicalize_url(value: str) -> str:
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
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, query, ""))


def normalize_item(
    item: RawFeedItem,
    *,
    collected_at: datetime | None = None,
) -> tuple[Article, Evidence]:
    collected = collected_at or datetime.now(UTC)
    title = normalize_text(item.title)
    extracted = clean_html_text(item.content_html) if item.content_html else ""
    abstract = normalize_text(extracted or item.summary or "")[:2_500] or None
    canonical_url = canonicalize_url(item.url)
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
                scores[topic.id] = round(topic.weight * matches / len(topic.keywords), 4)
        article.topic_scores = scores
        if not topics or max(scores.values(), default=0) >= minimum_score:
            selected.append(article)
    return selected


def apply_content_quotas(
    articles: list[Article],
    *,
    max_total: int = 40,
    max_per_source: int = 8,
) -> list[Article]:
    if max_total < 1 or max_per_source < 1:
        raise ValueError("content_quotas_must_be_positive")
    ranked = sorted(
        articles,
        key=lambda article: (
            max(article.topic_scores.values(), default=0),
            article.published_at or article.collected_at,
        ),
        reverse=True,
    )
    counts: dict[str, int] = {}
    result: list[Article] = []
    for article in ranked:
        if len(result) >= max_total:
            break
        if counts.get(article.source_id, 0) >= max_per_source:
            continue
        result.append(article)
        counts[article.source_id] = counts.get(article.source_id, 0) + 1
    return result
