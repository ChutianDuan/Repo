import pytest

from python_rag.utils.text_chunker import normalize_text, simple_chunk_text


def test_normalize_text_collapses_extra_blank_lines():
    text = "a\r\n\r\n\r\nb  \r\n"

    assert normalize_text(text) == "a\n\nb"


def test_simple_chunk_text_preserves_overlap():
    chunks = simple_chunk_text("abcdefghij", chunk_size=4, overlap=2)

    assert chunks == ["abcd", "cdef", "efgh", "ghij"]


def test_simple_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError, match="overlap"):
        simple_chunk_text("abcdef", chunk_size=4, overlap=4)
