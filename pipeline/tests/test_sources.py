from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.adapters import parse_json_feed, parse_source
from newseviday_pipeline.embeddings import HashingEmbedder, cosine_similarity
from newseviday_pipeline.extraction import clean_html_text
from newseviday_pipeline.models import SourceConfig, TopicConfig
from newseviday_pipeline.network import FetchResult, validate_public_url
from newseviday_pipeline.runner import run_network_pipeline


def source(source_id: str) -> SourceConfig:
    return SourceConfig(
        id=source_id,
        name=source_id,
        adapter="rss",
        url=f"https://{source_id}.example/feed.xml",
        language="en",
        region="global",
        enabled=True,
        usage_scope="metadata_and_excerpt",
    )


def rss(title: str, link: str, summary: str) -> bytes:
    return f"""<?xml version="1.0"?><rss version="2.0"><channel><item>
      <title>{title}</title><link>{link}</link><description>{summary}</description>
      <pubDate>Fri, 01 Aug 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>""".encode()


def test_html_extraction_removes_scripts_navigation_and_markup() -> None:
    value = (
        "<nav>menu</nav><article><h1>Title</h1><p>Useful body.</p>"
        "<script>secret()</script></article>"
    )
    assert clean_html_text(value) == "Title\nUseful body."


def test_json_feed_adapter_supports_standard_items() -> None:
    items = parse_json_feed(
        b'{"items":[{"id":"https://example.com/a","title":"Agent update",'
        b'"content_text":"Evidence"}]}',
        source_id="json-source",
        language="en",
    )
    assert items[0].url == "https://example.com/a"
    assert items[0].summary == "Evidence"


def test_public_url_validation_blocks_local_targets() -> None:
    validate_public_url("https://example.com/feed")
    for value in ["http://example.com/feed", "https://localhost/feed", "https://127.0.0.1/feed"]:
        try:
            validate_public_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected {value} to be rejected")


def test_network_pipeline_keeps_partial_source_failures_and_writes_trace(
    tmp_path: Path, monkeypatch: object
) -> None:
    configured = [source("one"), source("two"), source("three"), source("four")]

    def fake_fetch(item: SourceConfig) -> FetchResult:
        if item.id == "four":
            return FetchResult(item, None, None, "timeout")
        titles = {
            "one": "Data agent uses governed semantic metrics",
            "two": "Retrieval evaluation enters the data agent release gate",
            "three": "Data agent connects catalog lineage and permissions",
        }
        content = rss(
            titles[item.id],
            f"https://{item.id}.example/posts/1",
            "Data agent metrics layer and governed retrieval.",
        )
        return FetchResult(item, content, str(item.url), None)

    monkeypatch.setattr("newseviday_pipeline.runner.fetch_source", fake_fetch)  # type: ignore[attr-defined]
    run, snapshot = run_network_pipeline(
        configured,
        tmp_path,
        topics=[TopicConfig(id="data-agent", label="Data Agent", keywords=["data agent"])],
        config_version=1,
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    assert run.status == "succeeded"
    assert snapshot.source_count == 3
    assert len(snapshot.articles) == 3
    assert (tmp_path / "runs" / f"{run.id}.json").exists()
    assert parse_source(rss("Title long enough", "https://example.com/a", "Body"), configured[0])


def test_hashing_embeddings_are_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(dimensions=64)
    vectors = embedder.embed(["semantic layer for data agent", "semantic layer for data agent"])
    assert vectors[0] == vectors[1]
    assert round(cosine_similarity(vectors[0], vectors[1]), 6) == 1.0
