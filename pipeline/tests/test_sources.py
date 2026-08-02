from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.adapters import (
    parse_html_headings,
    parse_html_listing,
    parse_json_feed,
    parse_source,
)
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


def test_html_listing_applies_official_article_url_allowlist() -> None:
    content = b"""
      <nav><a href="/pricing">Pricing and unrelated navigation</a></nav>
      <main><a href="/news/agent-release">Agent release with evidence</a></main>
    """
    items = parse_html_listing(
        content,
        source_id="official-news",
        language="en",
        base_url="https://example.com/news",
        include_url_patterns=[r"^https://example\.com/news/[a-z-]+$"],
    )

    assert [item.url for item in items] == ["https://example.com/news/agent-release"]


def test_html_listing_prefers_heading_over_card_metadata() -> None:
    content = b"""
      <a href="/news/claude-release">
        <span>Product</span><time>Aug 2</time><h3>Claude release for agents</h3>
        <p>Long description that should not become the title.</p>
      </a>
    """
    items = parse_html_listing(
        content,
        source_id="anthropic-news",
        language="en",
        base_url="https://example.com/news",
    )

    assert items[0].title == "Claude release for agents"


def test_html_listing_can_select_a_source_specific_title_class() -> None:
    content = b"""
      <a href="/news/security-evals">
        <time>Jul 30, 2026</time><span class="card__subject">Frontier Red Team</span>
        <span class="card__title body-3">Investigating cybersecurity evaluations</span>
      </a>
    """
    items = parse_html_listing(
        content,
        source_id="anthropic-news",
        language="en",
        base_url="https://example.com/news",
        title_class_patterns=[r"__title(?:\s|$)"],
    )

    assert items[0].title == "Investigating cybersecurity evaluations"


def test_html_heading_listing_creates_stable_fragment_links() -> None:
    content = b"""
      <h2 id="2026-08-02">2026-08-02</h2>
      <h3 id="deepseek-v4">\xe2\x80\x8bDeepSeek-V4</h3>
      <h3>Navigation heading without an id</h3>
    """
    items = parse_html_headings(
        content,
        source_id="deepseek-updates",
        language="mixed",
        base_url="https://api-docs.deepseek.com/updates/",
        heading_tags=["h3"],
    )

    assert [(item.url, item.title) for item in items] == [
        ("https://api-docs.deepseek.com/updates/#deepseek-v4", "DeepSeek-V4")
    ]
    assert items[0].preserve_fragment is True


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
