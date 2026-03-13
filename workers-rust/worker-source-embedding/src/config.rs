use std::path::PathBuf;

use manifeed_worker_common::{Result, WorkerAuthConfig, WorkerType};

const API_URL: &str = "http://127.0.0.1:8000";
const ENROLLMENT_TOKEN: &str = "manifeed-embedding-enroll";
const IDENTITY_DIR: &str = "/home/dorn/.config/manifeed/worker-source-embedding";
const MODEL_DIR: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../models/multilingual-e5-large"
);
const POLL_SECONDS: u64 = 30;
const LEASE_SECONDS: u32 = 300;
const INFERENCE_BATCH_SIZE: usize = 1;

#[derive(Clone, Debug)]
pub struct EmbeddingWorkerConfig {
    pub api_url: String,
    pub poll_seconds: u64,
    pub lease_seconds: u32,
    pub inference_batch_size: usize,
    pub model_dir: PathBuf,
    pub auth: WorkerAuthConfig,
}

impl EmbeddingWorkerConfig {
    pub fn local_linux_x86() -> Result<Self> {
        Ok(Self {
            api_url: API_URL.to_string(),
            poll_seconds: POLL_SECONDS,
            lease_seconds: LEASE_SECONDS,
            inference_batch_size: INFERENCE_BATCH_SIZE,
            model_dir: PathBuf::from(MODEL_DIR),
            auth: WorkerAuthConfig {
                worker_type: WorkerType::SourceEmbedding,
                identity_dir: Some(PathBuf::from(IDENTITY_DIR)),
                enrollment_token: Some(ENROLLMENT_TOKEN.to_string()),
                worker_version: env!("CARGO_PKG_VERSION").to_string(),
            },
        })
    }
}
