import re
from pathlib import Path
 
from app.errors.rss import RssRepositorySyncError

def normalize_file_extension(file_extension: str) -> str:
    normalized_extension = file_extension.strip()
    if not normalized_extension:
        raise RssRepositorySyncError("File extension cannot be empty.")

    if normalized_extension.startswith("*."):
        normalized_extension = normalized_extension[1:]
    elif normalized_extension.startswith("*"):
        normalized_extension = normalized_extension[1:]

    if not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"
    return normalized_extension


def normalize_name_from_filename(file_name: str) -> str:
    raw_name = Path(file_name).stem.replace("_", " ")
    normalized_name = re.sub(r"\s+", " ", raw_name).strip()
    if not normalized_name:
        raise ValueError(f"Could not derive name from file path: {file_name}")
    return normalized_name

def normalize_country(country: str | None) -> str | None:
    if country is None:
        return None

    normalized_language = country.strip().lower()
    if not normalized_language:
        return None
    return normalized_language[:2]


MAP_COUNTRY_TO_LANG = {
    "au": "en",
    "br": "pt",
    "ca": "en",
    "cn": "zh",
    "de": "de",
    "es": "es",
    "en": "en",
    "eu": "en",
    "fr": "fr",
    "gb": "en",
    "hk": "en",
    "it": "it",
    "uk": "en",
    "us": "en",
    "wo": "en",
}

def normalize_lang_by_country(country: str | None) -> str | None:
    return MAP_COUNTRY_TO_LANG.get(country) or None