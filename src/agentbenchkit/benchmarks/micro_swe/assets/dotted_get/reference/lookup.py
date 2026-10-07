def dotted_get(mapping, path, default=None):
    current = mapping
    if not path:
        return current
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current
