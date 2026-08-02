import json
from collections.abc import Mapping
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
        try:
            parsed = parsedate_to_datetime(value.strip())
        except (TypeError, ValueError):
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
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or self._href is not None:
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href:
            self._href = urljoin(self.base_url, href)
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        title = " ".join("".join(self._text).split())
        if len(title) >= 12 and self._href.startswith(("http://", "https://")):
            self.links.append((self._href, title))
        self._href = None
        self._text = []


def parse_html_listing(
    content: bytes,
    *,
    source_id: str,
    language: str,
    base_url: str,
) -> list[RawFeedItem]:
    parser = _ListingParser(base_url)
    parser.feed(content.decode("utf-8", errors="replace"))
    seen: set[str] = set()
    result: list[RawFeedItem] = []
    for link, title in parser.links:
        if link in seen:
            continue
        seen.add(link)
        result.append(
            RawFeedItem(source_id=source_id, url=link, title=title, language=language)
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
        return parse_html_listing(
            content,
            source_id=source.id,
            language=source.language,
            base_url=str(source.url),
        )


ADAPTERS: dict[str, SourceAdapter] = {
    "atom": SyndicationAdapter(),
    "rss": SyndicationAdapter(),
    "json": JsonFeedAdapter(),
    "html": HtmlListingAdapter(),
}


def parse_source(content: bytes, source: SourceConfig) -> list[RawFeedItem]:
    return ADAPTERS[source.adapter].parse(content, source)[: source.max_items]
