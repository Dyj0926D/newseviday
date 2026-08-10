import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urljoin
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from newseviday_pipeline.extraction import clean_html_text
from newseviday_pipeline.models import RawFeedItem, SourceConfig

ATOM = "{http://www.w3.org/2005/Atom}"


def _text(element: Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _datetime(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for date_format in ("%b %d, %Y", "%B %d, %Y"):
            try:
                parsed = datetime.strptime(value.strip(), date_format).replace(tzinfo=UTC)
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                parsed = parsedate_to_datetime(value.strip())
            except (TypeError, ValueError):
                return None
        if parsed is None:
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_syndication(
    content: bytes,
    *,
    source_id: str,
    language: str,
) -> list[RawFeedItem]:
    root = ElementTree.fromstring(content)
    if root.tag == f"{ATOM}feed":
        return _parse_atom(root, source_id=source_id, language=language)
    if root.tag.lower().endswith("rss") or root.find("channel") is not None:
        return _parse_rss(root, source_id=source_id, language=language)
    raise ValueError("unsupported_feed_format")


def parse_fixture(path: Path, *, source_id: str, language: str) -> list[RawFeedItem]:
    return parse_syndication(path.read_bytes(), source_id=source_id, language=language)


def _parse_atom(
    root: Element,
    *,
    source_id: str,
    language: str,
) -> list[RawFeedItem]:
    items: list[RawFeedItem] = []
    for entry in root.findall(f"{ATOM}entry"):
        link = next(
            (
                element.attrib.get("href", "")
                for element in entry.findall(f"{ATOM}link")
                if element.attrib.get("rel", "alternate") == "alternate"
            ),
            "",
        )
        if not link:
            link = _text(entry.find(f"{ATOM}id"))
        title = _text(entry.find(f"{ATOM}title"))
        if not link or not title:
            continue
        authors = [
            _text(author.find(f"{ATOM}name"))
            for author in entry.findall(f"{ATOM}author")
            if _text(author.find(f"{ATOM}name"))
        ]
        items.append(
            RawFeedItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=clean_html_text(_text(entry.find(f"{ATOM}summary"))) or None,
                authors=authors,
                published_at=_datetime(
                    _text(entry.find(f"{ATOM}published")) or _text(entry.find(f"{ATOM}updated"))
                ),
                language=language,
                content_html=_text(entry.find(f"{ATOM}content")) or None,
            )
        )
    return items


def _parse_rss(
    root: Element,
    *,
    source_id: str,
    language: str,
) -> list[RawFeedItem]:
    items: list[RawFeedItem] = []
    for entry in root.findall("./channel/item"):
        link = _text(entry.find("link")) or _text(entry.find("guid"))
        title = _text(entry.find("title"))
        if not link or not title:
            continue
        author = _text(entry.find("author"))
        items.append(
            RawFeedItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=clean_html_text(_text(entry.find("description"))) or None,
                authors=[author] if author else [],
                published_at=_datetime(_text(entry.find("pubDate"))),
                language=language,
                content_html=_text(entry.find("{http://purl.org/rss/1.0/modules/content/}encoded"))
                or None,
            )
        )
    return items


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def parse_json_feed(content: bytes, *, source_id: str, language: str) -> list[RawFeedItem]:
    payload = json.loads(content.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("unsupported_json_feed_format")
    items: list[RawFeedItem] = []
    for raw_item in payload["items"]:
        item = _mapping(raw_item)
        link = str(item.get("url") or item.get("external_url") or item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not link or not title:
            continue
        authors = [
            str(author.get("name"))
            for author in (_mapping(value) for value in item.get("authors", []))
            if author.get("name")
        ]
        content_html = str(item.get("content_html") or "").strip() or None
        summary = str(item.get("summary") or item.get("content_text") or "").strip()
        if not summary and content_html:
            summary = clean_html_text(content_html)
        items.append(
            RawFeedItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=summary or None,
                authors=authors,
                published_at=_datetime(str(item.get("date_published") or "")),
                language=language,
                content_html=content_html,
            )
        )
    return items


class _ListingParser(HTMLParser):
    def __init__(self, base_url: str, title_class_patterns: Sequence[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_class_patterns = [re.compile(pattern) for pattern in title_class_patterns]
        self.links: list[tuple[str, str, str | None, datetime | None]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self._heading_tag: str | None = None
        self._heading_text: list[str] = []
        self._title_tag: str | None = None
        self._title_text: list[str] = []
        self._summary_tag: str | None = None
        self._summary_text: list[str] = []
        self._time_tag: str | None = None
        self._time_text: list[str] = []
        self._time_value: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._href is not None and tag in {"h1", "h2", "h3", "h4"}:
            self._heading_tag = tag
            self._heading_text = []
            return
        if self._href is not None and self._title_tag is None:
            class_name = dict(attrs).get("class") or ""
            if any(pattern.search(class_name) for pattern in self.title_class_patterns):
                self._title_tag = tag
                self._title_text = []
                return
        if self._href is not None and tag == "p" and self._summary_tag is None:
            self._summary_tag = tag
            self._summary_text = []
            return
        if self._href is not None and tag == "time" and self._time_tag is None:
            self._time_tag = tag
            self._time_text = []
            self._time_value = dict(attrs).get("datetime")
            return
        if tag != "a" or self._href is not None:
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href:
            self._href = urljoin(self.base_url, href)
            self._text = []
            self._heading_tag = None
            self._heading_text = []
            self._title_tag = None
            self._title_text = []
            self._summary_tag = None
            self._summary_text = []
            self._time_tag = None
            self._time_text = []
            self._time_value = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)
            if self._heading_tag is not None:
                self._heading_text.append(data)
            if self._title_tag is not None:
                self._title_text.append(data)
            if self._summary_tag is not None:
                self._summary_text.append(data)
            if self._time_tag is not None:
                self._time_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_tag:
            self._heading_tag = None
            return
        if tag == self._title_tag:
            self._title_tag = None
            return
        if tag == self._summary_tag:
            self._summary_tag = None
            return
        if tag == self._time_tag:
            self._time_tag = None
            return
        if tag != "a" or self._href is None:
            return
        heading_title = " ".join("".join(self._heading_text).split())
        class_title = " ".join("".join(self._title_text).split())
        title = heading_title or class_title or " ".join("".join(self._text).split())
        summary = " ".join("".join(self._summary_text).split()) or None
        published_at = _datetime(self._time_value or " ".join(self._time_text))
        if len(title) >= 12 and self._href.startswith(("http://", "https://")):
            self.links.append((self._href, title, summary, published_at))
        self._href = None
        self._text = []
        self._heading_tag = None
        self._heading_text = []
        self._title_tag = None
        self._title_text = []
        self._summary_tag = None
        self._summary_text = []
        self._time_tag = None
        self._time_text = []
        self._time_value = None


class _CardParser(HTMLParser):
    """Extract one item from semantic ``article`` or ``.card-post`` containers."""

    DATE_PATTERN = re.compile(
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}\b",
        re.IGNORECASE,
    )

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[tuple[list[tuple[str, str | None]], str, str | None, datetime | None]] = []
        self._root_tag: str | None = None
        self._root_depth = 0
        self._links: list[tuple[str, str | None]] = []
        self._headings: list[str] = []
        self._paragraphs: list[str] = []
        self._all_text: list[str] = []
        self._capture_tag: str | None = None
        self._capture_text: list[str] = []
        self._capture_kind: str | None = None
        self._time_value: str | None = None

    def _reset_card(self) -> None:
        self._links = []
        self._headings = []
        self._paragraphs = []
        self._all_text = []
        self._capture_tag = None
        self._capture_text = []
        self._capture_kind = None
        self._time_value = None

    def _flush_card(self) -> None:
        if not self._links:
            return
        title = next((item for item in self._headings if len(item) >= 8), "")
        if not title:
            title = next(
                (label for _link, label in self._links if label and len(label.strip()) >= 8),
                "",
            )
        if not title:
            return
        summary = next(
            (item for item in self._paragraphs if len(item) >= 20 and item != title),
            None,
        )
        full_text = " ".join(" ".join(self._all_text).split())
        date_match = self.DATE_PATTERN.search(full_text)
        published_at = _datetime(self._time_value or (date_match.group(0) if date_match else ""))
        self.cards.append((self._links.copy(), title, summary, published_at))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        is_card_root = tag == "article" or (tag == "div" and "card-post" in classes)
        if self._root_tag is None:
            if is_card_root:
                self._reset_card()
                self._root_tag = tag
                self._root_depth = 1
            return
        if tag == self._root_tag:
            self._root_depth += 1
        if tag == "a" and (href := attributes.get("href")):
            self._links.append((urljoin(self.base_url, href), attributes.get("aria-label")))
        if self._capture_tag is not None:
            return
        if tag in {"h1", "h2", "h3", "h4"} or "card-title" in classes:
            self._capture_tag = tag
            self._capture_kind = "heading"
            self._capture_text = []
        elif tag == "p":
            self._capture_tag = tag
            self._capture_kind = "paragraph"
            self._capture_text = []
        elif tag == "time":
            self._capture_tag = tag
            self._capture_kind = "time"
            self._capture_text = []
            self._time_value = attributes.get("datetime")

    def handle_data(self, data: str) -> None:
        if self._root_tag is None:
            return
        self._all_text.append(data)
        if self._capture_tag is not None:
            self._capture_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._root_tag is None:
            return
        if tag == self._capture_tag:
            value = " ".join("".join(self._capture_text).split())
            if value and self._capture_kind == "heading":
                self._headings.append(value)
            elif value and self._capture_kind == "paragraph":
                self._paragraphs.append(value)
            elif value and self._capture_kind == "time" and self._time_value is None:
                self._time_value = value
            self._capture_tag = None
            self._capture_text = []
            self._capture_kind = None
        if tag != self._root_tag:
            return
        self._root_depth -= 1
        if self._root_depth == 0:
            self._flush_card()
            self._root_tag = None


class _HeadingParser(HTMLParser):
    def __init__(self, base_url: str, heading_tags: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.heading_tags = heading_tags
        self.headings: list[tuple[str, str, str | None, datetime | None]] = []
        self._tag: str | None = None
        self._id: str | None = None
        self._text: list[str] = []
        self._current_date: datetime | None = None
        self._active_item: tuple[str, str, datetime | None] | None = None
        self._summary_text: list[str] = []

    def _flush_item(self) -> None:
        if self._active_item is None:
            return
        heading_id, title, published_at = self._active_item
        summary = " ".join("".join(self._summary_text).split())[:4_000] or None
        self.headings.append(
            (urljoin(self.base_url, f"#{heading_id}"), title, summary, published_at)
        )
        self._active_item = None
        self._summary_text = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "hr":
            self._flush_item()
            return
        if self._tag is not None or tag not in self.heading_tags | {"h2"}:
            return
        self._flush_item()
        heading_id = dict(attrs).get("id")
        if heading_id or tag == "h2":
            self._tag = tag
            self._id = heading_id
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._tag is not None:
            self._text.append(data)
        elif self._active_item is not None:
            self._summary_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._tag:
            return
        title = " ".join("".join(self._text).replace("\u200b", "").split())
        date_match = re.fullmatch(r"Date:\s*(\d{4}-\d{2}-\d{2})", title, re.IGNORECASE)
        if tag == "h2" and date_match:
            self._current_date = _datetime(date_match.group(1))
        elif tag in self.heading_tags and self._id is not None and len(title) >= 4:
            self._active_item = (self._id, title, self._current_date)
            self._summary_text = []
        self._tag = None
        self._id = None
        self._text = []

    def finish(self) -> None:
        self._flush_item()


def parse_html_listing(
    content: bytes,
    *,
    source_id: str,
    language: str,
    base_url: str,
    include_url_patterns: list[str] | None = None,
    exclude_url_patterns: list[str] | None = None,
    title_class_patterns: list[str] | None = None,
) -> list[RawFeedItem]:
    parser = _ListingParser(base_url, title_class_patterns or [])
    parser.feed(content.decode("utf-8", errors="replace"))
    seen: set[str] = set()
    result: list[RawFeedItem] = []
    includes = [re.compile(pattern) for pattern in (include_url_patterns or [])]
    excludes = [re.compile(pattern) for pattern in (exclude_url_patterns or [])]
    for link, title, summary, published_at in parser.links:
        if link in seen:
            continue
        if includes and not any(pattern.search(link) for pattern in includes):
            continue
        if any(pattern.search(link) for pattern in excludes):
            continue
        seen.add(link)
        result.append(
            RawFeedItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=summary,
                published_at=published_at,
                language=language,
            )
        )
    return result


def parse_html_cards(
    content: bytes,
    *,
    source_id: str,
    language: str,
    base_url: str,
    include_url_patterns: list[str] | None = None,
    exclude_url_patterns: list[str] | None = None,
) -> list[RawFeedItem]:
    parser = _CardParser(base_url)
    parser.feed(content.decode("utf-8", errors="replace"))
    includes = [re.compile(pattern) for pattern in (include_url_patterns or [])]
    excludes = [re.compile(pattern) for pattern in (exclude_url_patterns or [])]
    seen: set[str] = set()
    result: list[RawFeedItem] = []
    for links, title, summary, published_at in parser.cards:
        link = next(
            (
                item
                for item, _label in links
                if (not includes or any(pattern.search(item) for pattern in includes))
                and not any(pattern.search(item) for pattern in excludes)
            ),
            None,
        )
        if link is None or link in seen:
            continue
        seen.add(link)
        result.append(
            RawFeedItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=summary,
                published_at=published_at,
                language=language,
            )
        )
    return result


def parse_html_headings(
    content: bytes,
    *,
    source_id: str,
    language: str,
    base_url: str,
    heading_tags: Sequence[str],
) -> list[RawFeedItem]:
    parser = _HeadingParser(base_url, set(heading_tags))
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.finish()
    seen: set[str] = set()
    result: list[RawFeedItem] = []
    for link, title, summary, published_at in parser.headings:
        if link in seen:
            continue
        seen.add(link)
        result.append(
            RawFeedItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=summary,
                published_at=published_at,
                language=language,
                preserve_fragment=True,
            )
        )
    return result


