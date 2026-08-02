from html.parser import HTMLParser


class _ReadableTextParser(HTMLParser):
    _blocked = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form"}
    _breaks = {"article", "blockquote", "br", "div", "h1", "h2", "h3", "li", "p", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._blocked:
            self._blocked_depth += 1
        elif tag in self._breaks and self._blocked_depth == 0:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._blocked and self._blocked_depth:
            self._blocked_depth -= 1
        elif tag in self._breaks and self._blocked_depth == 0:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._blocked_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        paragraphs = [" ".join(part.split()) for part in "".join(self._parts).splitlines()]
        return "\n".join(part for part in paragraphs if part)


def clean_html_text(value: str, *, max_chars: int = 12_000) -> str:
    parser = _ReadableTextParser()
    parser.feed(value)
    return parser.text()[:max_chars]
