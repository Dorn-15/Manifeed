use std::fmt::{Display, Formatter};
use std::io::Cursor;
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use reqwest::header::{HeaderMap, HeaderValue, IF_MODIFIED_SINCE, IF_NONE_MATCH};
use reqwest::{StatusCode, Url};
use tokio::sync::Mutex;

use super::normalize::normalize_sources;
use crate::logging::stdout_log;
use crate::model::{RssFeedPayload, RssResult};
use crate::worker::{FeedFetcher, Result};

pub(super) const SIMPLE_FETCHPROTECTION: u8 = 1;
pub(super) const ADVANCED_FETCHPROTECTION: u8 = 2;
const DEFAULT_RSS_HEADERS: [(&str, &str); 4] = [
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"),
    ("Accept-Language", "fr-FR,fr;q=0.9,en-US;q=0.7,en;q=0.6"),
    (
        "Accept",
        "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml,application/atom+xml;q=0.8,*/*;q=0.7",
    ),
    ("Accept-Encoding", "gzip, deflate, br"),
];

pub struct HttpFeedFetcher {
    client: reqwest::Client,
    host_request_deadlines: Arc<Mutex<std::collections::HashMap<String, tokio::time::Instant>>>,
    host_max_requests_per_second: u32,
    fetch_retry_count: u32,
}

#[derive(Debug)]
enum FetchAttemptError {
    Permanent(String),
    Transient(String),
}

impl Display for FetchAttemptError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Permanent(message) | Self::Transient(message) => formatter.write_str(message),
        }
    }
}

impl std::error::Error for FetchAttemptError {}

impl FetchAttemptError {
    fn is_transient(&self) -> bool {
        matches!(self, Self::Transient(_))
    }
}

impl HttpFeedFetcher {
    pub fn new(
        host_max_requests_per_second: u32,
        request_timeout_seconds: u64,
        fetch_retry_count: u32,
    ) -> Result<Self> {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(request_timeout_seconds.max(1)))
            .build()?;
        Ok(Self {
            client,
            host_request_deadlines: Arc::new(Mutex::new(std::collections::HashMap::new())),
            host_max_requests_per_second,
            fetch_retry_count,
        })
    }

    async fn fetch_once(
        &self,
        job_id: &str,
        ingest: bool,
        feed: &RssFeedPayload,
    ) -> std::result::Result<RssResult, FetchAttemptError> {
        if feed.fetchprotection == 0 {
            return Ok(RssResult::error(
                job_id,
                ingest,
                feed,
                "Blocked by fetch protection",
            ));
        }

        self.wait_for_rate_limit(feed).await;

        let response = self
            .client
            .get(&feed.feed_url)
            .headers(
                build_headers(feed)
                    .map_err(|error| FetchAttemptError::Permanent(error.to_string()))?,
            )
            .send()
            .await
            .map_err(classify_reqwest_error)?;

        let response_etag = response
            .headers()
            .get("etag")
            .and_then(|value| value.to_str().ok())
            .map(|value| value.to_string());
        let response_last_modified = response
            .headers()
            .get("last-modified")
            .and_then(|value| value.to_str().ok())
            .and_then(|value| httpdate::parse_http_date(value).ok())
            .map(DateTime::<Utc>::from);
        stdout_log(format!(
            "fetch {} {} {} {}",
            feed.feed_id,
            response.status().as_u16(),
            if response.status().is_success() {
                "ok"
            } else {
                "ko"
            },
            feed.feed_url
        ));

        if response.status() == StatusCode::NOT_MODIFIED {
            return Ok(RssResult::not_modified(
                job_id,
                ingest,
                feed,
                response_etag,
                response_last_modified,
            ));
        }

        if is_transient_status(response.status()) {
            return Err(FetchAttemptError::Transient(format!(
                "Transient HTTP status {} for {}",
                response.status(),
                feed.feed_url
            )));
        }

        if !response.status().is_success() {
            return Err(FetchAttemptError::Permanent(format!(
                "HTTP status {} for {}",
                response.status(),
                feed.feed_url
            )));
        }

        let bytes = response.bytes().await.map_err(classify_reqwest_error)?;
        let parsed_feed = feed_rs::parser::parse(Cursor::new(bytes)).map_err(|error| {
            FetchAttemptError::Permanent(format!(
                "Failed to parse RSS feed {}: {}",
                feed.feed_url, error
            ))
        })?;
        stdout_log(format!("parsing {} ok {}", feed.feed_id, feed.feed_url));
        let normalized_sources = normalize_sources(&parsed_feed, feed.last_db_article_published_at);

        Ok(RssResult::success(
            job_id,
            ingest,
            feed,
            response_etag,
            response_last_modified.or(parsed_feed.updated),
            Some(feed.fetchprotection),
            normalized_sources,
        ))
    }

    async fn wait_for_rate_limit(&self, feed: &RssFeedPayload) {
        let key = scheduling_host_key(feed);
        let interval_ms = 1000_u64 / self.host_max_requests_per_second.max(1) as u64;
        let sleep_until = {
            let deadlines = self.host_request_deadlines.lock().await;
            deadlines.get(&key).copied()
        };
        if let Some(deadline) = sleep_until {
            let now = tokio::time::Instant::now();
            if deadline > now {
                tokio::time::sleep_until(deadline).await;
            }
        }
        let mut deadlines = self.host_request_deadlines.lock().await;
        deadlines.insert(
            key,
            tokio::time::Instant::now() + tokio::time::Duration::from_millis(interval_ms),
        );
    }
}

