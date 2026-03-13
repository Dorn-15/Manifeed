from __future__ import annotations

import re
import unicodedata


def normalize_article_identity_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = "".join(
        character
        for character in normalized_value
        if not unicodedata.combining(character)
    )
    normalized_value = normalized_value.casefold()
    normalized_value = re.sub(r"[^a-z0-9]+", " ", normalized_value)
    normalized_value = re.sub(r"\s+", " ", normalized_value).strip()
    return normalized_value or None
