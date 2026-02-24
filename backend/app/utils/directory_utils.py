from pathlib import Path
from pathlib import PurePosixPath

from .normalize_utils import normalize_file_extension

def is_empty_directory(path: Path) -> bool:
    return path.exists() and path.is_dir() and not any(path.iterdir())

def list_files_on_dir_with_ext(
    repository_path: Path,
    file_extension: str = "*",
) -> list[str]:
    normalized_extension = normalize_file_extension(file_extension)
    catalog_files = [
        file_path.relative_to(repository_path).as_posix()
        for file_path in repository_path.rglob(f"*{normalized_extension}")
        if ".git" not in file_path.parts
    ]
    return (catalog_files)
