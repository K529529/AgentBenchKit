def chunked(items, size):
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("size must be a positive integer")
    result = []
    for item in items:
        if not result or len(result[-1]) == size:
            result.append([])
        result[-1].append(item)
    return result
