use std::path::PathBuf;

use manifeed_worker_common::{Result, WorkerAuthConfig, WorkerType};

const API_URL: &str = "http://127.0.0.1:8000";
const ENROLLMENT_TOKEN: &str = "manifeed-rss-enroll";
const IDENTITY_DIR: &str = "/home/dorn/.config/manifeed/worker-rss";
const POLL_SECONDS: u64 = 5;
const LEASE_SECONDS: u32 = 300;
const HOST_MAX_REQUESTS_PER_SECOND: u32 = 3;
const MAX_IN_FLIGHT_REQUESTS: usize = 10;
const MAX_CLAIMED_TASKS: usize = 8;
const REQUEST_TIMEOUT_SECONDS: u64 = 10;
const FETCH_RETRY_COUNT: u32 = 2;

#[derive(Clone, Debug)]
pub struct RssWorkerConfig {
    pub api_url: String,
    pub poll_seconds: u64,
    pub lease_seconds: u32,
    pub host_max_requests_per_second: u32,
    pub max_in_flight_requests: usize,
    pub max_claimed_tasks: usize,
    pub request_timeout_seconds: u64,
    pub fetch_retry_count: u32,
    pub auth: WorkerAuthConfig,
}

impl RssWorkerConfig {
    pub fn local_linux_x86() -> Result<Self> {
        Ok(Self {
            api_url: API_URL.to_string(),
            poll_seconds: POLL_SECONDS,
            lease_seconds: LEASE_SECONDS,
            host_max_requests_per_second: HOST_MAX_REQUESTS_PER_SECOND,
            max_in_flight_requests: MAX_IN_FLIGHT_REQUESTS,
            max_claimed_tasks: MAX_CLAIMED_TASKS,
            request_timeout_seconds: REQUEST_TIMEOUT_SECONDS,
            fetch_retry_count: FETCH_RETRY_COUNT,
            auth: WorkerAuthConfig {
                worker_type: WorkerType::RssScrapper,
                identity_dir: Some(PathBuf::from(IDENTITY_DIR)),
                enrollment_token: Some(ENROLLMENT_TOKEN.to_string()),
                worker_version: env!("CARGO_PKG_VERSION").to_string(),
            },
        })
    }
}
