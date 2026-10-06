import tomllib


def load_settings(path, overrides=None):
    with open(path, "rb") as stream:
        result = tomllib.load(stream)
    result.update(overrides or {})
    return result
