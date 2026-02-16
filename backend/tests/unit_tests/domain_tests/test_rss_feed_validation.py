from app.domain.rss import validate_rss_feed_payload


def test_validate_rss_feed_payload_accepts_rss_xml() -> None:
    status, error = validate_rss_feed_payload(
        content="""<?xml version="1.0" encoding="UTF-8"?><rss><channel></channel></rss>""",
        content_type="application/rss+xml",
    )

    assert status == "valid"
    assert error is None


def test_validate_rss_feed_payload_rejects_non_xml_content() -> None:
    status, error = validate_rss_feed_payload(
        content="hello world",
        content_type="text/plain",
    )

    assert status == "invalid"
    assert error == "Not an XML/RSS feed"
