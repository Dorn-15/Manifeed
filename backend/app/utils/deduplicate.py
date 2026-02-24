from collections.abc import Sequence

def dedup_str(str_list: Sequence[str]) -> list[str]:
    unique_str: list[str] = []
    seen_str: set[str] = set()

    for new_str in str_list:
        clean_str = new_str.strip()
        if not clean_str or clean_str in seen_str:
            continue
        seen_str.add(clean_str)
        unique_str.append(clean_str)

    return unique_str