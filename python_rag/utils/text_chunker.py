def simple_chunk_text(text, chunk_size=800, overlap=100):
    if not text:
        return []

    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)

    if overlap >= chunk_size:
        overlap = 0

    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap

    return chunks