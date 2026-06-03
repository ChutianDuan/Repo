
def normalize_text(text):
    if text is None:
        return ""

    # 统一换行
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 去掉连续过多空行
    lines = []
    empty_count = 0
    for line in text.split("\n"):
        line = line.rstrip()
        if line == "":
            empty_count += 1
            if empty_count <= 1:
                lines.append("")
        else:
            empty_count = 0
            lines.append(line)

    return "\n".join(lines).strip()


def simple_chunk_text(text, chunk_size=800, overlap=100):
    """
    按字符切片：
    - chunk_size: 每块最大字符数
    - overlap: 相邻块重叠字符数
    """
    text = normalize_text(text)
    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0:
        raise ValueError("overlap must be >= 0")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break

        start = end - overlap

    return chunks