class SourceAdapter(Protocol):
    def parse(self, content: bytes, source: SourceConfig) -> list[RawFeedItem]: ...


class SyndicationAdapter:
    def parse(self, content: bytes, source: SourceConfig) -> list[RawFeedItem]:
        return parse_syndication(content, source_id=source.id, language=source.language)


class JsonFeedAdapter:
    def parse(self, content: bytes, source: SourceConfig) -> list[RawFeedItem]:
        return parse_json_feed(content, source_id=source.id, language=source.language)


class HtmlListingAdapter:
    def parse(self, content: bytes, source: SourceConfig) -> list[RawFeedItem]:
        if source.html_card_mode:
            return parse_html_cards(
                content,
                source_id=source.id,
                language=source.language,
                base_url=str(source.url),
                include_url_patterns=source.include_url_patterns,
                exclude_url_patterns=source.exclude_url_patterns,
            )
        if source.heading_tags:
            return parse_html_headings(
                content,
                source_id=source.id,
                language=source.language,
                base_url=str(source.url),
                heading_tags=source.heading_tags,
            )
        return parse_html_listing(
            content,
            source_id=source.id,
            language=source.language,
            base_url=str(source.url),
            include_url_patterns=source.include_url_patterns,
            exclude_url_patterns=source.exclude_url_patterns,
            title_class_patterns=source.title_class_patterns,
        )


ADAPTERS: dict[str, SourceAdapter] = {
    "atom": SyndicationAdapter(),
    "rss": SyndicationAdapter(),
    "json": JsonFeedAdapter(),
    "html": HtmlListingAdapter(),
}


def parse_source(content: bytes, source: SourceConfig) -> list[RawFeedItem]:
    parsed = ADAPTERS[source.adapter].parse(content, source)
    items = [
        item
        for item in parsed
        if (not source.require_published_at or item.published_at is not None)
        and (not source.require_summary or bool((item.summary or "").strip()))
    ][: source.max_items]
    for item in items:
        item.source_type = source.source_type
        item.evidence_tier = source.evidence_tier
    return items
