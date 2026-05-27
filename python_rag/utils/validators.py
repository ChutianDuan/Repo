def normalize_positive_int_list(value, field_name="doc_ids"):
    if value is None:
        return value

    normalized = []
    seen = set()
    for item in value:
        item_id = int(item)
        if item_id <= 0:
            raise ValueError("{0} must contain positive integers".format(field_name))
        if item_id in seen:
            continue
        seen.add(item_id)
        normalized.append(item_id)

    if not normalized:
        raise ValueError("{0} must not be empty".format(field_name))

    return normalized
