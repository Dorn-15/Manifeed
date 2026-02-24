import re
from pathlib import Path
from urllib.parse import urlsplit

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

    return country.strip().lower()[:2]


def normalize_host(host: str | None) -> str | None:
    if host is None:
        return None

    normalized_host = host.strip()
    if not normalized_host:
        return None

    prefixed_host = normalized_host if "://" in normalized_host else f"//{normalized_host}"
    parsed_host = urlsplit(prefixed_host)
    hostname = parsed_host.hostname
    if hostname is None:
        return None

    normalized_host = hostname.strip().lower()
    return normalized_host or None
