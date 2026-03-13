use std::time::Duration;

use tracing::{info, warn};
use worker_source_embedding::api::HttpEmbeddingGateway;
use worker_source_embedding::config::EmbeddingWorkerConfig;
use worker_source_embedding::onnx::OnnxEmbedder;
use worker_source_embedding::worker::EmbeddingWorker;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt().with_target(false).init();

    let config = EmbeddingWorkerConfig::local_linux_x86()?;
    let gateway = HttpEmbeddingGateway::new(&config)?;
    let embedder = OnnxEmbedder::new(config.model_dir.clone())?;
    let mut worker = EmbeddingWorker::new(gateway, embedder, config.inference_batch_size);

    info!("worker_source_embedding rust v2 started");
    loop {
        match worker.run_once().await {
            Ok(processed) => {
                if !processed {
                    tokio::time::sleep(Duration::from_secs(config.poll_seconds)).await;
                }
            }
            Err(error) if error.is_network_error() => {
                warn!(
                    retry_delay_seconds = config.poll_seconds,
                    "network error in embedding worker loop, retrying: {error}"
                );
                tokio::time::sleep(Duration::from_secs(config.poll_seconds)).await;
            }
            Err(error) => return Err(Box::new(error) as Box<dyn std::error::Error>),
        }
    }
}
