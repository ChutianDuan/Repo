import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List
from urllib.parse import quote, urljoin, urlparse

from python_rag.app.core.error_codes import ERR_INVALID_REQUEST
from python_rag.app.core.errors import AppError
from python_rag.app.shared import http_client
from python_rag.app.shared.text_chunker import normalize_text


FETCH_TIMEOUT_SECONDS = 20
MAX_WEB_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_WEB_REDIRECTS = 5
WEB_DOCUMENT_USER_AGENT = "python-rag-web-ingest/1.0"
WEB_DOCUMENT_MIME = "text/markdown; charset=utf-8"
_IGNORED_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}
_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "dd",
    "details",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?，。；：！？])")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass
class WebPageDocument:
    url: str
    final_url: str
    title: str
    description: str
    filename: str
    mime: str
    content: str
    content_bytes: bytes


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: List[str] = []
        self.meta: Dict[str, str] = {}
        self.body_parts: List[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs_dict = {str(name).lower(): value for name, value in attrs if name}
        if tag in _IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "meta":
            self._handle_meta(attrs_dict)
            return
        if tag == "li":
            self._append_newline()
            self.body_parts.append("- ")
            return
        if tag in _BLOCK_TAGS:
            self._append_newline()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in _BLOCK_TAGS:
            self._append_newline()

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = _compact_inline_text(data)
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
            return
        self.body_parts.append(text)
        self.body_parts.append(" ")

    def _handle_meta(self, attrs: Dict[str, str]) -> None:
        content = _compact_inline_text(attrs.get("content") or "")
        if not content:
            return
        key = _compact_inline_text(attrs.get("name") or attrs.get("property") or "").lower()
        if key:
            self.meta[key] = content

    def _append_newline(self) -> None:
        if not self.body_parts or self.body_parts[-1].endswith("\n"):
            return
        self.body_parts.append("\n")

    def title(self) -> str:
        title = " ".join(part.strip() for part in self.title_parts if part.strip())
        return _compact_inline_text(title)

    def description(self) -> str:
        for key in ("description", "og:description", "twitter:description"):
            value = self.meta.get(key)
            if value:
                return value
        return ""

    def body_text(self) -> str:
        return _normalize_body_text("".join(self.body_parts))


def validate_web_url(url: str) -> str:
    normalized = (url or "").strip()
    if not normalized:
        raise AppError(ERR_INVALID_REQUEST, "url is required")

    parsed = urlparse(normalized)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        raise AppError(ERR_INVALID_REQUEST, "url must be an http or https URL")
    if parsed.username is not None or parsed.password is not None:
        raise AppError(ERR_INVALID_REQUEST, "url must not contain credentials")
    return normalized


def _validate_public_target(url: str) -> str:
    normalized = validate_web_url(url)
    parsed = urlparse(normalized)
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {
            item[4][0].split("%", 1)[0]
            for item in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError) as exc:
        raise AppError(ERR_INVALID_REQUEST, "url host could not be resolved") from exc

    if not addresses:
        raise AppError(ERR_INVALID_REQUEST, "url host could not be resolved")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise AppError(ERR_INVALID_REQUEST, "url host resolved to an invalid address") from exc
        if not ip.is_global:
            raise AppError(ERR_INVALID_REQUEST, "url must resolve to a public address")
    return normalized


def _read_limited_response(response) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_WEB_DOCUMENT_BYTES:
                raise AppError(ERR_INVALID_REQUEST, "fetched web page is too large")
        except ValueError:
            pass

    chunks = []
    total_bytes = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total_bytes += len(chunk)
        if total_bytes > MAX_WEB_DOCUMENT_BYTES:
            raise AppError(ERR_INVALID_REQUEST, "fetched web page is too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _fetch_response(source_url: str):
    current_url = source_url
    for redirect_count in range(MAX_WEB_REDIRECTS + 1):
        current_url = _validate_public_target(current_url)
        try:
            response = http_client.request(
                "GET",
                current_url,
                timeout=FETCH_TIMEOUT_SECONDS,
                allow_redirects=False,
                stream=True,
                headers={
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
                    "User-Agent": WEB_DOCUMENT_USER_AGENT,
                },
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(ERR_INVALID_REQUEST, "failed to fetch url: {0}".format(exc)) from exc

        if response.status_code not in {301, 302, 303, 307, 308}:
            return response, current_url

        location = response.headers.get("location")
        response.close()
        if not location:
            raise AppError(ERR_INVALID_REQUEST, "web redirect is missing a location")
        if redirect_count >= MAX_WEB_REDIRECTS:
            raise AppError(ERR_INVALID_REQUEST, "too many web redirects")
        current_url = urljoin(current_url, location)

    raise AppError(ERR_INVALID_REQUEST, "too many web redirects")


def fetch_web_page_document(url: str) -> WebPageDocument:
    source_url = validate_web_url(url)
    try:
        response, final_url = _fetch_response(source_url)
        try:
            if response.status_code >= 400:
                raise AppError(
                    ERR_INVALID_REQUEST,
                    "failed to fetch url: http status {0}".format(response.status_code),
                )
            raw = _read_limited_response(response)
            content_type = (response.headers.get("content-type") or "").lower()
            text = _decode_response_text(response, raw)
        finally:
            response.close()
    except AppError:
        raise

    if not raw:
        raise AppError(ERR_INVALID_REQUEST, "fetched web page is empty")

    if "html" in content_type or _looks_like_html(text):
        title, description, body_text = _extract_html_text(text)
    else:
        title = ""
        description = ""
        body_text = normalize_text(text)

    if not body_text:
        raise AppError(ERR_INVALID_REQUEST, "fetched web page text is empty")

    if not title:
        title = _title_from_url(final_url)

    content = _render_web_document_markdown(
        title=title,
        url=source_url,
        final_url=final_url,
        description=description,
        body_text=body_text,
    )
    content_bytes = content.encode("utf-8")
    return WebPageDocument(
        url=source_url,
        final_url=final_url,
        title=title,
        description=description,
        filename=_build_web_document_filename(final_url, title),
        mime=WEB_DOCUMENT_MIME,
        content=content,
        content_bytes=content_bytes,
    )


def _decode_response_text(response, raw: bytes) -> str:
    encoding = getattr(response, "encoding", None) or getattr(response, "apparent_encoding", None)
    if encoding:
        try:
            return raw.decode(encoding, errors="replace")
        except LookupError:
            pass
    return raw.decode("utf-8", errors="replace")


def _extract_html_text(html: str) -> tuple[str, str, str]:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.title(), parser.description(), parser.body_text()


def _render_web_document_markdown(
    *,
    title: str,
    url: str,
    final_url: str,
    description: str,
    body_text: str,
) -> str:
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    parts = [
        "# {0}".format(title.strip()),
        "",
        "Source URL: {0}".format(url.strip()),
    ]
    if final_url != url:
        parts.append("Final URL: {0}".format(final_url.strip()))
    parts.append("Fetched At: {0}".format(fetched_at))
    if description:
        parts.extend(["", description.strip()])
    parts.extend(["", body_text.strip()])
    return normalize_text("\n".join(parts))


def _compact_inline_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", unescape(text or "").replace("\r", " ").replace("\n", " ")).strip()


def _normalize_body_text(text: str) -> str:
    lines = []
    for line in unescape(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _compact_inline_text(line)
        line = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", line)
        if line:
            lines.append(line)
    return _BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()


def _looks_like_html(text: str) -> bool:
    sample = (text or "")[:2048].lower()
    return "<html" in sample or "<body" in sample or "<!doctype html" in sample


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")[-1]
    if path:
        return path.replace("-", " ").replace("_", " ").strip()
    return parsed.hostname or "web page"


def _build_web_document_filename(url: str, title: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "web"
    title_slug = _SLUG_RE.sub("_", (title or "").strip()).strip("._-").lower()
    if not title_slug:
        title_slug = quote(parsed.path.strip("/").split("/")[-1] or "page", safe="")
    title_slug = title_slug[:80].strip("._-") or "page"
    return "web_{0}_{1}.md".format(_SLUG_RE.sub("_", host).strip("._-"), title_slug)
