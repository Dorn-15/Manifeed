use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RssFeedPayload {
    pub feed_id: u64,
    pub feed_url: String,
    pub company_id: Option<u64>,
    pub host_header: Option<String>,
    pub fetchprotection: u8,
    pub etag: Option<String>,
    pub last_update: Option<DateTime<Utc>>,
    pub last_db_article_published_at: Option<DateTime<Utc>>,
}

#[derive(Clone, Debug)]
pub struct ClaimedRssTask {
    pub task_id: u64,
    pub execution_id: u64,
    pub job_id: String,
    pub ingest: bool,
    pub feeds: Vec<RssFeedPayload>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RssSource {
    pub title: String,
    pub url: String,
    pub summary: Option<String>,
    pub author: Option<String>,
    pub published_at: Option<DateTime<Utc>>,
    pub image_url: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RssResult {
    pub job_id: String,
    pub ingest: bool,
    pub feed_id: u64,
    pub feed_url: String,
    pub status: String,
    pub error_message: Option<String>,
    pub new_etag: Option<String>,
    pub new_last_update: Option<DateTime<Utc>>,
    pub fetchprotection: u8,
    pub resolved_fetchprotection: Option<u8>,
    pub sources: Vec<RssSource>,
}

impl RssResult {
    pub fn success(
        job_id: impl Into<String>,
        ingest: bool,
        feed: &RssFeedPayload,
        new_etag: Option<String>,
        new_last_update: Option<DateTime<Utc>>,
        resolved_fetchprotection: Option<u8>,
        sources: Vec<RssSource>,
    ) -> Self {
        Self {
            new_etag,
            new_last_update,
            resolved_fetchprotection,
            sources,
            ..Self::new(job_id, ingest, feed, "success")
        }
    }

    pub fn not_modified(
        job_id: impl Into<String>,
        ingest: bool,
        feed: &RssFeedPayload,
        new_etag: Option<String>,
        new_last_update: Option<DateTime<Utc>>,
    ) -> Self {
        Self {
            new_etag,
            new_last_update,
            ..Self::new(job_id, ingest, feed, "not_modified")
        }
    }

    pub fn error(
        job_id: impl Into<String>,
        ingest: bool,
        feed: &RssFeedPayload,
        error_message: impl Into<String>,
    ) -> Self {
        Self {
            error_message: Some(error_message.into()),
            new_etag: feed.etag.clone(),
            new_last_update: feed.last_update,
            ..Self::new(job_id, ingest, feed, "error")
        }
    }

    fn new(job_id: impl Into<String>, ingest: bool, feed: &RssFeedPayload, status: &str) -> Self {
        Self {
            job_id: job_id.into(),
            ingest,
            feed_id: feed.feed_id,
            feed_url: feed.feed_url.clone(),
            status: status.to_string(),
            error_message: None,
            new_etag: None,
            new_last_update: None,
            fetchprotection: feed.fetchprotection,
            resolved_fetchprotection: None,
            sources: Vec::new(),
        }
    }
}