#[async_trait]
impl FeedFetcher for HttpFeedFetcher {
    async fn fetch(&self, job_id: &str, ingest: bool, feed: &RssFeedPayload) -> Result<RssResult> {
        let fetch_attempts = build_fetch_attempts(feed.fetchprotection, ingest);
        let mut last_result = None;

        for fetchprotection in fetch_attempts {
            let attempt_feed = RssFeedPayload {
                fetchprotection,
                ..feed.clone()
            };
            let mut attempt_no = 0;
            loop {
                match self.fetch_once(job_id, ingest, &attempt_feed).await {
                    Ok(result) => return Ok(result),
                    Err(error) if error.is_transient() && attempt_no < self.fetch_retry_count => {
                        attempt_no += 1;
                        tokio::time::sleep(Duration::from_millis(250 * u64::from(attempt_no)))
                            .await;
                    }
                    Err(error) => {
                        last_result = Some(RssResult::error(
                            job_id,
                            ingest,
                            &attempt_feed,
                            error.to_string(),
                        ));
                        break;
                    }
                }
            }
        }

        Ok(last_result.unwrap_or_else(|| {
            RssResult::error(job_id, ingest, feed, "No fetch strategy available")
        }))
    }
}

pub(crate) fn resolve_effective_host(feed: &RssFeedPayload) -> Option<String> {
    normalize_host(feed.host_header.as_deref()).or_else(|| {
        Url::parse(&feed.feed_url)
            .ok()
            .and_then(|url| url.host_str().map(|host| host.to_lowercase()))
    })
}

pub(crate) fn scheduling_host_key(feed: &RssFeedPayload) -> String {
    resolve_effective_host(feed).unwrap_or_else(|| format!("feed:{}", feed.feed_id))
}

pub(super) fn build_headers(feed: &RssFeedPayload) -> Result<HeaderMap> {
    let mut headers = HeaderMap::new();
    for (key, value) in DEFAULT_RSS_HEADERS {
        headers.insert(key, HeaderValue::from_str(value)?);
    }
    if feed.fetchprotection == ADVANCED_FETCHPROTECTION {
        if let Some(host) = &feed.host_header {
            headers.insert("Host", HeaderValue::from_str(host)?);
            headers.insert("Origin", HeaderValue::from_str(&format!("https://{host}"))?);
            headers.insert(
                "Referer",
                HeaderValue::from_str(&format!("https://{host}/"))?,
            );
        }
    }
    if let Some(etag) = &feed.etag {
        headers.insert(IF_NONE_MATCH, HeaderValue::from_str(etag)?);
    }
    if let Some(last_update) = feed.last_update {
        headers.insert(
            IF_MODIFIED_SINCE,
            HeaderValue::from_str(&httpdate::fmt_http_date(last_update.into()))?,
        );
    }
    Ok(headers)
}

pub(super) fn build_fetch_attempts(fetchprotection: u8, ingest: bool) -> Vec<u8> {
    if fetchprotection == 0 {
        return vec![0];
    }

    if ingest {
        return match fetchprotection {
            SIMPLE_FETCHPROTECTION => vec![SIMPLE_FETCHPROTECTION, ADVANCED_FETCHPROTECTION],
            ADVANCED_FETCHPROTECTION => vec![ADVANCED_FETCHPROTECTION, SIMPLE_FETCHPROTECTION],
            _ => vec![fetchprotection],
        };
    }

    vec![SIMPLE_FETCHPROTECTION, ADVANCED_FETCHPROTECTION]
}

fn normalize_host(raw_host: Option<&str>) -> Option<String> {
    let value = raw_host?.trim();
    if value.is_empty() {
        return None;
    }

    let with_scheme = if value.contains("://") {
        value.to_string()
    } else {
        format!("https://{value}")
    };

    Url::parse(&with_scheme)
        .ok()
        .and_then(|url| url.host_str().map(|host| host.to_lowercase()))
}

fn classify_reqwest_error(error: reqwest::Error) -> FetchAttemptError {
    if let Some(status) = error.status() {
        if is_transient_status(status) {
            return FetchAttemptError::Transient(format!(
                "Transient HTTP status {status}: {error}"
            ));
        }
        return FetchAttemptError::Permanent(format!("HTTP status {status}: {error}"));
    }

    if error.is_timeout() || error.is_connect() || error.is_body() {
        return FetchAttemptError::Transient(error.to_string());
    }

    FetchAttemptError::Permanent(error.to_string())
}

fn is_transient_status(status: StatusCode) -> bool {
    matches!(
        status,
        StatusCode::REQUEST_TIMEOUT
            | StatusCode::TOO_MANY_REQUESTS
            | StatusCode::INTERNAL_SERVER_ERROR
            | StatusCode::BAD_GATEWAY
            | StatusCode::SERVICE_UNAVAILABLE
            | StatusCode::GATEWAY_TIMEOUT
    )
}
