def _to_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat(sep="T", timespec="seconds")
    return str(value)