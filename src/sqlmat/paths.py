import re


def normalize_path(path: str) -> str:
    """Collapse consecutive slashes in a path, preserving protocol prefixes like ``s3://``."""
    return re.sub(r"(?<!:)/{2,}", "/", path)
