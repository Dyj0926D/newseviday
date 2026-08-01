from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree

from newseviday_pipeline.models import RawFeedItem

ATOM = "{http://www.w3.org/2005/Atom}"


def _text(element: ElementTree.Element | None) -> str:
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
    root: ElementTree.Element,
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
                summary=_text(entry.find(f"{ATOM}summary")) or None,
                authors=authors,
                published_at=_datetime(
                    _text(entry.find(f"{ATOM}published")) or _text(entry.find(f"{ATOM}updated"))
                ),
                language=language,
            )
        )
    return items


def _parse_rss(
    root: ElementTree.Element,
    *,
    source_id: str,
    language: str,
) -> list[RawFeedItem]:
    items: list[RawFeedItem] = []
    for entry in root.findall("./channel/item"):
        link = _text(entry.find("link"))
        title = _text(entry.find("title"))
        if not link or not title:
            continue
        author = _text(entry.find("author"))
        items.append(
            RawFeedItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=_text(entry.find("description")) or None,
                authors=[author] if author else [],
                published_at=_datetime(_text(entry.find("pubDate"))),
                language=language,
            )
        )
    return items
