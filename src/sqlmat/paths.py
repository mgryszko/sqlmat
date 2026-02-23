import re


def normalize_path(path: str) -> str:
    return re.sub(r"(?<!:)/{2,}", "/", path)
