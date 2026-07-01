from pathlib import Path

import pytest

from python_rag.app.core.errors import AppError
from python_rag.app.modules.documents import service as document_service
from python_rag.app.modules.ingest import web_page_service
from python_rag.app.modules.ingest.web_page_service import WebPageDocument


class FakeResponse:
    def __init__(self, html: str, url: str = "https://example.com/docs") -> None:
        self.status_code = 200
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"
        self.content = html.encode("utf-8")


def test_fetch_web_page_document_extracts_readable_markdown(monkeypatch):
    html = """
    <!doctype html>
    <html>
      <head>
        <title>Example Title</title>
        <meta name="description" content="Short page summary">
        <style>.hidden { display: none; }</style>
        <script>window.secret = true;</script>
      </head>
      <body>
        <main>
          <h1>Main Heading</h1>
          <p>First paragraph with <strong>inline text</strong>.</p>
          <ul><li>First item</li><li>Second item</li></ul>
        </main>
      </body>
    </html>
    """

    def fake_request(method, url, **kwargs):
        assert method == "GET"
        assert url == "https://example.com/docs"
        assert kwargs["allow_redirects"] is True
        return FakeResponse(html)

    monkeypatch.setattr(web_page_service.http_client, "request", fake_request)

    document = web_page_service.fetch_web_page_document("https://example.com/docs")

    assert document.filename == "web_example.com_example_title.md"
    assert "# Example Title" in document.content
    assert "Source URL: https://example.com/docs" in document.content
    assert "Short page summary" in document.content
    assert "Main Heading" in document.content
    assert "First paragraph with inline text." in document.content
    assert "- First item" in document.content
    assert "secret" not in document.content


def test_fetch_web_page_document_rejects_non_http_url():
    with pytest.raises(AppError) as exc:
        web_page_service.fetch_web_page_document("ftp://example.com/file")

    assert "http or https" in str(exc.value)


def test_save_web_document_writes_markdown_and_creates_document_record(monkeypatch, tmp_path):
    content = "# Page\n\nSource URL: https://example.com/page\n\nBody"
    web_document = WebPageDocument(
        url="https://example.com/page",
        final_url="https://example.com/page",
        title="Page",
        description="",
        filename="web_example.com_page.md",
        mime="text/markdown; charset=utf-8",
        content=content,
        content_bytes=content.encode("utf-8"),
    )
    created = {}

    monkeypatch.setattr(
        document_service,
        "fetch_web_page_document",
        lambda url: web_document,
    )
    monkeypatch.setattr(
        document_service,
        "build_upload_path",
        lambda filename: str(tmp_path / filename),
    )

    def fake_create_document_record(**kwargs):
        created.update(kwargs)
        return 42

    monkeypatch.setattr(document_service, "create_document_record", fake_create_document_record)

    result = document_service.save_web_document(user_id=7, url="https://example.com/page")

    saved_path = Path(created["storage_path"])
    assert result["doc_id"] == 42
    assert result["filename"] == "web_example.com_page.md"
    assert result["source_url"] == "https://example.com/page"
    assert saved_path.read_text(encoding="utf-8") == content
    assert created["user_id"] == 7
    assert created["filename"] == "web_example.com_page.md"
    assert created["mime"] == "text/markdown; charset=utf-8"
    assert created["size_bytes"] == len(content.encode("utf-8"))
