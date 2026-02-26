from app.domain.result_mapping_domain import resolve_queue_kind


def test_resolve_queue_kind_maps_known_streams() -> None:
    assert resolve_queue_kind(
        "rss_check_results",
        check_stream="rss_check_results",
        ingest_stream="rss_ingest_results",
        error_stream="error_feeds_parsing",
    ) == "check"
    assert resolve_queue_kind(
        "rss_ingest_results",
        check_stream="rss_check_results",
        ingest_stream="rss_ingest_results",
        error_stream="error_feeds_parsing",
    ) == "ingest"
    assert resolve_queue_kind(
        "error_feeds_parsing",
        check_stream="rss_check_results",
        ingest_stream="rss_ingest_results",
        error_stream="error_feeds_parsing",
    ) == "error"


def test_resolve_queue_kind_falls_back_to_error_for_unknown_stream() -> None:
    assert resolve_queue_kind(
        "unknown_stream",
        check_stream="rss_check_results",
        ingest_stream="rss_ingest_results",
        error_stream="error_feeds_parsing",
    ) == "error"
