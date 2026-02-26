from __future__ import annotations


def resolve_queue_kind(stream_name: str, *, check_stream: str, ingest_stream: str, error_stream: str) -> str:
    if stream_name == check_stream:
        return "check"
    if stream_name == ingest_stream:
        return "ingest"
    if stream_name == error_stream:
        return "error"
    return "error"
