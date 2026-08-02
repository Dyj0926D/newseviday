from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

import httpx

from newseviday_pipeline.models import SourceConfig

USER_AGENT = "NewsEviday/0.2 (+https://github.com/Dyj0926D/newseviday)"
MAX_RESPONSE_BYTES = 3_000_000


@dataclass(frozen=True)
class FetchResult:
    source: SourceConfig
    content: bytes | None
    final_url: str | None
    error_code: str | None

    @property
    def ok(self) -> bool:
        return self.content is not None


def validate_public_url(value: str) -> None:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("source_url_must_be_public_https")
    if parts.hostname.casefold() in {"localhost", "localhost.localdomain"}:
        raise ValueError("source_url_must_be_public_https")
    try:
        address = ip_address(parts.hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("source_url_must_be_public_https")


def fetch_source(source: SourceConfig) -> FetchResult:
    url = str(source.url)
    validate_public_url(url)
    try:
        with (
            httpx.Client(
            follow_redirects=True,
            timeout=source.request_timeout_seconds,
            headers={
                "Accept": (
                    "application/atom+xml, application/rss+xml, application/json, "
                    "text/html;q=0.8"
                ),
                "User-Agent": USER_AGENT,
            },
            ) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            validate_public_url(str(response.url))
            parts: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    return FetchResult(source, None, str(response.url), "response_too_large")
                parts.append(chunk)
            return FetchResult(source, b"".join(parts), str(response.url), None)
    except (httpx.HTTPError, ValueError) as error:
        return FetchResult(source, None, None, type(error).__name__)
