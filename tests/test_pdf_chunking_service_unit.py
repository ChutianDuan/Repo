import sys
from types import SimpleNamespace

import pytest

from python_rag.app.core.errors import AppError
from python_rag.app.modules.ingest.chunking_service import (
    chunk_text_by_title,
    extract_text_from_document,
)


def test_pdf_is_converted_to_markdown_before_title_chunking(tmp_path, monkeypatch):
    pdf_path = tmp_path / "guide.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    markdown = (
        "# Installation\n\n"
        "Install the package before starting.\n\n"
        "## Configuration\n\n"
        "Set the service endpoint."
    )
    calls = []

    def to_markdown(path, *, show_progress):
        calls.append((path, show_progress))
        return markdown

    monkeypatch.setitem(
        sys.modules,
        "pymupdf4llm",
        SimpleNamespace(to_markdown=to_markdown),
    )

    extracted = extract_text_from_document(str(pdf_path), pdf_path.name)
    chunks = chunk_text_by_title(
        extracted,
        filename=pdf_path.name,
        chunk_size=200,
        overlap=20,
    )

    assert calls == [(str(pdf_path), False)]
    assert extracted == markdown
    assert chunks == [
        "# Installation\n\nInstall the package before starting.",
        "## Configuration\n\nSet the service endpoint.",
    ]


def test_pdf_conversion_rejects_empty_markdown(tmp_path, monkeypatch):
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    monkeypatch.setitem(
        sys.modules,
        "pymupdf4llm",
        SimpleNamespace(to_markdown=lambda *args, **kwargs: ""),
    )

    with pytest.raises(AppError, match="separately configured OCR engine"):
        extract_text_from_document(str(pdf_path), pdf_path.name)
