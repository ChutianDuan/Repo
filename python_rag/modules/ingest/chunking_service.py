import os
from typing import Iterable, List

from python_rag.core.error_codes import ERR_CELERY_ERROR
from python_rag.core.errors import AppError


SUPPORTED_DOCUMENT_EXTENSIONS = (
    "md",
    "txt",
    "json",
    "csv",
    "pdf",
    "docx",
)

TEXT_DOCUMENT_EXTENSIONS = {"md", "txt", "json", "csv"}


def get_document_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    return ext.lower().lstrip(".")


def supported_document_extensions_text() -> str:
    return ", ".join(f".{ext}" for ext in SUPPORTED_DOCUMENT_EXTENSIONS)


def is_supported_document_filename(filename: str) -> bool:
    return get_document_extension(filename) in SUPPORTED_DOCUMENT_EXTENSIONS


def validate_supported_document_filename(filename: str) -> None:
    if is_supported_document_filename(filename):
        return
    raise AppError(
        ERR_CELERY_ERROR,
        "unsupported document format; currently supported: %s"
        % supported_document_extensions_text(),
    )


def _read_binary_file(path: str) -> bytes:
    if not os.path.exists(path):
        raise AppError(ERR_CELERY_ERROR, "document file does not exist")

    with open(path, "rb") as f:
        return f.read()


def _decode_text_bytes(raw: bytes) -> str:
    if not raw:
        return ""

    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue

    return raw.decode("utf-8", errors="ignore")


def _extract_text_from_plain_file(path: str) -> str:
    return _decode_text_bytes(_read_binary_file(path))


def _extract_text_from_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise AppError(
            ERR_CELERY_ERROR,
            f"pdf parser dependencies are not available: {exc}",
        ) from exc

    try:
        reader = PdfReader(path)
    except Exception as exc:
        raise AppError(ERR_CELERY_ERROR, f"failed to open pdf: {exc}") from exc

    page_texts: List[str] = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if text:
            page_texts.append(f"[Page {page_index}]\n{text}")

    if not page_texts:
        raise AppError(
            ERR_CELERY_ERROR,
            "pdf text extraction produced empty content; scanned pdf OCR is not supported yet",
        )

    return "\n\n".join(page_texts)


def _iter_docx_table_texts(document) -> Iterable[str]:
    for table in getattr(document, "tables", []):
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
            if cells:
                yield " | ".join(cells)


def _extract_text_from_docx(path: str) -> str:
    try:
        from docx import Document
    except Exception as exc:
        raise AppError(
            ERR_CELERY_ERROR,
            f"docx parser dependencies are not available: {exc}",
        ) from exc

    try:
        document = Document(path)
    except Exception as exc:
        raise AppError(ERR_CELERY_ERROR, f"failed to open docx: {exc}") from exc

    parts: List[str] = []
    for paragraph in document.paragraphs:
        text = (paragraph.text or "").strip()
        if text:
            parts.append(text)

    parts.extend(_iter_docx_table_texts(document))
    return "\n\n".join(parts)


def extract_text_from_document(path: str, filename: str) -> str:
    validate_supported_document_filename(filename)

    ext = get_document_extension(filename)
    if ext in TEXT_DOCUMENT_EXTENSIONS:
        return _extract_text_from_plain_file(path)
    if ext == "pdf":
        return _extract_text_from_pdf(path)
    if ext == "docx":
        return _extract_text_from_docx(path)

    raise AppError(
        ERR_CELERY_ERROR,
        "unsupported document format; currently supported: %s"
        % supported_document_extensions_text(),
    )
