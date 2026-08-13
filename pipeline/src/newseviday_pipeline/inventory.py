import hashlib
from datetime import datetime, timedelta

from newseviday_pipeline.models import Article, ContentSnapshot
from newseviday_pipeline.stages import (
    ARXIV_SOURCE_ID,
    apply_article_scoring,
    chinese_display_ready,
)


def _article_time(article: Article) -> datetime:
    return article.published_at or article.collected_at


def _source_limit(source_id: str, *, max_per_source: int) -> int:
    return 6 if source_id == ARXIV_SOURCE_ID else max_per_source


def merge_rolling_inventory(
    incoming: ContentSnapshot,
    accepted: ContentSnapshot,
    *,
    window_days: int = 30,
    max_total: int = 40,
    minimum_chinese_ready: int = 20,
    max_per_source: int = 8,
) -> ContentSnapshot:
    """Merge a fresh collection with the accepted rolling public inventory.

    The fresh collection remains the source of pipeline metadata. Recently published,
    Chinese-ready accepted articles may survive a feed rotation, and accepted AI fields
    are restored on matching incoming articles before the next enrichment pass.
    """

    if min(window_days, max_total, minimum_chinese_ready, max_per_source) < 1:
        raise ValueError("rolling_inventory_limits_must_be_positive")

    cutoff = incoming.generated_at - timedelta(days=window_days)
    accepted_by_hash = {article.content_hash: article for article in accepted.articles}
    accepted_by_url = {article.canonical_url: article for article in accepted.articles}
    accepted_ready_hashes = {
        article.content_hash
        for article in accepted.articles
        if _article_time(article) >= cutoff and chinese_display_ready(article)
    }
    candidates: dict[str, Article] = {}

    for item in incoming.articles:
        article = item.model_copy(deep=True)
        previous = accepted_by_hash.get(article.content_hash) or accepted_by_url.get(
            article.canonical_url
        )
        if previous is not None and previous.ai is not None:
            article.ai = previous.ai.model_copy(deep=True)
        apply_article_scoring(article, anchor=incoming.generated_at)
        candidates[article.content_hash] = article

    for item in accepted.articles:
        if item.content_hash in candidates:
            continue
        if _article_time(item) < cutoff or not chinese_display_ready(item):
            continue
        article = item.model_copy(deep=True)
        apply_article_scoring(article, anchor=incoming.generated_at)
        candidates[article.content_hash] = article

    ranked_ready = sorted(
        (
            article
            for article in candidates.values()
            if _article_time(article) >= cutoff and chinese_display_ready(article)
        ),
        key=lambda article: (_article_time(article), article.content_score or 0.0),
        reverse=True,
    )
    ranked_all = sorted(
        candidates.values(),
        key=lambda article: (article.content_score or 0.0, _article_time(article)),
        reverse=True,
    )

    selected: list[Article] = []
    selected_hashes: set[str] = set()
    source_counts: dict[str, int] = {}

    def select(article: Article) -> bool:
        if article.content_hash in selected_hashes or len(selected) >= max_total:
            return False
        limit = _source_limit(article.source_id, max_per_source=max_per_source)
        if source_counts.get(article.source_id, 0) >= limit:
            return False
        selected.append(article)
        selected_hashes.add(article.content_hash)
        source_counts[article.source_id] = source_counts.get(article.source_id, 0) + 1
        return True

    new_ready_count = sum(
        article.content_hash not in accepted_ready_hashes and chinese_display_ready(article)
        for article in incoming.articles
        if _article_time(article) >= cutoff
    )
    desired_ready = min(
        max_total,
        max(minimum_chinese_ready, len(accepted_ready_hashes) + new_ready_count),
    )
    for article in ranked_ready:
        if sum(chinese_display_ready(item) for item in selected) >= desired_ready:
            break
        select(article)
    for article in ranked_all:
        if len(selected) >= max_total:
            break
        select(article)

    # Feed order is explicitly time-first. Content score still decides ties and admission.
    selected.sort(
        key=lambda article: (_article_time(article), article.content_score or 0.0),
        reverse=True,
    )

    source_by_id = {source.id: source.model_copy(deep=True) for source in accepted.sources}
    source_by_id.update({source.id: source.model_copy(deep=True) for source in incoming.sources})
    evidence_by_id = {item.id: item.model_copy(deep=True) for item in accepted.evidence}
    evidence_by_id.update({item.id: item.model_copy(deep=True) for item in incoming.evidence})
    selected_evidence_ids = {
        evidence_id for article in selected for evidence_id in article.evidence_ids
    }
    signature = hashlib.sha256(
        "\n".join(article.content_hash for article in selected).encode("utf-8")
    ).hexdigest()[:8]

    result = incoming.model_copy(deep=True)
    result.snapshot_id = f"{incoming.snapshot_id}-rolling-{signature}"
    result.source_count = len(source_by_id)
    result.sources = list(source_by_id.values())
    result.articles = selected
    result.evidence = [
        evidence
        for evidence_id, evidence in evidence_by_id.items()
        if evidence_id in selected_evidence_ids
    ]
    result.briefs = [brief.model_copy(deep=True) for brief in accepted.briefs]
    result.state = "ready" if selected else "empty"
    return result
