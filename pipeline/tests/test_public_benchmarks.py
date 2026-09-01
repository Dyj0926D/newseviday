from datetime import UTC, datetime

from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.public_benchmarks import (
    adapt_multihop_rows,
    evaluate_multihop_retrieval,
)


def test_multihop_adapter_and_retrieval_report_are_reproducible() -> None:
    corpus = [
        {
            "url": "https://example.com/alpha",
            "title": "Alpha launches semantic catalog",
            "body": "Alpha released a semantic catalog for governed enterprise metrics.",
            "source": "Example",
            "category": "technology",
            "published_at": "2026-01-01T00:00:00Z",
        },
        {
            "url": "https://example.com/beta",
            "title": "Beta adds lineage",
            "body": "Beta added column-level lineage to its data platform.",
            "source": "Example",
            "category": "technology",
            "published_at": "2026-01-02T00:00:00Z",
        },
    ]
    questions = [
        {
            "query": "Which product launched a semantic catalog?",
            "question_type": "inference_query",
            "answer": "Alpha",
            "evidence_list": [{"url": "https://example.com/alpha"}],
        },
        {
            "query": "What relates the semantic catalog and column-level lineage?",
            "question_type": "comparison_query",
            "answer": "They are data governance capabilities.",
            "evidence_list": [
                {"url": "https://example.com/alpha"},
                {"url": "https://example.com/beta"},
            ],
        },
        {
            "query": "This question has no evidence.",
            "question_type": "null_query",
            "answer": "Insufficient information.",
            "evidence_list": [],
        },
    ]
    artifact = adapt_multihop_rows(
        corpus,
        questions,
        revision="fixture-revision",
        fetched_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    report = evaluate_multihop_retrieval(
        artifact,
        HashingEmbedder(dimensions=64),
        sample_size=0,
        now=datetime(2026, 1, 4, tzinfo=UTC),
    )

    assert len(artifact.documents) == 2
    assert len(artifact.questions) == 3
    assert report.corpus_document_count == 2
    assert report.evaluated_question_count == 2
    assert report.excluded_null_question_count == 1
    assert report.metrics.recall_at10 == 1.0
    assert report.dataset_revision == "fixture-revision"
